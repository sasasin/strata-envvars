#!/usr/bin/env python3
"""索引と実ファイルの突合で、docs/envvars と docs/cli の追従状況を確認する。

envvars 側: 未作成・孤児・索引と綴りの違うファイル名・索引の重複と並び順・本文の必須節・commit SHA と調査日。
cli 側: 予定リンク（未作成）・孤児・索引に無い tool-id・コマンド節の概要リンク・option の並び順・commit SHA と調査日。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


DEFAULT_REPO = Path(__file__).resolve().parents[4]

ENVVAR_DIR = "docs/envvars"
ENVVAR_INDEX = "000_envvers.md"
ENVVAR_EXCLUDE = {"001_investigation.md", "STRATA_ADAPT_OVERLAP.md"}
ENVVAR_ENTRY_RE = re.compile(r"^- `([A-Za-z0-9_]+)`\s*$")
ENVVAR_REQUIRED_SECTIONS = ["## 役割", "## 値と判定", "## 有効になる条件", "## 実行時の詳細"]
ENVVAR_EVIDENCE_HEADING_RE = re.compile(r"^## .*(根拠|参照|出典)", re.MULTILINE)
SOURCE_LINE_RE = re.compile(r"[\w./+-]+\.(?:c|cc|cpp|cppm|h|hpp|cu|cuh|hip|py|rs|js|mjs|ts|sh|bash|bat|cmd|ps1|cmake|json|toml|yml|yaml|nsi|md)(?::\d+)")

CLI_DIR = "docs/cli"
CLI_INDEX = "README.md"
CLI_INDEX_LINK_RE = re.compile(r"^- \[(.*?)\]\(([^)]+)\)\s*$")
SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
OPTION_NAME_RE = re.compile(r"`([^`]+)`")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="docs/envvars と docs/cli の索引・実ファイルを突合します。",
    )
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO, help="strata-envvars の root")
    parser.add_argument(
        "--scope",
        choices=["all", "envvars", "cli"],
        default="all",
        help="点検対象 (default: all)",
    )
    parser.add_argument(
        "--target",
        metavar="SHA",
        help="--stale の基準 commit SHA (既定は索引に書かれた SHA)",
    )
    parser.add_argument("--stale", action="store_true", help="基準 SHA 以外で書かれた文書を並べる")
    parser.add_argument("--list-missing", action="store_true", help="未作成の文書パスを一覧する")
    parser.add_argument("--json", action="store_true", help="機械可読な JSON で出す")
    parser.add_argument("--strict", action="store_true", help="問題があれば終了コード 1")
    return parser.parse_args()


def read_index_sha(index_path: Path) -> str:
    """索引の先頭付近に書かれた Strata の commit SHA。"""
    if not index_path.is_file():
        return ""
    for line in index_path.read_text(encoding="utf-8").splitlines()[:15]:
        if line.startswith("調査対象:"):
            match = SHA_RE.search(line)
            if match:
                return match.group(0)
    return ""


def doc_meta(path: Path) -> tuple[str, str, bool]:
    """文書から調査対象行の commit SHA と調査日を取り出す。

    戻り値は (sha, date, 調査対象行が見つかったか)。SHA と調査日は
    「調査対象: ...」行にのみ求める（本文中の日付を根拠にしない）。
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines()[:12]:
        if line.startswith("調査対象:"):
            sha = SHA_RE.search(line)
            date = DATE_RE.search(line)
            return (
                sha.group(0) if sha else "",
                date.group(0) if date else "",
                True,
            )
    return ("", "", False)


