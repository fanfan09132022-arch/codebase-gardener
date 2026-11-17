#!/usr/bin/env python3
"""判断一次改动的风险等级：green / yellow / red。

同时看两样东西：
1. 改了哪些文件（路径）。
2. 改动的内容里有没有碰钱、权限、删数据、密钥、对外发送的迹象（关键词）。

拿不准就往高判。关键词会误报，这是故意的：误报的代价是使用者多批一次，
漏报的代价是危险改动自动上线。

用法：
  python3 risk_scan.py --config .gardener/config.json --base origin/main
  python3 risk_scan.py --config .gardener/config.json --base origin/main --fail-on red

退出码：0 = 没超过 --fail-on 指定的等级；1 = 超过了；2 = 脚本自身出错（按红色处理）。
只用 Python 标准库，Python 3.8 及以上。
"""
import argparse
import fnmatch
import json
import re
import subprocess
import sys

ORDER = {"green": 0, "yellow": 1, "red": 2}

# 通用红色关键词。只在新增或删除的行里查。按类别分组，命中时报告类别，方便使用者看懂。
RED_KEYWORDS = {
    "碰钱": [
        r"\bpay(ment)?s?\b", r"\bprice", r"\bamount\b", r"\bbalance\b", r"\brefund",
        r"\bcharge", r"\binvoice", r"\bcheckout\b", r"\bwithdraw", r"\btransfer\b",
        r"\bwallet\b", r"\border(s)?\b", r"\btrade\b", r"\bstripe\b", r"\bpaypal\b",
        r"支付", r"金额", r"余额", r"退款", r"下单", r"转账", r"价格",
    ],
    "权限和登录": [
        r"\bauth", r"\bpermission", r"\brole(s)?\b", r"\bpassword", r"\bsession\b",
        r"\bjwt\b", r"\boauth", r"\blogin\b", r"\bis ?admin\b", r"\bsudo\b", r"\bacl\b",
        r"权限", r"登录", r"密码",
    ],
    "删除或迁移数据": [
        r"\bdelete\s+from\b", r"\bdrop\s+(table|column|database|index)\b", r"\btruncate\b",
        r"\balter\s+table\b", r"\brm\s+-rf?\b", r"\bunlink\(", r"\brmtree\(",
        r"\.delete\(", r"\.destroy\(", r"\bmigrat", r"\bdelete ?many\b",
    ],
    "密钥": [
        r"\bsecret", r"\bapi ?key", r"\bprivate ?key", r"\baccess ?token",
        r"BEGIN [A-Z ]*PRIVATE KEY", r"\bmnemonic\b", r"\bseed ?phrase",
    ],
    "对外发送": [
        r"\bsend ?e?mails?\b", r"\bmailer\b", r"\bsmtp", r"\bwebhook", r"\bsendgrid\b", r"\btwilio\b",
        r"\bpush ?notification", r"\bnotif(y|ication)", r"\btweet", r"\bpost ?message\b",
        r"发送", r"推送", r"发帖",
    ],
}


def run(cmd):
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("命令失败：%s\n%s" % (" ".join(cmd), out.stderr.strip()))
    return out.stdout


