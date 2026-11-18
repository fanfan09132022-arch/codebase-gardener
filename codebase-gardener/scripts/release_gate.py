#!/usr/bin/env python3
"""放权闸门：按实测结果决定一个区域的改动能不能不经使用者就自动上线。

依据三件事，对应「上线损失 ≈ 出错概率 × 影响范围 × 发现和恢复的时间」：
  出错概率   变更失败率的 95% 置信上界（Wilson 区间），样本少时上界高，自然不放权
  恢复时间   出事后从上线到恢复的中位时间
  可承受范围 错误预算：区域按 SLO 允许的「坏掉的分钟数」，用完就停止自动上线
另外检查：五项前提都有证据，且证据没过期；最近一次埋雷测试里这个区域的核心雷全部拦下；
没有未解除的暂停。

上线账本是 .gardener/deploys.jsonl，每行一次上线。由流水线调用 record 追加，不手改。

用法：
  python3 release_gate.py check  --area 下单 --tier yellow
  python3 release_gate.py record --area 下单 --version v42 --result ok
  python3 release_gate.py record --area 下单 --version v43 --result rolled_back --bad-minutes 12 --detected-by 健康检查
  python3 release_gate.py resume --area 下单 --note "补了运费验证，埋雷 2026-11-20 全拦下" --approved-by 使用者
  python3 release_gate.py report
  python3 release_gate.py import-history --from prod/history.jsonl --area 研判 \
      --time-key ts --version-key to --kind-key reason --release-value release --rollback-value rollback --rolled-back-key from

import-history 把项目已有的发版记录换算成上线账本，适合本机发版、早就留着记录的项目，
不用从 0 次开始攒。只能导入空账本。记录里每次「退回」都把被退掉的那一版记为 rolled_back，
坏掉的分钟数 = 退回时间 − 那一版的上线时间。
它看不出「发出去以后又发了一版来修」的情况，这类返工要另外按提交信息估一个上限，汇报时两个数一起给。

check 的退出码：0 = 可以自动上线；1 = 不行，要使用者批准；2 = 脚本出错（按不行处理）。
只用 Python 标准库，Python 3.8 及以上。
"""
import argparse
import datetime as dt
import glob
import json
import math
import os
import subprocess
import sys

RESULTS = {"ok", "rolled_back", "hotfix", "incident"}
FAILED = {"rolled_back", "hotfix", "incident"}
PREREQS = ["结构", "强制关卡", "自动验证", "能退回", "标准答案"]


def now():
    return dt.datetime.now(dt.timezone.utc)


def parse_time(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def wilson_upper(fails, n, z):
    """失败率的 Wilson 置信区间上界。n=0 时返回 1，表示什么都不知道。"""
    if n == 0:
        return 1.0
    p = fails / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, (centre + margin) / denom)


