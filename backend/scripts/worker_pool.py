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
"""
import json
import os
import subprocess
import sys
import tempfile
import threading

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

WORKER_BOOT = r'''
import sys, os, json, runpy, traceback

# 预热：把策略脚本常用的重依赖先导入，之后重复执行脚本不再付这份代价
for _m in ("json", "re", "os", "sys", "math", "datetime",
           "requests", "numpy", "pandas"):
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
        print("__DONE__ %s %s" % (req_id, "1" if ok else "0"), flush=True)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        print("__DONE__ %s 0" % req_id, flush=True)
'''


class Worker:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self._start()

    def _start(self):
        env = dict(os.environ)
        env['SCRIPTS_DIR'] = SCRIPTS_DIR
        env['PYTHONUNBUFFERED'] = '1'
        # stderr 直接丢弃到 DEVNULL，避免被大量日志堵死
        self.proc = subprocess.Popen(
            [sys.executable, '-u', '-c', WORKER_BOOT],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env=env,
        )
        self.proc.stdout.readline()   # READY

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

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
    def __init__(self, size=4):
        self.size = size
        self.pool = []
        self.pool_lock = threading.Lock()
        for _ in range(size):
            try:
                self.pool.append(Worker())
            except Exception:
                break
        # 后台巡检：worker 意外退出时自动补齐，避免下次请求撞上冷启动
        threading.Thread(target=self._heal_loop, daemon=True).start()

    def _heal_loop(self):
        import time as _t
        while True:
            _t.sleep(5)
            try:
                alive = [w for w in self.pool if w.alive()]
                missing = self.size - len(alive)
                if missing <= 0:
                    continue
                # 先移除已死的，再补足
                with self.pool_lock:
                    self.pool = [w for w in self.pool if w.alive()]
                for _ in range(missing):
                    try:
                        w = Worker()
                        with self.pool_lock:
                            self.pool.append(w)
                    except Exception:
                        break
            except Exception:
                pass

    def run(self, path, args, timeout=60):
        w = None
        with self.pool_lock:
            for cand in self.pool:
                if cand.alive() and cand.lock.acquire(blocking=False):
                    w = cand
                    break
        if w is None:
            # 全忙或全挂：起一个临时 worker 保证可用性
            tmp = Worker()
            try:
                ok, body = tmp.run(path, args, timeout)
                return {'ok': ok, 'stdout': body, 'stderr': ''}
            except Exception as e:
                return {'ok': False, 'stdout': '', 'stderr': str(e)}
            finally:
                try:
                    tmp.proc.kill()
                except Exception:
                    pass
        try:
            ok, body = w.run(path, args, timeout)
            return {'ok': ok, 'stdout': body, 'stderr': ''}
        except Exception as e:
            # 该 worker 已死：从池中摘掉（巡检线程会补新的），
            # 本次请求改用临时 worker，不让用户承担重建成本
            try:
                w.proc.kill()
            except Exception:
                pass
            with self.pool_lock:
                if w in self.pool:
                    self.pool.remove(w)
            try:
                tmp = Worker()
                try:
                    ok, body = tmp.run(path, args, timeout)
                    return {'ok': ok, 'stdout': body, 'stderr': ''}
                finally:
                    try:
                        tmp.proc.kill()
                    except Exception:
                        pass
            except Exception as e2:
                return {'ok': False, 'stdout': '', 'stderr': f'{e} / {e2}'}
        finally:
            try:
                w.lock.release()
            except Exception:
                pass


_POOL = None
_POOL_LOCK = threading.Lock()


def get_pool():
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                _POOL = WorkerPool(size=int(os.environ.get('WORKER_POOL_SIZE', '4')))
    return _POOL


def run_script(script_name, args=None, timeout=60):
    path = os.path.join(SCRIPTS_DIR, script_name)
    return get_pool().run(path, [str(a) for a in (args or [])], timeout)


if __name__ == '__main__':
    import time
    for name, argv in [('calculate_ma200_trend.py', []),
                       ('calculate_momentum_joinquant.py', ['25', '0', '0.97'])]:
        for i in range(3):
            t = time.time()
            r = run_script(name, argv)
            print(f"{name} 第{i+1}次: {time.time()-t:.3f}s  ok={r['ok']} "
                  f"输出{len(r['stdout'])}字节", flush=True)
