#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
常驻脚本执行池

问题：每个策略接口都用 subprocess 新起一次 python3，
      光解释器启动 + 导入 pandas/numpy/requests 就要 0.7~1.5 秒。
      这部分开销与"数据是否新鲜"完全无关，纯粹是重复劳动。

做法：预热一批常驻 Python 进程，启动时已导入好依赖；
      每次调用把脚本用 runpy 重新执行一遍，结果写进临时文件再读回。
      —— 解释器与依赖复用，单次开销降到几十毫秒；
      —— 脚本仍被真实完整执行，实时价仍是每次现拉，绝不复用结果。

不用管道传结果，是因为脚本 stdout 可能很大（轮动脚本约 40KB），
配合 stderr 输出容易造成管道阻塞；临时文件方式没有这个风险。

三个关键设计（都为了"线上不会突然变慢"）：

1. 只预热 requests，不预热 pandas/numpy
   MA200 链路只用到 requests，却因为统一预热白付 0.39 秒启动、多吃 80MB 内存。
   实测：预热 requests 约 0.11s / 29MB；再加 numpy+pandas 变成 0.50s / 109MB。
   需要 pandas 的脚本（轮动、均值回归）首次执行时自行导入，之后该 worker 就是热的，
   由后台预热任务把这条路走一遍，用户请求不会撞上。

2. 按需扩容，不按固定 4 个
   策略接口的超时是 30 秒，若 4 个 worker 全被占住，第 5 个请求会去起临时 worker
   （0.44 秒启动，低配容器上更久）。这里改成：没有空闲就现开一个并留在池里，
   请求直接受益；空闲过多（超过 max_size）时回收多余的，控制内存。

3. 被杀不连坐，巡检只补不重建
   worker 被外部杀掉（OOM、容器回收）时，原来会退化成"每次请求都新建一个再杀掉"，
   每次都要付完整启动成本。现在改为：把死的从池里摘掉、立即补一个新的，
   本次请求仍用存活的 worker 或新补的 worker，池子稳态迅速恢复。
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# 池子生命周期日志开关。线上排查"为什么每次都要 5 秒"时最有用：
# 如果日志里 Worker 出生/死亡很频繁，说明进程在被反复重建（内存被 OOM 是常见原因）。
POOL_LOG = os.environ.get('POOL_LOG', '1') != '0'
_BOOT_SEQ = [0]


def _plog(msg):
    if not POOL_LOG:
        return
    import time as _t
    print(f"[{_t.strftime('%H:%M:%S')}][池] {msg}", flush=True)

# 预热模块：只放几乎所有脚本都要、且加载快的
BOOT_MODULES = ("json", "re", "os", "sys", "math", "datetime", "requests")

WORKER_BOOT = r'''
import sys, os, json, runpy, traceback

# 预热：只导入轻量且通用的依赖。
# pandas/numpy 很重（+0.39s / +80MB），这里不预热，
# 由真正需要它们的脚本在首次执行时自行导入。
for _m in %(mods)s:
    try:
        __import__(_m)
    except Exception:
        pass

sys.path.insert(0, os.environ["SCRIPTS_DIR"])

def _run(path, argv, out_path):
    old_argv, old_out = sys.argv, sys.stdout
    sys.argv = [path] + argv
    fh = open(out_path, "w", encoding="utf-8")
    ok = True
    try:
        sys.stdout = fh
        runpy.run_path(path, run_name="__main__")
    except SystemExit:
        pass
    except Exception:
        ok = False
        traceback.print_exc(file=sys.stderr)
    finally:
        sys.stdout = old_out
        fh.close()
    return ok

print("READY", flush=True)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    req_id = ""
    try:
        req = json.loads(line)
        req_id = req.get("id", "")
        ok = _run(req["path"], req.get("args", []), req["out"])
        print("__DONE__ %%s %%s" %% (req_id, "1" if ok else "0"), flush=True)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        print("__DONE__ %%s 0" %% req_id, flush=True)
''' % {'mods': repr(BOOT_MODULES)}