def load_ledger(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                raise ValueError("上线账本第 %d 行不是合法 JSON，账本可能被手改过" % i)
    return rows


def git_last_change_days(path):
    """证据文件最后一次提交距今几天。用 git 记录而不是文件时间，因为 CI 检出会刷新文件时间。"""
    p = subprocess.run(["git", "log", "-1", "--format=%cI", "--", path], capture_output=True, text=True)
    if p.returncode != 0 or not p.stdout.strip():
        return None
    return (now() - parse_time(p.stdout.strip())).days


def latest_mine_result(results_dir):
    files = sorted(glob.glob(os.path.join(results_dir, "*.json")))
    if not files:
        return None
    with open(files[-1], encoding="utf-8") as f:
        return json.load(f)


def area_stats(rows, area, window_days):
    since = now() - dt.timedelta(days=window_days)
    deploys = [r for r in rows if r.get("type") == "deploy" and r.get("area") == area
               and parse_time(r["time"]) >= since]
    fails = [r for r in deploys if r["result"] in FAILED]
    recov = sorted(r.get("bad_minutes", 0) for r in fails)
    median = None
    if recov:
        mid = len(recov) // 2
        median = recov[mid] if len(recov) % 2 else (recov[mid - 1] + recov[mid]) / 2
    bad_minutes = sum(r.get("bad_minutes", 0) for r in fails)
    return {"deploys": len(deploys), "fails": len(fails), "median_recovery": median, "bad_minutes": bad_minutes}


def paused(rows, area):
    """最近一次失败之后，有没有使用者批准的恢复记录。账本只追加，所以按行的先后判断，不按时间戳。"""
    state = None
    for r in rows:
        if r.get("area") != area:
            continue
        if r.get("type") == "deploy" and r.get("result") in FAILED:
            state = r
        elif r.get("type") == "resume":
            state = None
    return state


def check(cfg, rows, area_name, tier, mine_dir):
    th = cfg["thresholds"]
    reasons_no = []
    reasons_ok = []
    area = cfg.get("areas", {}).get(area_name)
    if area is None:
        return False, ["区域「%s」没有在配置里登记" % area_name], []

    # 区域定为红色时，区域里的任何改动都按红色处理；否则按 risk_scan.py 判出的改动等级。
    if area.get("tier") == "red" or tier == "red":
        reasons_no.append("红色改动永远要使用者批准")
    elif tier == "yellow" and not area.get("allow_yellow_auto"):
        reasons_no.append("这个区域还没被使用者允许中风险改动自动上线")

    for name in PREREQS:
        item = area.get("readiness", {}).get(name, {})
        if item.get("status") != "ok":
            reasons_no.append("前提「%s」没有达标" % name)
            continue
        ev = item.get("evidence", "")
        if not ev or not os.path.exists(ev):
            reasons_no.append("前提「%s」标了达标，但证据文件不存在：%s" % (name, ev or "空"))
            continue
        age = git_last_change_days(ev)
        if age is None:
            reasons_no.append("前提「%s」的证据文件没有提交记录：%s" % (name, ev))
        elif age > th["max_evidence_age_days"]:
            reasons_no.append("前提「%s」的证据已经 %d 天没更新，超过 %d 天" % (name, age, th["max_evidence_age_days"]))

    mines = latest_mine_result(mine_dir)
    if mines is None:
        reasons_no.append("还没有做过埋雷测试")
    else:
        age = (dt.date.today() - dt.date.fromisoformat(mines["date"])).days
        core = [m for m in mines["results"] if m["area"] == area_name and m["core"]]
        if age > th["max_mine_age_days"]:
            reasons_no.append("最近一次埋雷是 %d 天前，超过 %d 天" % (age, th["max_mine_age_days"]))
        if not core:
            reasons_no.append("这个区域没有核心功能雷")
        else:
            bad = [m["id"] for m in core if m["status"] != "blocked"]
            if bad:
                reasons_no.append("核心雷没拦下或已失效：%s" % "、".join(bad))
            sources = {m["source"] for m in core}
            if len(sources) < th["min_mine_sources"]:
                reasons_no.append("核心雷只来自 %d 种来源（%s），至少要 %d 种" % (
                    len(sources), "、".join(sorted(sources)), th["min_mine_sources"]))
            if not bad:
                reasons_ok.append("埋雷：%d 个核心雷全部拦下" % len(core))

    p = paused(rows, area_name)
    if p:
        reasons_no.append("区域处于暂停：%s 上线的 %s 出了问题，还没有使用者批准的恢复记录" % (p["time"][:10], p.get("version", "?")))

    st = area_stats(rows, area_name, th["window_days"])
    upper = wilson_upper(st["fails"], st["deploys"], th["confidence_z"])
    if upper > th["max_change_fail_rate"]:
        reasons_no.append("近 %d 天 %d 次上线、%d 次出事，失败率上界 %.1f%%，高于 %.1f%%。样本不够时，要先由使用者批准着上线攒记录" % (
            th["window_days"], st["deploys"], st["fails"], upper * 100, th["max_change_fail_rate"] * 100))
    else:
        reasons_ok.append("失败率上界 %.1f%%（%d 次上线）" % (upper * 100, st["deploys"]))
    if st["median_recovery"] is not None and st["median_recovery"] > th["max_median_recovery_minutes"]:
        reasons_no.append("出事后恢复的中位时间 %s 分钟，超过 %d 分钟" % (st["median_recovery"], th["max_median_recovery_minutes"]))

    slo = area.get("slo", {}).get("target")
    if slo is None:
        reasons_no.append("区域没有设定 SLO，算不出错误预算")
    else:
        budget = (1 - slo) * th["window_days"] * 24 * 60
        used = st["bad_minutes"] / budget if budget > 0 else 1.0
        if used >= 1:
            reasons_no.append("错误预算已用完：坏了 %d 分钟，预算 %.0f 分钟" % (st["bad_minutes"], budget))
        else:
            reasons_ok.append("错误预算用了 %.0f%%" % (used * 100))

    return not reasons_no, reasons_no, reasons_ok


def cmd_check(args, cfg):
    rows = load_ledger(args.ledger)
    ok, no, yes = check(cfg, rows, args.area, args.tier, args.mine_results)
    print("区域「%s」，%s 改动：%s" % (args.area, args.tier, "✅ 可以自动上线" if ok else "⛔ 需要使用者批准"))
    for r in no:
        print("  ⛔ " + r)
    for r in yes:
        print("  ✅ " + r)
    return 0 if ok else 1


def append(path, row):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def cmd_record(args, cfg):
    if args.result not in RESULTS:
        print("result 只能是：%s" % "、".join(sorted(RESULTS)), file=sys.stderr)
        return 2
    if args.result in FAILED and args.bad_minutes is None:
        print("出事的记录必须写 --bad-minutes：从上线到恢复一共坏了多少分钟", file=sys.stderr)
        return 2
    row = {"type": "deploy", "time": now().isoformat(timespec="seconds"), "area": args.area,
           "version": args.version, "result": args.result, "tier": args.tier,
           "auto": args.auto, "bad_minutes": args.bad_minutes or 0, "detected_by": args.detected_by}
    append(args.ledger, row)
    print("已记账：%s %s %s" % (args.area, args.version, args.result))
    if args.result in FAILED:
        print("这个区域已自动暂停自动上线。请在 docs/漏网记录.md 记一笔，补好关卡、重跑埋雷后，由使用者批准 resume。")
    return 0


def cmd_resume(args, cfg):
    append(args.ledger, {"type": "resume", "time": now().isoformat(timespec="seconds"),
                         "area": args.area, "note": args.note, "approved_by": args.approved_by})
    print("已记录恢复：%s。账本属于受保护文件，这次改动必须由使用者批准合并才生效。" % args.area)
    return 0


def short_version(v):
    return os.path.basename(str(v).rstrip("/"))


def cmd_import_history(args, cfg):
    if load_ledger(args.ledger):
        print("上线账本已经有记录，import-history 只能导入空账本，避免重复记账。", file=sys.stderr)
        return 2
    src = []
    with open(args.source, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if line.strip():
                try:
                    src.append(json.loads(line))
                except json.JSONDecodeError:
                    raise ValueError("发版记录第 %d 行不是合法 JSON" % i)
    deploys = []
    unmatched = 0
    for r in src:
        kind = r.get(args.kind_key)
        if kind == args.release_value:
            deploys.append({"type": "deploy", "time": parse_time(r[args.time_key]).isoformat(timespec="seconds"),
                            "area": args.area, "version": short_version(r[args.version_key]), "result": "ok",
                            "tier": "", "auto": False, "bad_minutes": 0, "detected_by": "",
                            "imported_from": args.source})
        elif kind == args.rollback_value:
            bad = short_version(r.get(args.rolled_back_key, ""))
            hit = next((d for d in reversed(deploys) if d["version"] == bad and d["result"] == "ok"), None)
            if hit is None:
                unmatched += 1
                continue
            hit["result"] = "rolled_back"
            hit["detected_by"] = "退回记录"
            hit["bad_minutes"] = round((parse_time(r[args.time_key]) - parse_time(hit["time"])).total_seconds() / 60, 1)
    for d in deploys:
        append(args.ledger, d)
    fails = sum(d["result"] == "rolled_back" for d in deploys)
    print("已导入 %d 次上线，其中 %d 次被退回。" % (len(deploys), fails))
    if unmatched:
        print("有 %d 条退回记录找不到对应的上线，没有计入。请人工核对。" % unmatched)
    return 0


def cmd_report(args, cfg):
    rows = load_ledger(args.ledger)
    th = cfg["thresholds"]
    print("近 %d 天上线情况（按区域）" % th["window_days"])
    print("| 区域 | 上线次数 | 出事次数 | 失败率上界 | 恢复中位分钟 | 错误预算已用 | 暂停 |")
    print("|---|---|---|---|---|---|---|")
    for name, area in cfg.get("areas", {}).items():
        st = area_stats(rows, name, th["window_days"])
        upper = wilson_upper(st["fails"], st["deploys"], th["confidence_z"])
        slo = area.get("slo", {}).get("target")
        if slo:
            budget = (1 - slo) * th["window_days"] * 24 * 60
            used = "%.0f%%" % (100 * st["bad_minutes"] / budget)
        else:
            used = "未设 SLO"
        med = "-" if st["median_recovery"] is None else str(st["median_recovery"])
        print("| %s | %d | %d | %.1f%% | %s | %s | %s |" % (
            name, st["deploys"], st["fails"], upper * 100, med, used, "是" if paused(rows, name) else "否"))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=".gardener/config.json")
    ap.add_argument("--ledger", default=".gardener/deploys.jsonl")
    ap.add_argument("--mine-results", default=".gardener/mine-results")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--area", required=True)
    c.add_argument("--tier", required=True, choices=["green", "yellow", "red"])
    r = sub.add_parser("record")
    r.add_argument("--area", required=True)
    r.add_argument("--version", required=True)
    r.add_argument("--result", required=True)
    r.add_argument("--tier", default="")
    r.add_argument("--auto", action="store_true", help="这次是自动上线")
    r.add_argument("--bad-minutes", type=float)
    r.add_argument("--detected-by", default="")
    s = sub.add_parser("resume")
    s.add_argument("--area", required=True)
    s.add_argument("--note", required=True)
    s.add_argument("--approved-by", required=True)
    sub.add_parser("report")
    h = sub.add_parser("import-history")
    h.add_argument("--from", dest="source", required=True, help="已有的发版记录，JSON Lines")
    h.add_argument("--area", required=True)
    h.add_argument("--time-key", default="time")
    h.add_argument("--version-key", default="version")
    h.add_argument("--kind-key", default="reason")
    h.add_argument("--release-value", default="release")
    h.add_argument("--rollback-value", default="rollback")
    h.add_argument("--rolled-back-key", default="from", help="退回记录里「被退掉的版本」字段")
    args = ap.parse_args()
    try:
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
        return {"check": cmd_check, "record": cmd_record, "resume": cmd_resume, "report": cmd_report,
                "import-history": cmd_import_history}[args.cmd](args, cfg)
    except Exception as e:
        print("放权闸门出错，按「不放行」处理：%s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