def check_envvars(repo: Path, target_sha: str) -> dict[str, object]:
    """docs/envvars の索引と本文を突合する。"""
    doc_root = repo / ENVVAR_DIR
    index_path = doc_root / ENVVAR_INDEX
    report: dict[str, object] = {"index_sha": target_sha, "problems": []}
    if not index_path.is_file():
        report["problems"].append(f"索引が見つかりません: {index_path}")
        return report

    names: list[str] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        match = ENVVAR_ENTRY_RE.match(line)
        if not match:
            continue
        name = match.group(1)
        if name in seen:
            duplicates.append(name)
        seen.add(name)
        names.append(name)

    if duplicates:
        report["problems"].append(f"索引の重複項目 {len(duplicates)} 件: {duplicates[:10]}")

    out_of_order = [
        f"{i}: {name} (あるべき: {sorted_name})"
        for i, (name, sorted_name) in enumerate(zip(names, sorted(names)))
        if name != sorted_name
    ]
    report["index_count"] = len(names)
    report["index_order_violations"] = out_of_order
    if out_of_order:
        report["problems"].append(f"索引が ASCII 順に並んでいない位置 {len(out_of_order)} 件")

    files = [
        path
        for path in sorted(doc_root.glob("*.md"))
        if path.name not in ENVVAR_EXCLUDE and not path.name.startswith("000_")
    ]
    stems = {path.stem: path for path in files}
    missing = [name for name in names if (doc_root / f"{name}.md").is_file() is False]

    lowered = {}
    for stem in stems:
        lowered.setdefault(stem.lower(), []).append(stem)
    index_lowers = {name.lower() for name in names}
    mismatched_stems = {stem for stem in stems if stem not in seen and stem.lower() in index_lowers}
    spelling_mismatch = []
    for name in names:
        if (doc_root / f"{name}.md").is_file():
            continue
        for stem in lowered.get(name.lower(), ()):
            if stem != name:
                spelling_mismatch.append(f"{name} (索引) -> {stem}.md (実ファイル)")

    orphans = sorted(
        stem for stem in stems if stem not in seen and stem not in mismatched_stems
    )

    state_path = repo / ".create-envvars-docs.state.json"
    tried: set[str] = set()
    if state_path.is_file():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                tried = {key for key, value in data.items() if isinstance(value, dict)}
        except (json.JSONDecodeError, OSError) as exc:
            report["problems"].append(f"試行記録が読めません: {exc}")

    missing_untried = [name for name in missing if name not in tried]
    missing_tried = [name for name in missing if name in tried]

    no_meta: list[str] = []
    no_sha: list[str] = []
    no_date: list[str] = []
    bad_title: list[str] = []
    thin_sections: list[str] = []
    no_evidence: list[str] = []
    sha_counts: Counter[str] = Counter()

    for stem, path in stems.items():
        text = path.read_text(encoding="utf-8", errors="replace")
        first = text.split("\n", 1)[0].strip()
        if first != f"# `{stem}`":
            if not first.startswith("# "):
                bad_title.append(f"{path.name}: H1 が無い（1 行目が `{first[:60]}`）")
            elif stem not in first:
                bad_title.append(f"{path.name}: H1 に環境変数名が無い（`{first[:60]}`）")
            elif f"`{stem}`" not in first:
                bad_title.append(f"{path.name}: H1 の表記が逸脱（`{first[:60]}`）")
            else:
                bad_title.append(f"{path.name}: H1 に余計な文字がある（`{first[:60]}`）")
        sha, date, has_meta = doc_meta(path)
        if not has_meta:
            no_meta.append(path.name)
        if not sha:
            no_sha.append(path.name)
        else:
            sha_counts[sha] += 1
        if not date:
            no_date.append(path.name)
        absent = [section for section in ENVVAR_REQUIRED_SECTIONS if section not in text]
        if absent:
            thin_sections.append(f"{path.name}: {', '.join(absent)}")
        if not ENVVAR_EVIDENCE_HEADING_RE.search(text) and not SOURCE_LINE_RE.search(text):
            no_evidence.append(path.name)

    report.update(
        {
            "doc_count": len(files),
            "missing": missing,
            "missing_untried": missing_untried,
            "missing_tried": missing_tried,
            "orphans": orphans,
            "spelling_mismatch": spelling_mismatch,
            "no_meta": no_meta,
            "no_sha": no_sha,
            "no_date": no_date,
            "bad_title": bad_title,
            "thin_sections": thin_sections,
            "no_evidence": no_evidence,
            "sha_counts": dict(sha_counts),
        }
    )

    if orphans:
        report["problems"].append(f"索引に無い環境変数文書 {len(orphans)} 件")
    if spelling_mismatch:
        report["problems"].append(f"索引と綴りが違うファイル {len(spelling_mismatch)} 件")
    if no_meta or no_sha or no_date:
        report["problems"].append(
            f"envvars: 調査対象行 {len(no_meta)} 件 / SHA {len(no_sha)} 件 / 調査日 {len(no_date)} 件の欠落"
        )
    add_suspect_shas(report, target_sha)
    return report