class Worker:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self._start()

    def _start(self):
        env = dict(os.environ)
        env['SCRIPTS_DIR'] = SCRIPTS_DIR
        env['PYTHONUNBUFFERED'] = '1'
        t0 = time.time()
        # stderr 直接丢弃到 DEVNULL，避免被大量日志堵死
        self.proc = subprocess.Popen(
            [sys.executable, '-u', '-c', WORKER_BOOT],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env=env,
        )
        self.proc.stdout.readline()   # READY
        self.born = time.time()
        _BOOT_SEQ[0] += 1
        self.seq = _BOOT_SEQ[0]
        _plog(f"Worker#{self.seq} 启动 pid={self.proc.pid} 就绪耗时 {time.time()-t0:.2f}s")
        threading.Thread(target=self._watch, daemon=True).start()

    def _watch(self):
        """守候进程退出：记录退出码 + 运行时长。

        OOM 被杀在容器里表现为退出码 -9（SIGKILL）或 137，
        运行时长很短说明是被反复重建，这正是"每次都要几秒"的典型特征。
        """
        try:
            rc = self.proc.wait()
        except Exception:
            return
        life = time.time() - getattr(self, 'born', time.time())
        _plog(f"Worker#{getattr(self, 'seq', '?')} 退出 pid={self.proc.pid} "
              f"rc={rc} 存活 {life:.1f}s")

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def kill(self):
        try:
            self.proc.kill()
        except Exception:
            pass

    def run(self, path, args, timeout):
        if not self.alive():
            self._start()
        fd, out_path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        try:
            req_id = str(id(out_path))
            self.proc.stdin.write(json.dumps(
                {'id': req_id, 'path': path, 'args': args, 'out': out_path}) + '\n')
            self.proc.stdin.flush()

            while True:
                line = self.proc.stdout.readline()
                if line == '':
                    raise RuntimeError('worker 进程已退出')
                s = line.strip()
                if s.startswith('__DONE__'):
                    ok = s.endswith(' 1')
                    break
            with open(out_path, 'r', encoding='utf-8') as f:
                body = f.read()
            return ok, body
        finally:
            try:
                os.unlink(out_path)
            except Exception:
                pass