def match_any(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def parse_diff(diff_text):
    """返回 {文件路径: {"added": [行], "removed": [行]}}。"""
    files = {}
    current = None
    in_header = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current = None
            in_header = True
            continue
        if line.startswith("@@"):
            in_header = False
            continue
        if not in_header and current is None and (line.startswith("--- ") or line.startswith("+++ ")):
            in_header = True  # 没有 diff --git 行的普通 diff
        if in_header and (line.startswith("rename from ") or line.startswith("rename to ")):
            name = line.split(" ", 2)[2].strip()
            files.setdefault(name, {"added": [], "removed": []})
            continue
        if in_header and line.startswith("Binary files "):
            m = re.match(r"Binary files (?:a/)?(.+?) and (?:b/)?(.+?) differ", line)
            if m:
                for name in m.groups():
                    if name != "/dev/null":
                        files.setdefault(name, {"added": [], "removed": []})
            continue
        if in_header and line.startswith("+++ "):
            name = line[4:].strip()
            if name != "/dev/null":
                current = name[2:] if name.startswith("b/") else name
                files.setdefault(current, {"added": [], "removed": []})
            continue
        if in_header and line.startswith("--- "):
            name = line[4:].strip()
            if name != "/dev/null":
                old = name[2:] if name.startswith("a/") else name
                current = old
                files.setdefault(current, {"added": [], "removed": []})
            continue
        if in_header or current is None:
            continue
        if line.startswith("+"):
            files[current]["added"].append(line[1:])
        elif line.startswith("-"):
            files[current]["removed"].append(line[1:])
    return files


def normalize(line):
    """把 issueRefund、issue_refund、issue-refund 都拆成 issue refund，让单词边界在标识符里也能生效。"""
    line = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", line)
    return line.replace("_", " ").replace("-", " ")


def keyword_hits(lines, extra):
    lines = list(lines) + [normalize(l) for l in lines]
    hits = set()
    groups = dict(RED_KEYWORDS)
    if extra:
        groups = dict(groups)
        groups["项目自定关键词"] = [re.escape(k) for k in extra]
    for group, pats in groups.items():
        for pat in pats:
            rx = re.compile(pat, re.IGNORECASE)
            if any(rx.search(l) for l in lines):
                hits.add(group)
                break
    return sorted(hits)


def area_of(path, areas):
    for name, area in areas.items():
        if match_any(path, area.get("paths", [])):
            return name
    return None


def classify(files, cfg):
    protected = cfg.get("protected_paths", [])
    green_paths = cfg.get("green_paths", [])
    test_paths = cfg.get("test_paths", [])
    extra = cfg.get("red_keywords_extra", [])
    areas = cfg.get("areas", {})

    results = []
    for path, change in sorted(files.items()):
        reasons = []
        tier = "yellow"
        area = area_of(path, areas)
        is_test = match_any(path, test_paths)

        if match_any(path, protected):
            tier = "red"
            reasons.append("改的是关卡本身或数据结构（受保护路径）")
        elif area and areas[area].get("tier") == "red":
            tier = "red"
            reasons.append("所在区域「%s」被使用者定为红色" % area)

        hits = keyword_hits(change["added"] + change["removed"], extra)
        if hits and not is_test:
            tier = "red"
            reasons.append("改动内容疑似涉及：" + "、".join(hits))

        if is_test and change["removed"]:
            tier = "red"
            reasons.append("删除或修改了已有测试，等于放松关卡")

        if tier != "red":
            if is_test and not change["removed"]:
                tier = "green"
                reasons.append("只新增测试")
            elif match_any(path, green_paths):
                tier = "green"
                reasons.append("文档、样式或文案文件")
            else:
                reasons.append("一般功能代码")
            if area is None and tier != "green":
                reasons.append("不属于任何已登记区域，不能自动上线")
        results.append({"file": path, "area": area, "tier": tier, "reasons": reasons})

    overall = "green"
    for r in results:
        if ORDER[r["tier"]] > ORDER[overall]:
            overall = r["tier"]
    if not results:
        overall = "green"
    touched_areas = sorted({r["area"] for r in results if r["area"]})
    unregistered = any(r["area"] is None and r["tier"] != "green" for r in results)
    return {
        "overall": overall,
        "areas": touched_areas,
        "has_unregistered_files": unregistered,
        "files": results,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=".gardener/config.json")
    ap.add_argument("--base", default="origin/main", help="和哪个版本比，默认 origin/main")
    ap.add_argument("--diff-file", help="直接读一个 diff 文件，不调用 git（用于测试）")
    ap.add_argument("--fail-on", choices=["yellow", "red"], help="等级达到这一级就返回 1")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    args = ap.parse_args()

    try:
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
        if args.diff_file:
            with open(args.diff_file, encoding="utf-8") as f:
                diff_text = f.read()
        else:
            diff_text = run(["git", "diff", "--no-color", "-U0", "%s...HEAD" % args.base])
        report = classify(parse_diff(diff_text), cfg)
    except Exception as e:  # 出错按红色处理，不能因为脚本坏了就放行
        print("风险判断脚本出错，按红色处理：%s" % e, file=sys.stderr)
        print(json.dumps({"overall": "red", "error": str(e)}, ensure_ascii=False))
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        label = {"green": "🟢 低风险", "yellow": "🟡 中风险", "red": "🔴 必须由使用者批准"}
        print("总体等级：%s" % label[report["overall"]])
        if report["areas"]:
            print("涉及区域：%s" % "、".join(report["areas"]))
        for r in report["files"]:
            print("  %s %s：%s" % (label[r["tier"]][:1], r["file"], "；".join(r["reasons"])))
        print("JSON:" + json.dumps(report, ensure_ascii=False))

    if args.fail_on and ORDER[report["overall"]] >= ORDER[args.fail_on]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