def cli_sections(index_text: str) -> list[tuple[str, list[str], list[str]]]:
    """索引を `###` 見出し単位に割り、(見出し, リンク text, リンク path) を返す。"""
    sections: list[tuple[str, list[str], list[str]]] = []
    current = ("(索引の前置き)", [], [])
    for line in index_text.splitlines():
        if line.startswith("### "):
            sections.append(current)
            current = (line[4:].strip(), [], [])
        elif line.startswith("## "):
            sections.append(current)
            current = ("(節: " + line[3:].strip() + ")", [], [])
        match = CLI_INDEX_LINK_RE.match(line)
        if match:
            current[1].append(match.group(1))
            current[2].append(match.group(2))
    sections.append(current)
    return [section for section in sections if section[1]]


def check_cli(repo: Path, target_sha: str) -> dict[str, object]:
    """docs/cli の索引と本文を突合する。"""
    doc_root = repo / CLI_DIR
    index_path = doc_root / CLI_INDEX
    report: dict[str, object] = {"index_sha": target_sha, "problems": []}
    if not index_path.is_file():
        report["problems"].append(f"索引が見つかりません: {index_path}")
        return report

    index_text = index_path.read_text(encoding="utf-8")
    linked: dict[str, str] = {}
    for line in index_text.splitlines():
        match = CLI_INDEX_LINK_RE.match(line)
        if match:
            linked[match.group(2)] = match.group(1)

    missing = sorted(path for path in linked if not (doc_root / path).is_file())
    linked_rel = set(linked)

    real_files: list[Path] = []
    for path in sorted(doc_root.rglob("*.md")):
        rel = str(path.relative_to(doc_root))
        if rel in {CLI_INDEX, "000_cli_tools.md", "001_investigation.md"}:
            continue
        real_files.append(path)

    orphans = sorted(str(p.relative_to(doc_root)) for p in real_files if str(p.relative_to(doc_root)) not in linked_rel)

    indexed_tools = {rel.split("/")[0] for rel in linked_rel if "/" in rel}
    real_tools = {path.name for path in doc_root.iterdir() if path.is_dir()}
    unknown_tools = sorted(real_tools - indexed_tools)

    section_problems: list[str] = []
    order_problems: list[str] = []
    for title, texts, paths in cli_sections(index_text):
        overview = [path for path in paths if path.endswith("/README.md")]
        if len(overview) == 0:
            section_problems.append(f"{title}: コマンド概要リンクが無い")
        elif len(overview) > 1:
            section_problems.append(f"{title}: コマンド概要リンクが {len(overview)} 個")
        elif paths[0] != overview[0]:
            section_problems.append(f"{title}: コマンド概要が先頭に無い")
        keys = []
        for text, path in zip(texts, paths):
            if path.endswith("/README.md"):
                continue
            name_match = OPTION_NAME_RE.search(text)
            keys.append((name_match.group(1) if name_match else path, path))
        ordered = sorted(keys, key=lambda item: item[0])
        if [k for k, _ in keys] != [k for k, _ in ordered]:
            first_bad = next(
                (
                    i
                    for i, (a, b) in enumerate(zip(keys, ordered))
                    if a[0] != b[0]
                ),
                0,
            )
            order_problems.append(
                f"{title}: {keys[first_bad][0]} が {ordered[first_bad][0]} より後ろに有る"
            )

    no_meta: list[str] = []
    no_sha: list[str] = []
    no_date: list[str] = []
    sha_counts: Counter[str] = Counter()
    for path in real_files:
        sha, date, has_meta = doc_meta(path)
        rel = str(path.relative_to(doc_root))
        if not has_meta:
            no_meta.append(rel)
        if not sha:
            no_sha.append(rel)
        else:
            sha_counts[sha] += 1
        if not date:
            no_date.append(rel)

    report.update(
        {
            "index_link_count": len(linked),
            "doc_count": len(real_files),
            "missing": missing,
            "orphans": orphans,
            "unknown_tools": unknown_tools,
            "section_problems": section_problems,
            "order_problems": order_problems,
            "no_meta": no_meta,
            "no_sha": no_sha,
            "no_date": no_date,
            "sha_counts": dict(sha_counts),
        }
    )

    if orphans:
        report["problems"].append(f"索引にリンクされていない CLI 文書 {len(orphans)} 件")
    if unknown_tools:
        report["problems"].append(f"索引に現れない tool-id ディレクトリ {len(unknown_tools)} 件: {unknown_tools}")
    if section_problems:
        report["problems"].append(f"コマンド節の問題 {len(section_problems)} 件")
    if order_problems:
        report["problems"].append(f"option の並び順違反 {len(order_problems)} 件")
    if no_meta or no_sha or no_date:
        report["problems"].append(
            f"cli: 調査対象行 {len(no_meta)} 件 / SHA {len(no_sha)} 件 / 調査日 {len(no_date)} 件の欠落"
        )
    add_suspect_shas(report, target_sha)
    return report


