#!/usr/bin/env python3
"""上线后健康检查：按清单访问几个关键地址，检查状态码和页面里该有的字，任何一条不对就失败。

清单是 JSON，例如 .gardener/health.json：
  [{"name": "首页能打开", "url": "https://example.com/", "status": 200, "contains": "欢迎"},
   {"name": "下单接口活着", "url": "https://example.com/api/health", "status": 200}]

用法：
  python3 health_check.py --checks .gardener/health.json --base-url https://canary.example.com --retries 3

--base-url 用来把同一份清单对着金丝雀或正式环境跑：清单里的 url 写成以 / 开头的路径即可。
退出码：0 = 全部正常；1 = 有不正常的。只用 Python 标准库。

这只是最低限度的检查。能接入真正的监控（错误率、延迟）时，金丝雀要和旧版本对比这些指标，
见 reference/release-pipeline.md 的「金丝雀自动判断」。
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def probe(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "gardener-health-check"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(200000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return None, str(e)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checks", default=".gardener/health.json")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--retries", type=int, default=3, help="刚上线时服务可能还在启动，每条最多试几次")
    ap.add_argument("--wait", type=float, default=10, help="两次重试之间等几秒")
    args = ap.parse_args()

    with open(args.checks, encoding="utf-8") as f:
        checks = json.load(f)
    if not checks:
        print("健康检查清单是空的，按失败处理。")
        return 1

    failed = 0
    for c in checks:
        url = c["url"]
        if url.startswith("/"):
            url = args.base_url.rstrip("/") + url
        want = c.get("status", 200)
        ok = False
        detail = ""
        for attempt in range(args.retries):
            status, body = probe(url, args.timeout)
            ok = status == want and (not c.get("contains") or c["contains"] in body)
            detail = "状态码 %s" % status if status is not None else "连不上：%s" % body[:100]
            if ok:
                break
            if attempt + 1 < args.retries:
                time.sleep(args.wait)
        print("%s %s（%s）" % ("✅" if ok else "❌", c["name"], detail))
        failed += 0 if ok else 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