class WorkerPool:
    def __init__(self, size=2, max_size=6):
        self.size = max(1, size)          # 常驻数量（巡检维持的下限）
        self.max_size = max(self.size, max_size)
        self.pool = []
        self.pool_lock = threading.Lock()
        for _ in range(self.size):
            try:
                self.pool.append(Worker())
            except Exception:
                break
        # 后台巡检：worker 意外退出时自动补齐，避免下次请求撞上冷启动
        threading.Thread(target=self._heal_loop, daemon=True).start()

    def _alive(self):
        return [w for w in self.pool if w.alive()]

    def _heal_loop(self):
        """巡检：补齐到 size，多于 max_size 的回收掉。

        注意这里必须先把死掉的 worker 对象彻底移出列表再补新的，
        否则旧对象（连同其管道）会一直占着位置，导致"补了等于没补"。
        """
        import time as _t
        while True:
            _t.sleep(3)
            try:
                with self.pool_lock:
                    before = len(self.pool)
                    dead = [w for w in self.pool if not w.alive()]
                    self.pool = [w for w in self.pool if w.alive()]
                    alive = len(self.pool)
                    if dead:
                        _plog(f"巡检清理死亡 worker {len(dead)} 个，存活 {alive}")
                    need = self.size - alive
                    extra = alive - self.max_size
                    if extra > 0:
                        # 回收多余的（挑没被占用的）
                        for w in list(self.pool):
                            if extra <= 0:
                                break
                            if w.lock.acquire(blocking=False):
                                try:
                                    w.kill()
                                    self.pool.remove(w)
                                    extra -= 1
                                finally:
                                    w.lock.release()
                    for _ in range(max(0, need)):
                        try:
                            self.pool.append(Worker())
                        except Exception:
                            break
                    if len(self.pool) != before:
                        _plog(f"巡检后池内 {before} -> {len(self.pool)}")
            except Exception:
                pass

    def _acquire(self, fresh=False):
        """取一个空闲 worker。

        fresh=True 时忽略池里现有的（用于"池里全是死进程"的补救）。
        拿不到就现开一个并留在池里，让下一次请求直接受益。
        """
        with self.pool_lock:
            if not fresh:
                for cand in self.pool:
                    # 必须先判活：进程可能刚被 OOM / kill 掉，
                    # 此时锁还是空闲的，直接取走会在 run 里立刻抛"进程已退出"。
                    if cand.alive() and cand.lock.acquire(blocking=False):
                        return cand
            if fresh or len(self.pool) < self.max_size:
                try:
                    w = Worker()
                    if w.lock.acquire(blocking=False):
                        self.pool.append(w)
                        return w
                    w.kill()
                except Exception:
                    pass
        return None

    def _discard(self, w):
        """把失效 worker 摘掉，并立刻补一个新的维持常驻数量。"""
        with self.pool_lock:
            if w in self.pool:
                self.pool.remove(w)
        w.kill()
        def _refill():
            try:
                with self.pool_lock:
                    if len(self._alive()) >= self.size:
                        return
                    self.pool.append(Worker())
            except Exception:
                pass
        threading.Thread(target=_refill, daemon=True).start()

    def run(self, path, args, timeout=60):
        t0 = time.time()
        w, tag = self._acquire_tagged()
        wait = time.time() - t0      # 取 worker 的等待时间（含新建进程的成本）

        # 没拿到空闲 worker（已达上限且全忙）：临时开一个，用完即弃
        if w is None:
            t1 = time.time()
            tmp = Worker()
            boot = time.time() - t1
            _plog(f"{os.path.basename(path)} 无空闲 worker，临时进程 boot {boot:.2f}s")
            try:
                ok, body = tmp.run(path, args, timeout)
                return {'ok': ok, 'stdout': body, 'stderr': '',
                        'via': f'临时进程(boot {boot:.2f}s)', 'elapsed': time.time() - t0}
            except Exception as e:
                return {'ok': False, 'stdout': '', 'stderr': str(e),
                        'via': f'临时进程(boot {boot:.2f}s)', 'elapsed': time.time() - t0}
            finally:
                tmp.kill()

        # 排队超过 0.5s 才值得单独记一笔——这是"看起来慢但 CPU 不忙"的典型原因
        if wait > 0.5:
            _plog(f"{os.path.basename(path)} 等 worker 用了 {wait:.2f}s（池内 {len(self.pool)}）")

        # 锁的归属：正常路径由这里释放；worker 失效时在 _exec 里就地交接给新 worker
        handoff = False
        try:
            handoff, out = self._exec(w, path, args, timeout)
            out.setdefault('via', tag)
            out.setdefault('elapsed', time.time() - t0)
            return out
        finally:
            if not handoff:
                try:
                    w.lock.release()
                except Exception:
                    pass

    def _acquire_tagged(self):
        """取 worker，同时返回它是"已在池里的"还是"新开的"，供日志定位。"""
        with self.pool_lock:
            before = len(self.pool)
            alive_before = len([w for w in self.pool if w.alive()])
        w = self._acquire()
        if w is None:
            return None, 'none'
        with self.pool_lock:
            grew = len(self.pool) > before
        tag = '扩容worker' if grew else f'池内worker(存活{alive_before})'
        return w, tag

    def _exec(self, w, path, args, timeout):
        """执行一次，返回 (是否已把锁交接出去, 结果字典)。"""
        try:
            ok, body = w.run(path, args, timeout)
            return False, {'ok': ok, 'stdout': body, 'stderr': '', 'via': '池内worker'}
        except Exception as e:
            # worker 已死（被 OOM / 外部杀掉）：摘掉并后台补位。
            # 本次请求换一个存活的 worker 重试，不让用户承担重建成本。
            self._discard(w)
            try:
                w.lock.release()      # 释放死 worker 的锁
            except Exception:
                pass

            last_err = e
            # 池里可能同时躺着一批死进程（例如容器刚被 OOM 扫过），
            # 所以最多重试两次：先取存活的，再不行就强制新建。
            for attempt in ('pool', 'fresh'):
                w2 = self._acquire(fresh=(attempt == 'fresh'))
                if w2 is None:
                    continue
                try:
                    ok, body = w2.run(path, args, timeout)
                    return True, {'ok': ok, 'stdout': body, 'stderr': '',
                                  'via': f'重建后重试({attempt})'}
                except Exception as e2:
                    last_err = e2
                    self._discard(w2)
                    try:
                        w2.lock.release()
                    except Exception:
                        pass
            return False, {'ok': False, 'stdout': '', 'stderr': str(last_err)}


_POOL = None
_POOL_LOCK = threading.Lock()


def get_pool():
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                _POOL = WorkerPool(
                    size=int(os.environ.get('WORKER_POOL_SIZE', '2')),
                    max_size=int(os.environ.get('WORKER_POOL_MAX', '6')),
                )
    return _POOL


def run_script(script_name, args=None, timeout=60):
    path = os.path.join(SCRIPTS_DIR, script_name)
    return get_pool().run(path, [str(a) for a in (args or [])], timeout)