def add_suspect_shas(report: dict[str, object], target: str) -> None:
    """索引の SHA と 1〜2 文字しか違わない commit SHA を誤記候補として報告する。"""
    if not target:
        return
    counts = report.get("sha_counts", {})
    if not isinstance(counts, dict):
        return
    for sha, count in sorted(counts.items()):
        if sha != target and similar(sha, target):
            report["problems"].append(
                f"{sha} は索引の {target} と {distance(sha, target)} 文字差（誤記または別 commit）: {count} 件"
            )


def similar(a: str, b: str) -> bool:
    """SHA 表記の誤記らしきものだけを拾う（1〜2 文字差）。"""
    return 0 < distance(a, b) <= 2


def distance(a: str, b: str) -> int:
    """同じ長さの 16 進文字列としての異なる文字数。長さが違えば大きい値を返す。"""
    if len(a) != len(b):
        return 99
    return sum(1 for x, y in zip(a, b) if x != y)


def print_meta_gaps(report: dict[str, object], limit: int = 15) -> None:
    """調査対象行の欠落を、原因別にまとめて表示する。"""
    no_meta = set(report.get("no_meta", []))
    no_sha_only = [item for item in report.get("no_sha", []) if item not in no_meta]
    no_date_only = [
        item
        for item in report.get("no_date", [])
        if item not in no_meta and item not in no_sha_only
    ]
    groups = [
        ("調査対象行そのものが無い", sorted(no_meta)),
        ("調査対象行に commit SHA が無い", sorted(no_sha_only)),
        ("調査対象行に調査日が無い", sorted(no_date_only)),
    ]
    for label, items in groups:
        if not items:
            continue
        print(f"  {label} {len(items)} 件:")
        for item in items[:limit]:
            print(f"    {item}")
        if len(items) > limit:
            print(f"    … 他 {len(items) - limit} 件")


