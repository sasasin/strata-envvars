#!/usr/bin/env python3
"""Create missing CLI documentation listed in docs/cli/README.md."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
DOC_ROOT = REPO_ROOT / "docs" / "cli"
INDEX = DOC_ROOT / "README.md"
STRATA_ROOT = Path.home() / "src" / "github.com" / "Niko1221" / "Strata"

PROMPT_TEMPLATE = """調査依頼です。Strata の CLI 文書を1件作成してください。

調査対象ソースコード:
`{strata_root}`

作成対象文書:
`{doc_path}`

次の手順で作業してください。

1. Strata リポジトリで `git rev-parse HEAD` と `git status --short --branch` を確認してください。調査対象の完全な commit SHA と調査日を文書に記録し、未コミット変更を上書きしないでください。
2. `{index}` で作成対象のリンク、コマンド階層、option の scope を確認してください。
3. `{investigation}` の配置規約と調査基準に従ってください。
4. 作成対象がオプション文書なら、parser 定義から実際の使用箇所まで調べ、値、既定値、validation、効果、相互作用、適用条件、副作用、出力・失敗経路をソースで裏付けてください。対象がコマンド概要 `README.md` なら `{example_readme}` を参考にし、そのコマンドの役割、代表的な利用方法、実行モード、主要な動作・副作用、注意点、関連文書へのリンクをまとめてください。
5. 文書は日本語で書き、確認した Strata の相対ファイルパスと行番号を根拠として挙げてください。確認できない点は推測せず、調査範囲や制約を明記してください。安全に使える同一 revision の CLI `--help` は補助資料として使えますが、ソースの parser と照合してください。
6. 作成先がすでに存在する場合は上書きせず、その旨を報告してください。指定された option が現行 parser にない場合、または索引との食い違いがある場合も、別の文書を推測で作らず差異を報告してください。
7. 編集対象は指定された文書1件だけです。索引や他文書を変更しないでください。調査のためのソース変更、build、GPU 実行、性能測定、テストは行わないでください。
{stale_note}
"""

INDEX_LINK_RE = re.compile(r"^- \[.*?\]\(([^)]+)\)\s*$")


def positive_int(value: str) -> int:
    """Argparse type for values that must be at least one."""
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def non_negative_int(value: str) -> int:
    """Argparse type for values that may be zero."""
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="docs/cli/README.md から未作成の CLI 文書を選び、Codex で調査・作成します。",
        epilog="--doc-limit 0 は未作成文書をすべて対象にします。",
    )
    parser.add_argument(
        "-l",
        "--doc-limit",
        type=non_negative_int,
        default=1,
        metavar="N",
        help="今回作成する文書数の上限 (default: 1, 0: all)",
    )
    parser.add_argument(
        "-p",
        "--parallel",
        type=positive_int,
        default=1,
        metavar="N",
        help="同時に実行する codex の最大数 (default: 1)",
    )
    parser.add_argument(
        "--stale-report",
        type=Path,
        default=REPO_ROOT / ".strata-stale.json",
        help="find-stale.py の報告。削除理由を codex へ渡す (存在しなければ無視)",
    )
    return parser.parse_args()


def strata_head() -> str:
    result = subprocess.run(
        ("git", "-C", str(STRATA_ROOT), "rev-parse", "HEAD"),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip()


def load_stale_notes(report_path: Path, revision: str) -> dict[str, str]:
    """陳腐化検出の報告を、docs/cli 配下の相対パスごとの追記文にする。"""
    if not report_path.is_file():
        return {}
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"陳腐化報告を読み込めません: {exc}", file=sys.stderr)
        return {}
    if payload.get("revision") != revision:
        print(
            f"陳腐化報告の revision ({payload.get('revision')}) が Strata HEAD ({revision}) と違うので無視します",
            file=sys.stderr,
        )
        return {}

    notes: dict[str, str] = {}
    for item in payload.get("candidates", []):
        if item.get("scope") != "cli":
            continue
        rel = str(item.get("key", ""))
        if not rel:
            continue
        lines = [
            "",
            "追加情報: この文書は陳腐化検出で削除されました。旧記述を引き継がず、現行 checkout の parser を読み直して作成してください。",
            f"- 判定: {item.get('verdict')}",
            f"- 旧文書の調査対象: {item.get('doc_sha')}（{item.get('doc_date') or '調査日不明'}）、現行基準: {revision}",
        ]
        if item.get("sha_suggestion"):
            lines.append(
                f"- 旧文書の SHA は Strata に実在しません。索引の {item['sha_suggestion']} の打ち間違いの可能性があります"
            )
        commits = item.get("changed_commits") or []
        if commits:
            lines.append(f"- 根拠ファイルに触れたコミット（先頭 {min(6, len(commits))} 件）:")
            lines += [f"    {line}" for line in commits[:6]]
        for diff_line in (item.get("token_lines") or [])[:4]:
            lines.append(f"- 変更差分にこの option 文字列が現れます: {diff_line[:160]}")
        if item.get("grammar_hits") is not None:
            lines.append(f"- 現行 Strata での option 文字列の出現箇所数: {item['grammar_hits']}")
        notes[rel] = "\n".join(lines)
    return notes


def find_missing_docs() -> list[Path]:
    if not INDEX.is_file():
        raise FileNotFoundError(f"CLI document index not found: {INDEX}")

    missing: set[Path] = set()
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        match = INDEX_LINK_RE.match(line)
        if not match:
            continue

        target = DOC_ROOT / match.group(1)
        if not target.exists():
            missing.add(target)
    return sorted(missing, key=lambda path: str(path))


def create_doc(doc_path: Path, stale_note: str = "") -> tuple[Path, int, str, str]:
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = PROMPT_TEMPLATE.format(
        strata_root=STRATA_ROOT,
        doc_path=doc_path,
        index=INDEX,
        investigation=DOC_ROOT / "001_investigation.md",
        example_readme=DOC_ROOT / "strata-terminal" / "launch" / "README.md",
        stale_note=stale_note,
    )
    with tempfile.TemporaryDirectory(prefix="create-cli-docs-") as temp_dir:
        temp_path = Path(temp_dir)
        last_message_path = temp_path / "last-message.md"
        log_path = temp_path / "codex.log"
        command = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--cd",
            str(REPO_ROOT),
            "--output-last-message",
            str(last_message_path),
            prompt,
        ]
        with log_path.open("w", encoding="utf-8") as log_file:
            result = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )

        last_message = (
            last_message_path.read_text(encoding="utf-8").strip()
            if last_message_path.is_file()
            else ""
        )
        log_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        failure_log = "\n".join(log_lines[-60:]) if result.returncode != 0 else ""
    return doc_path, result.returncode, last_message, failure_log


def main() -> int:
    args = parse_args()
    try:
        doc_paths = find_missing_docs()
    except (FileNotFoundError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.doc_limit > 0:
        doc_paths = doc_paths[: args.doc_limit]

    if not doc_paths:
        print("未作成の索引文書はありません。")
        return 0

    print(f"今回の作成対象: {len(doc_paths)} 件", flush=True)
    notes = load_stale_notes(args.stale_report, strata_head())
    if notes:
        hit = sum(1 for path in doc_paths if str(path.relative_to(DOC_ROOT)) in notes)
        print(f"陳腐化報告: {len(notes)} 件 / 今回対象に {hit} 件分付与", flush=True)
    failed = False
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {}
        for path in doc_paths:
            print(f"\n=== 開始: {path} ===", flush=True)
            futures[executor.submit(create_doc, path, notes.get(str(path.relative_to(DOC_ROOT)), ""))] = path
        for future in as_completed(futures):
            doc_path = futures[future]
            try:
                completed_path, returncode, last_message, failure_log = future.result()
            except OSError as exc:
                print(f"codex を実行できませんでした: {exc}", file=sys.stderr)
                failed = True
                continue

            print(f"\n=== {'完了' if returncode == 0 else '失敗'}: {completed_path} ===")
            if last_message:
                print(last_message)
            if returncode != 0:
                print(f"codex が終了コード {returncode} で終了しました: {completed_path}", file=sys.stderr)
                if failure_log:
                    print(f"--- codex の末尾ログ（最大60行）---\n{failure_log}", file=sys.stderr)
                failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
