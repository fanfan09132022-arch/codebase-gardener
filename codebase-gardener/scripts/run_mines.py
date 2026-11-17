#!/usr/bin/env python3
"""埋雷测试：把已知的错误逐个放进临时副本，看关卡能不能拦下。

雷登记在 docs/mines/mines.json，每个雷是一个补丁文件：
  [{"id": "m1", "area": "下单", "core": true, "source": "history",
    "patch": "docs/mines/m1.patch", "description": "运费算成负数"}]

source 只能是下面几种，用来分散「同一个 AI 设计雷又写检查」的盲区：
  mutation  变异测试工具自动生成
  history   从历史 bug 的修复提交反推出来（见 harvest 子命令）
  user      使用者用大白话描述「最怕坏成什么样」，再做成补丁
  ai        AI 设计。设计雷的会话不能是写这些检查的会话

用法：
  python3 run_mines.py run --config .gardener/config.json
  python3 run_mines.py harvest --commit <修 bug 的提交> --id m7 --area 下单 --description "..."

run 的步骤：
  1. 在临时目录里检出当前版本，先跑一遍关卡。不通过就停：验证方法本身有问题，结果不可信。
  2. 每个雷：放进一个全新的临时副本，跑关卡。关卡失败 = 拦下。
  3. 补丁放不进去的雷记为「失效」，不算拦下，必须修好或由使用者批准退役。
  4. 结果写入 .gardener/mine-results/<日期>.json，供 release_gate.py 读取。

退出码：0 = 所有核心雷都被拦下；1 = 有核心雷没拦下或失效；2 = 干净版本本身没通过关卡，或脚本出错。
只用 Python 标准库，Python 3.8 及以上。
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile

VALID_SOURCES = {"mutation", "history", "user", "ai"}
DEFAULT_TEST_EXCLUDES = [
    ":(exclude)tests/**", ":(exclude)test/**", ":(exclude)**/*_test.*",
    ":(exclude)**/*.test.*", ":(exclude)**/*.spec.*", ":(exclude)**/test_*",
]


def sh(cmd, cwd=None, check=True, timeout=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError("命令失败：%s\n%s" % (" ".join(cmd), p.stderr.strip()))
    return p


def repo_root():
    return sh(["git", "rev-parse", "--show-toplevel"]).stdout.strip()


class Worktree:
    """在系统临时目录里建一个独立副本，用完删掉，不碰使用者的工作目录。"""

    def __init__(self, root):
        self.root = root
        self.path = tempfile.mkdtemp(prefix="gardener-mine-")
        os.rmdir(self.path)

    def __enter__(self):
        sh(["git", "worktree", "add", "--detach", self.path, "HEAD"], cwd=self.root)
        return self.path

    def __exit__(self, *exc):
        sh(["git", "worktree", "remove", "--force", self.path], cwd=self.root, check=False)
        shutil.rmtree(self.path, ignore_errors=True)


def run_gate(cmd, cwd, timeout):
    try:
        p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout)
        tail = (p.stdout + p.stderr).strip().splitlines()[-5:]
        return p.returncode, "\n".join(tail)
    except subprocess.TimeoutExpired:
        return 124, "关卡超时"


def load_mines(root, path):
    full = os.path.join(root, path)
    with open(full, encoding="utf-8") as f:
        mines = json.load(f)
    errors = []
    ids = set()
    for m in mines:
        for k in ("id", "area", "core", "source", "patch", "description"):
            if k not in m:
                errors.append("雷 %s 缺少字段 %s" % (m.get("id", "?"), k))
        if m.get("source") not in VALID_SOURCES:
            errors.append("雷 %s 的 source 必须是 %s 之一" % (m.get("id"), "、".join(sorted(VALID_SOURCES))))
        if m.get("id") in ids:
            errors.append("雷 id 重复：%s" % m.get("id"))
        ids.add(m.get("id"))
    if errors:
        raise ValueError("\n".join(errors))
    return mines


def cmd_run(args):
    root = repo_root()
    with open(os.path.join(root, args.config), encoding="utf-8") as f:
        cfg = json.load(f)
    gate = args.gate or cfg.get("gate_command")
    if not gate:
        print("配置里没有 gate_command，无法判断雷有没有被拦下。", file=sys.stderr)
        return 2
    mines = load_mines(root, args.mines)
    head = sh(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()

    print("第 1 步：先确认干净版本能通过关卡……")
    with Worktree(root) as wt:
        code, tail = run_gate(gate, wt, args.timeout)
    if code != 0:
        print("干净版本没有通过关卡（退出码 %d）。先修好关卡或测试，再埋雷。\n%s" % (code, tail))
        return 2
    print("  通过。")

    results = []
    for m in mines:
        patch = os.path.join(root, m["patch"])
        with Worktree(root) as wt:
            ap = sh(["git", "apply", "--whitespace=nowarn", patch], cwd=wt, check=False)
            if ap.returncode != 0:
                status, detail = "stale", "补丁放不进去，代码已经变了：" + ap.stderr.strip()[:200]
            else:
                code, tail = run_gate(gate, wt, args.timeout)
                status = "blocked" if code != 0 else "missed"
                detail = tail
        results.append(dict(m, status=status, detail=detail))
        mark = {"blocked": "✅ 拦下", "missed": "❌ 漏过", "stale": "⚠️ 失效"}[status]
        print("  %s  [%s] %s：%s" % (mark, m["area"], m["id"], m["description"]))

    today = dt.date.today().isoformat()
    out_dir = os.path.join(root, ".gardener", "mine-results")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "%s.json" % today)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"date": today, "commit": head, "gate_command": gate, "results": results},
                  f, ensure_ascii=False, indent=2)

    core = [r for r in results if r["core"]]
    bad = [r for r in core if r["status"] != "blocked"]
    print("\n一共 %d 个雷，拦下 %d 个，漏过 %d 个，失效 %d 个。" % (
        len(results), sum(r["status"] == "blocked" for r in results),
        sum(r["status"] == "missed" for r in results), sum(r["status"] == "stale" for r in results)))
    print("核心功能的雷：%d 个，没拦下或失效 %d 个。" % (len(core), len(bad)))
    print("结果已写入 %s" % os.path.relpath(out, root))
    return 1 if bad else 0


def cmd_harvest(args):
    """把一次修 bug 的提交反过来，得到「bug 回来了」的补丁。测试文件不反转，因为要看现有测试能不能拦住。"""
    root = repo_root()
    excludes = DEFAULT_TEST_EXCLUDES + ["%s" % e for e in (args.exclude or [])]
    diff = sh(["git", "diff", "--no-color", args.commit, args.commit + "^", "--", "."] + excludes, cwd=root).stdout
    if not diff.strip():
        print("这个提交除了测试以外没有改动，做不成雷。", file=sys.stderr)
        return 2
    mines_path = os.path.join(root, args.mines)
    mines = []
    if os.path.exists(mines_path):
        with open(mines_path, encoding="utf-8") as f:
            mines = json.load(f)
    # 先查重再写补丁：否则重复的 id 会覆盖已有雷的补丁文件。
    if any(m["id"] == args.id for m in mines):
        print("雷 id 已存在：%s" % args.id, file=sys.stderr)
        return 2
    rel = os.path.join(os.path.dirname(args.mines), "%s.patch" % args.id)
    os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
    with open(os.path.join(root, rel), "w", encoding="utf-8") as f:
        f.write(diff)
    mines.append({"id": args.id, "area": args.area, "core": not args.not_core, "source": "history",
                  "patch": rel, "description": args.description, "from_commit": args.commit})
    with open(mines_path, "w", encoding="utf-8") as f:
        json.dump(mines, f, ensure_ascii=False, indent=2)
    print("已生成雷 %s：%s" % (args.id, rel))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=".gardener/config.json")
    ap.add_argument("--mines", default="docs/mines/mines.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--gate", help="覆盖配置里的 gate_command")
    r.add_argument("--timeout", type=int, default=1800, help="每次跑关卡的超时秒数")
    h = sub.add_parser("harvest")
    h.add_argument("--commit", required=True)
    h.add_argument("--id", required=True)
    h.add_argument("--area", required=True)
    h.add_argument("--description", required=True)
    h.add_argument("--not-core", action="store_true")
    h.add_argument("--exclude", action="append", help="额外不反转的路径，git pathspec 写法")
    args = ap.parse_args()
    try:
        return cmd_run(args) if args.cmd == "run" else cmd_harvest(args)
    except Exception as e:
        print("埋雷脚本出错：%s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
