#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""线上诊断：一次性测清"切换 tab 要 5 秒"慢在哪一层。

用法（在服务器上执行，域名换成你自己的）：
    python3 diag.py https://你的域名
    python3 diag.py http://127.0.0.1:5000                              # 只测前端
    python3 diag.py http://127.0.0.1:5000 http://127.0.0.1:3000        # 前端 + 后端

只依赖标准库，不用装任何包。
"""
import sys
import time
import json
import urllib.request
import urllib.error

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

FE = sys.argv[1].rstrip('/')
BE = sys.argv[2].rstrip('/') if len(sys.argv) > 2 else None


def one(url, timeout=120):
    """返回 (总耗时, 首字节耗时, 状态码, X-Server-Cost, 体积, 错误)"""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'diag/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            t_head = time.time()
            body = r.read()
            return (time.time() - t0, t_head - t0, r.status,
                    r.headers.get('X-Server-Cost'), len(body), None)
    except urllib.error.HTTPError as e:
        return (time.time() - t0, None, e.code, None, 0, 'HTTP %s' % e.code)
    except Exception as e:
        return (time.time() - t0, None, -1, None, 0, repr(e))


def block(title, url, n=3):
    print("\n%s\n  %s" % (title, url))
    for i in range(n):
        total, head, code, sc, size, err = one(url)
        sc_s = ("  后端计算 %6.0fms" % (float(sc) * 1000)) if sc else "  后端未返回耗时头"
        err_s = ("  [!] %s" % err) if err else ""
        head_s = ('%.0f' % (head * 1000)) if head else '-'
        print("  第%d次: 总 %7.0fms  首字节 %6sms%s  %dB  HTTP %s%s"
              % (i + 1, total * 1000, head_s, sc_s, size, code, err_s))
        time.sleep(0.3)


print("=" * 70)
print("诊断目标  FE=%s%s" % (FE, ("  BE=%s" % BE) if BE else ""))
print("=" * 70)

if BE:
    print("\n【1】后端进程状态（worker 池 / 内存 / Python 版本）")
    total, head, code, sc, size, err = one(BE + '/api/debug/perf')
    if err:
        print("  [!] 调不通: %s" % err)
        if code == 404:
            print("      404 说明线上跑的仍是旧版本，日志与诊断接口都不存在，先重新部署")
    else:
        with urllib.request.urlopen(BE + '/api/debug/perf', timeout=60) as r:
            d = json.loads(r.read())
        b = d.get('backend', {})
        wp = d.get('workerPool', {})
        print("  Python %s  CPU %s 核  后端常驻内存 %sMB  已运行 %ss"
              % (b.get('python'), b.get('cpuCount'), b.get('rssMB'), b.get('uptimeSec')))
        print("  worker 池: 存活 %s / 共 %s (常驻 %s, 上限 %s)"
              % (wp.get('alive'), wp.get('poolLen'), wp.get('size'), wp.get('max')))
        for w in wp.get('workers', []):
            print("    pid=%s alive=%s busy=%s" % (w.get('pid'), w.get('alive'), w.get('busy')))
        pr = d.get('probe', {})
        print("  实测 MA200: %ss  via=%s  ok=%s"
              % (pr.get('poolElapsed'), pr.get('via'), pr.get('ok')))
        print("  新浪实时直连: %ss" % pr.get('sina实时'))

    block("【2】后端直连（这一段 = 纯计算，不含 Next / 公网）",
          BE + '/api/strategy/ma200-trend')

block("【3】经前端代理（浏览器实际请求的地址）",
      FE + '/api/strategy/ma200-trend')

print("\n【4】模拟连续切换：轮动 → MA200，两轮")
for i in range(2):
    t1 = one(FE + '/api/strategy/etf-rotation')[0]
    t2 = one(FE + '/api/strategy/ma200-trend')[0]
    print("  第%d轮: 轮动 %.0fms → MA200 %.0fms" % (i + 1, t1 * 1000, t2 * 1000))

block("【5】前端首页 HTML（Next 服务端渲染本身是否慢）", FE + '/', n=2)

print("\n" + "=" * 70)
print("怎么读结果：")
print("  · 【2】就慢            -> 后端/worker 池问题，看【1】里 alive 是否小于常驻数")
print("  · 【2】快、【3】慢     -> Next 转发或网络链路问题")
print("  · 【3】快、【4】慢     -> 切换时的并发/重复请求问题")
print("  · 【5】慢              -> Next 生产进程本身慢（构建产物/机器性能）")
print("=" * 70)
