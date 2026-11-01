#!/usr/bin/env python3
"""find-stale.py の報告をもとに、陳腐化した文書を削除して再作成候補に戻す (Stage 2 の後片付け)。

- 本文を git rm する
- envvars は試行記録 (.create-envvars-docs.state.json) から entry を消して「未調査」に戻す
- 削除理由 (.strata-stale.removed.json) を残す
- 索引の名前は消さない（索引更新で消えるべきものが索引更新手順の仕事）

既定は dry-run。--apply で実行する。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
from datetime import datetime

from staleness_lib import CLI_DIR, StrataTree, default_strata_root, git_ok

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
DEFAULT_VERDICTS = ("token-in-diff", "option-absent-in-grammar", "symbol-gone")
STATE = REPO_ROOT / ".create-envvars-docs.state.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="陳腐化文書を削除し、未調査に戻します。")
    parser.add_argument("--repo", type=pathlib.Path, default=REPO_ROOT)
    parser.add_argument("--strata", type=pathlib.Path, default=default_strata_root())
    parser.add_argument("--report", type=pathlib.Path, default=REPO_ROOT / ".strata-stale.json")
    parser.add_argument("--removed-log", type=pathlib.Path, default=REPO_ROOT / ".strata-stale.removed.json")
    parser.add_argument(
        "--verdict",
        action="append",
        choices=["token-in-diff", "option-absent-in-grammar", "symbol-gone", "name-gone", "cited-file-gone", "unknown-sha"],
        help="削除対象の判定 (既定: token-in-diff, option-absent-in-grammar, symbol-gone)",
    )
    parser.add_argument(
        "--exclude-token",
        action="append",
        default=[],
        metavar="OPTION",
        help="この option 文字列の文書を対象外にする (繰り返し指定可)。既定の除外リストは持たないので、"
        " CLI を回すときは --exclude-token=--help を毎回付ける (usage 文言変更が主な群)。",
    )
    parser.add_argument("--limit", type=int, default=40, metavar="N", help="今回削除する上限 (安全弁)")
    parser.add_argument("--scope", choices=["all", "envvars", "cli"], default="all")
    parser.add_argument("--apply", action="store_true", help="実際に削除する (既定は dry-run)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    strata = args.strata.resolve()
    if not args.report.is_file():
        print(f"報告が見つかりません: {args.report} (find-stale.py を先に実行)")
        return 2

    report = json.loads(args.report.read_text(encoding="utf-8"))
    revision = str(report.get("revision", ""))
    if not revision or not git_ok(strata, "cat-file", "-e", f"{revision}^{{commit}}"):
        print(f"報告の revision が Strata に実在しません: {revision}")
        return 2
    tree = StrataTree(strata, revision)

    verdicts = set(args.verdict or DEFAULT_VERDICTS)
    excluded = set(args.exclude_token)
    all_candidates = [
        item
        for item in report.get("candidates", [])
        if item.get("verdict") in verdicts and (args.scope == "all" or item.get("scope") == args.scope)
    ]
    if excluded:
        dropped = [item for item in all_candidates if item.get("token") in excluded]
        print(f"除外 (--exclude-token): {len(dropped)} 件")
        tally = {}
        for item in dropped:
            tally[item.get("token")] = tally.get(item.get("token"), 0) + 1
        for token, count in sorted(tally.items(), key=lambda kv: -kv[1]):
            print(f"  {token:22} {count}")
    candidates = [item for item in all_candidates if item.get("token") not in excluded]
    if len(candidates) > args.limit:
        print(f"候補 {len(candidates)} 件のうち上限 {args.limit} 件だけを処理します")
        candidates = candidates[: args.limit]
    if not candidates:
        print("削除対象はありません。")
        return 0

    state_path = repo / ".create-envvars-docs.state.json"
    state = {}
    if state_path.is_file():
        try:
            loaded = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state = {k: v for k, v in loaded.items() if isinstance(v, dict)}
        except (json.JSONDecodeError, OSError):
            state = {}

    removed_log_path = repo / args.removed_log
    removed_log = []
    if removed_log_path.is_file():
        try:
            loaded = json.loads(removed_log_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                removed_log = loaded
        except (json.JSONDecodeError, OSError):
            removed_log = []

    print(("削除" if args.apply else "dry-run: 削除予定") + f" {len(candidates)} 件")
    for item in candidates:
        rel = str(item["file"])
        path = repo / rel
        if not path.is_file():
            print(f"  スキップ (本文なし): {rel}")
            continue
        coords = [c[0] for c in item.get("coords", [])]
        commits = list(item.get("changed_commits") or [])
        if not commits and coords:
            commits = tree.commits_touching(str(item["doc_sha"]), sorted(set(coords))[:12])
        print(f"  [{item['verdict']}] {rel}  doc_sha={str(item['doc_sha'])[:7]}  触れたコミット {len(commits)} 件")

        if not args.apply:
            continue

        subprocess.run(
            ("git", "-C", str(repo), "rm", "-q", "--", rel),
            check=True,
            capture_output=True,
            text=True,
        )
        if item.get("scope") == "envvars":
            state.pop(str(item["key"]), None)
        else:
            parent = path.parent
            while parent.relative_to(repo).as_posix().startswith(f"{CLI_DIR}/") and parent.is_dir():
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent

        removed_log.append(
            {
                "removed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "scope": item.get("scope"),
                "key": item.get("key"),
                "file": rel,
                "verdict": item.get("verdict"),
                "token": item.get("token"),
                "doc_sha": item.get("doc_sha"),
                "doc_date": item.get("doc_date"),
                "cited_files": sorted(set(coords)),
                "changed_commits": commits[:12],
                "token_lines": item.get("token_lines", [])[:4],
                "symbols_missing": item.get("symbols_missing", [])[:8],
                "grammar_hits": item.get("grammar_hits"),
            }
        )

    if not args.apply:
        print("\n--apply を付けると実際に削除します。")
        return 0

    if state_path.is_file() or any(item.get("scope") == "envvars" for item in candidates):
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    removed_log_path.write_text(json.dumps(removed_log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"\n削除完了: {len(candidates)} 件 / 試行記録: {state_path}")
    print(f"削除理由: {removed_log_path}")
    print("次: uv run ./create-envvars-docs.py --dry-run -l <件数> → 実行 → check-docs.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
