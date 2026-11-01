#!/usr/bin/env python3
"""Create missing environment variable documentation listed in docs/envvars/000_envvers.md.

候補一覧には Strata が実際に読まない名前も混じっているため、調査しても文書が作られない
変数がある。そのような変数を毎回選び直さないよう、試行結果を STATE ファイルに記録する。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
DOC_ROOT = REPO_ROOT / "docs" / "envvars"
INDEX = DOC_ROOT / "000_envvers.md"
STATE = REPO_ROOT / ".create-envvars-docs.state.json"
STRATA_ROOT = Path.home() / "src" / "github.com" / "Niko1221" / "Strata"

PROMPT_TEMPLATE = """調査依頼です。Strata の環境変数 1 個について、調査文書を作成してください。

調査対象ソースコード:
`{strata_root}`

対象環境変数:
`{envvar}`

作成対象文書:
`{doc_path}`

次の手順で作業してください。

1. Strata リポジトリで `git rev-parse HEAD` と `git status --short --branch` を確認してください。調査対象の完全な commit SHA と調査日を文書に記録し、未コミット変更を上書きしないでください。
2. `{investigation}` の調査範囲・手法・文書フォーマット・品質基準に従ってください。書式と詳しさの基準文書は `{example_doc}` です。
3. `{index}` は grep で得た候補一覧であり、その名前が実際に環境変数であることを保証しません。候補名の全参照を `rg` で洗い出し、実際に環境から値を読んでいる箇所を特定してください。helper 経由や動的な名前の渡し先も追跡し、最初に見つかった箇所だけで判断しないでください。
4. 値の判定（未設定・空文字・変換方法・境界・無効値）、既定値と CLI 引数や他の環境変数との優先順位、読み取りの時期と cache の有無、有効になる条件（OS / backend / build macro / サーバーモード / CLI / モデル状態 / 他変数）、実際の挙動、観測できるログ・終了・失敗経路を、Strata の相対ファイルパスと行番号で裏付けてください。
5. 外部ライブラリや GPU driver が読むだけの名前や、読み取り箇所が見つからない場合は、空の文書や推測の文書を作らず、`{index}` との食い違いとして報告してください。Strata が値を読む・転送する・警告を出す事実だけを書き、外部ライブラリ側の挙動を Strata の挙動として説明しないでください。
6. 作成先がすでに存在する場合は上書きせず、その旨を報告してください。
7. 編集対象は指定された文書 1 件だけです。索引 `{index}`、`{investigation}`、他の環境変数文書、Strata のソースコードを変更しないでください。調査のためのソース変更、build、GPU 実行、性能測定、テストは行わないでください。
{stale_note}
"""

INDEX_ENTRY_RE = re.compile(r"^- `([A-Za-z0-9_]+)`\s*$")
SAFE_ENVVAR_RE = re.compile(r"^[A-Za-z0-9_]+$")


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
        description=(
            "docs/envvars/000_envvers.md の一覧から未作成の環境変数文書を決め、"
            "1 変数 1 セッションで Codex に調査・作成させます。"
        ),
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
        "--include-tried",
        action="store_true",
        help="既に調査して文書ができなかった変数も候補に含める",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="作成対象を一覧するだけで codex は実行しない",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="試行記録を消してから実行する",
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
    """陳腐化検出の報告を、変数名ごとの追記文にする。"""
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
        if item.get("scope") != "envvars":
            continue
        name = str(item.get("key", ""))
        if not name:
            continue
        lines = [
            "",
            "追加情報: この文書は陳腐化検出で削除されました。旧記述を引き継がず、現行 checkout を読み直して作成してください。",
            f"- 判定: {item.get('verdict')}",
            f"- 旧文書の調査対象: {item.get('doc_sha')}（{item.get('doc_date') or '調査日不明'}）、現行基準: {revision}",
        ]
        commits = item.get("changed_commits") or []
        if commits:
            lines.append(f"- 根拠ファイルに触れたコミット（先頭 {min(6, len(commits))} 件）:")
            lines += [f"    {line}" for line in commits[:6]]
        for diff_line in (item.get("token_lines") or [])[:4]:
            lines.append(f"- 変更差分にこの変数名が現れます: {diff_line[:160]}")
        for path in (item.get("found_now") or [])[:5]:
            lines.append(f"- 現行 checkout での所在候補: {path}")
        for symbol in (item.get("symbols_missing") or [])[:6]:
            lines.append(f"- 旧文書が挙げるが現行 Strata に無い識別子: {symbol}")
        notes[name] = "\n".join(lines)
    return notes


def read_index() -> list[str]:
    """Return environment variable names listed in the index, in index order."""
    if not INDEX.is_file():
        raise FileNotFoundError(f"environment variable index not found: {INDEX}")

    names: list[str] = []
    seen: set[str] = set()
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        match = INDEX_ENTRY_RE.match(line)
        if not match:
            continue
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def load_state() -> dict[str, dict[str, object]]:
    """Return the recorded attempt history, or an empty mapping."""
    if not STATE.is_file():
        return {}
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"試行記録を読み込めません: {exc}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print("試行記録の形式が不正です。無視します。", file=sys.stderr)
        return {}
    return {key: value for key, value in data.items() if isinstance(value, dict)}


def save_state(state: dict[str, dict[str, object]]) -> None:
    STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def record(state: dict[str, dict[str, object]], envvar: str, status: str) -> None:
    entry = state.get(envvar, {})
    attempts = entry.get("attempts", 0)
    state[envvar] = {
        "attempts": (attempts + 1) if isinstance(attempts, int) else 1,
        "status": status,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    save_state(state)


def find_missing(names: list[str]) -> tuple[list[str], list[str]]:
    """Split index names into (missing, skipped) based on existing doc files."""
    missing: list[str] = []
    skipped: list[str] = []
    for name in names:
        if not SAFE_ENVVAR_RE.match(name):
            skipped.append(name)
            continue
        if (DOC_ROOT / f"{name}.md").exists():
            skipped.append(name)
            continue
        missing.append(name)
    return missing, skipped


def create_doc(envvar: str, stale_note: str = "") -> tuple[str, int, str, str]:
    doc_path = DOC_ROOT / f"{envvar}.md"
    prompt = PROMPT_TEMPLATE.format(
        strata_root=STRATA_ROOT,
        envvar=envvar,
        doc_path=doc_path,
        index=INDEX,
        investigation=DOC_ROOT / "001_investigation.md",
        example_doc=DOC_ROOT / "STRATA_ADAPT_OVERLAP.md",
        stale_note=stale_note,
    )
    with tempfile.TemporaryDirectory(prefix="create-envvars-docs-") as temp_dir:
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
    return envvar, result.returncode, last_message, failure_log


def main() -> int:
    args = parse_args()
    try:
        names = read_index()
    except (FileNotFoundError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 2

    if not names:
        print(f"索引から環境変数を読み取れませんでした: {INDEX}", file=sys.stderr)
        return 2

    if args.reset_state:
        if STATE.is_file():
            STATE.unlink()
            print(f"試行記録を消去しました: {STATE}")
        args.include_tried = True

    state = load_state()
    missing, skipped = find_missing(names)
    untried = [name for name in missing if name not in state]
    tried = [name for name in missing if name in state]

    pool = untried if not args.include_tried else missing
    targets = pool[: args.doc_limit] if args.doc_limit > 0 else pool

    print(
        f"索引: {len(names)} 件 / 作成済み・対象外: {len(skipped)} 件 / "
        f"未作成: {len(missing)} 件 (未調査: {len(untried)} 件, 試行済み: {len(tried)} 件)"
    )
    if tried and not args.include_tried:
        print(f"  試行済みの {len(tried)} 件は --include-tried で再調査できます。")
    print(f"今回: {len(targets)} 件")

    if not targets:
        print("未作成の環境変数文書はありません。")
        return 0

    if args.dry_run:
        for name in targets:
            print(f"  {name} -> docs/envvars/{name}.md")
        return 0

    notes = load_stale_notes(args.stale_report, strata_head())
    if notes:
        hit = sum(1 for name in targets if name in notes)
        print(f"陳腐化報告: {len(notes)} 件 / 今回対象に {hit} 件分付与")

    completed = 0
    failed_count = 0
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {}
        for name in targets:
            print(f"\n=== 開始: {name} ===", flush=True)
            futures[executor.submit(create_doc, name, notes.get(name, ""))] = name
        for future in as_completed(futures):
            envvar = futures[future]
            try:
                name, returncode, last_message, failure_log = future.result()
            except OSError as exc:
                print(f"codex を実行できませんでした: {exc}", file=sys.stderr)
                record(state, envvar, "error")
                failed_count += 1
                continue

            completed += 1
            if returncode != 0:
                status = "error"
                failed_count += 1
            elif (DOC_ROOT / f"{name}.md").is_file():
                status = "created"
            else:
                status = "no-doc"
            record(state, name, status)

            print(f"\n=== {'完了' if returncode == 0 else '失敗'}: {name} ({status}) ===")
            if last_message:
                print(last_message)
            if returncode != 0:
                print(
                    f"codex が終了コード {returncode} で終了しました: {name}",
                    file=sys.stderr,
                )
                if failure_log:
                    print(f"--- codex の末尾ログ（最大60行）---\n{failure_log}", file=sys.stderr)

    created_now = sum(1 for name in targets if (DOC_ROOT / f"{name}.md").is_file())
    still_missing = [name for name in missing if not (DOC_ROOT / f"{name}.md").is_file()]
    untried_now = [name for name in still_missing if name not in state]
    print(
        f"\n今回: 完了 {completed} 件 / 失敗 {failed_count} 件 / 生成 {created_now} 件"
    )
    print(
        f"残りの未作成 {len(still_missing)} 件"
        f"（未調査 {len(untried_now)} 件 / 試行済み {len(still_missing) - len(untried_now)} 件）"
    )

    return 1 if failed_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
