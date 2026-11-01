#!/usr/bin/env python3
"""Strata checkout から CLI option 文字列の inベントリを抽出して .cli-grammar.json に保存する。

索引更新 (docs/cli/README.md) と同じ grep 手順の機械抽出結果を、陳腐化検出 (find-stale.py の
S-c: option が現行 parser から消えたか) で再利用するための台帳。
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
from datetime import datetime

from staleness_lib import default_strata_root, git, git_ok, read_index_sha

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
CLI_INDEX = REPO_ROOT / "docs" / "cli" / "README.md"

LONG_OPTION_RE = r"-{1,2}[A-Za-z][A-Za-z0-9_-]*"
EXCLUDES = [
    ":(exclude)docs/**",
    ":(exclude)bench/results/**",
    ":(exclude)data/**",
    ":(exclude)ref/**",
    ":(exclude)third_party/**",
    ":(exclude)*.md",
]
LINE_RE = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):(?P<text>.*)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLI option inventory を作ります。")
    parser.add_argument("--strata", type=pathlib.Path, default=default_strata_root())
    parser.add_argument("--revision", help="基準 revision (既定は docs/cli/README.md の SHA)")
    parser.add_argument("--out", type=pathlib.Path, default=REPO_ROOT / ".cli-grammar.json")
    parser.add_argument(
        "--include-short",
        action="store_true",
        help="`-h` のような 1 文字 option も含める (--help 等の誤検地が増える)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    strata = args.strata.resolve()
    if not strata.is_dir():
        print(f"Strata checkout が見つかりません: {strata}")
        return 2

    revision = args.revision or read_index_sha(CLI_INDEX) or git(strata, "rev-parse", "HEAD").strip()
    if not git_ok(strata, "cat-file", "-e", f"{revision}^{{commit}}"):
        print(f"基準 revision が Strata に実在しません: {revision}")
        return 2

    pattern = '"(' + (LONG_OPTION_RE if args.include_short else r"--[A-Za-z][A-Za-z0-9_-]*") + ')"'
    out = git(strata, "grep", "-n", "-E", "-e", pattern, revision, "--", *EXCLUDES)

    options: dict[str, list[dict[str, object]]] = collections.defaultdict(list)
    per_file: dict[str, set[str]] = collections.defaultdict(set)
    for raw in out.split("\n"):
        if not raw:
            continue
        body = raw[len(revision) + 1 :] if raw.startswith(revision) else raw
        match = LINE_RE.match(body)
        if not match:
            continue
        token = match.group("text")
        for name in re.findall(r'"(' + LONG_OPTION_RE + r')"', token):
            options[name].append({"file": match.group("file"), "line": int(match.group("line"))})
            per_file[match.group("file")].add(name)

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "strata_root": str(strata),
        "revision": revision,
        "option_count": len(options),
        "options": dict(sorted(options.items())),
        "files": {k: sorted(v) for k, v in sorted(per_file.items())},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"revision: {revision}")
    print(f"option 文字列 {len(options)} 件 / 出現箇所 {sum(len(v) for v in options.values())} 件 / ファイル {len(per_file)} 件")
    print(f"台帳: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