def report_stale(env_report: dict[str, object], cli_report: dict[str, object], target: str) -> None:
    """基準 SHA 以外で書かれた文書の件数を出す（本文の特定はしない）。"""
    for label, report in (("envvars", env_report), ("cli", cli_report)):
        counts = report.get("sha_counts", {})
        if not isinstance(counts, dict):
            continue
        stale_total = sum(count for sha, count in counts.items() if sha != target)
        print(f"\n[{label}] 基準 {target or '(不明)'} 以外の文書: {stale_total} 件")
        for sha, count in sorted(counts.items(), key=lambda item: -item[1]):
            mark = "= 基準" if sha == target else ""
            print(f"  {sha}  {count} 件 {mark}")
        if target:
            close = [sha for sha in counts if sha != target and similar(sha, target)]
            for sha in sorted(close):
                print(f"  疑わしい SHA（{target} と {distance(sha, target)} 文字差）: {sha} {counts[sha]} 件")


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"リポジトリが見つかりません: {repo}", file=sys.stderr)
        return 2

    env_report: dict[str, object] = {}
    cli_report: dict[str, object] = {}

    if args.scope in ("all", "envvars"):
        index_sha = read_index_sha(repo / ENVVAR_DIR / ENVVAR_INDEX)
        env_report = check_envvars(repo, args.target or index_sha)
    if args.scope in ("all", "cli"):
        index_sha = read_index_sha(repo / CLI_DIR / CLI_INDEX)
        cli_report = check_cli(repo, args.target or index_sha)

    if args.json:
        print(json.dumps({"envvars": env_report, "cli": cli_report}, ensure_ascii=False, indent=2))
    else:
        if env_report:
            print(f"[envvars] 索引 {env_report['index_count']} 件 / 本文 {env_report['doc_count']} 件")
            print(
                f"  未作成 {len(env_report['missing'])} 件"
                f"（未調査 {len(env_report['missing_untried'])} 件 / 試行済み {len(env_report['missing_tried'])} 件）"
            )
            print(f"  索引に無い本文 {len(env_report['orphans'])} 件 / 綴り不一致 {len(env_report['spelling_mismatch'])} 件")
            print(
                f"  必須節の欠落 {len(env_report['thin_sections'])} 件 / 根拠の記載が無い {len(env_report['no_evidence'])} 件 / "
                f"見出し不審 {len(env_report['bad_title'])} 件 / 調査対象行の欠落 "
                f"{len(env_report['no_meta']) + len(env_report['no_sha']) + len(env_report['no_date'])} 件"
            )
            for label in ("orphans", "spelling_mismatch", "thin_sections", "no_evidence", "bad_title"):
                items = env_report[label]
                if items:
                    print(f"  {label}:")
                    for item in items[:15]:
                        print(f"    {item}")
                    if len(items) > 15:
                        print(f"    … 他 {len(items) - 15} 件")
            print_meta_gaps(env_report)
        if cli_report:
            print(f"\n[cli] 索引リンク {cli_report['index_link_count']} 件 / 本文 {cli_report['doc_count']} 件")
            print(f"  未作成（予定リンク） {len(cli_report['missing'])} 件 / 索引に無い本文 {len(cli_report['orphans'])} 件")
            print(
                f"  索引に無い tool-id {len(cli_report['unknown_tools'])} 件 / "
                f"コマンド節の問題 {len(cli_report['section_problems'])} 件 / 並び順違反 {len(cli_report['order_problems'])} 件 / "
                f"調査対象行の欠落 {len(cli_report['no_meta']) + len(cli_report['no_sha']) + len(cli_report['no_date'])} 件"
            )
            for label in ("missing", "orphans", "section_problems", "order_problems"):
                items = cli_report[label]
                if items:
                    print(f"  {label}:")
                    for item in items[:15]:
                        print(f"    {item}")
                    if len(items) > 15:
                        print(f"    … 他 {len(items) - 15} 件")
            print_meta_gaps(cli_report)

        problems = list(env_report.get("problems", [])) + list(cli_report.get("problems", []))
        print()
        if problems:
            print("問題:")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print("問題なし")

        if args.list_missing:
            for label, report in (("envvars", env_report), ("cli", cli_report)):
                for item in report.get("missing", []):
                    print(f"{label}\t{item}")

        if args.stale:
            target = args.target or str(env_report.get("index_sha") or cli_report.get("index_sha") or "")
            report_stale(env_report, cli_report, target)

    problems = list(env_report.get("problems", [])) + list(cli_report.get("problems", []))
    if args.strict and problems:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
