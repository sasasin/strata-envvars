#!/usr/bin/env python3
"""docs/envvars と docs/cli の文書から「調査対象 commit SHA」と「根拠座標」を抽出した台帳を作る。

Stage 0。find-stale.py がこの台帳を読んで陳腐化を判定する。台帳は機械生成なので
リポジトリにコミットしない (.strata-evidence.json)。
"""

from __future__ import annotations

import argparse
import json
import pathlib

from staleness_lib import (
    CLI_DIR,
    CLI_INDEX,
    ENVVAR_DIR,
    ENVVAR_INDEX,
    build_evidence,
    default_strata_root,
    git,
    git_ok,
    read_index_sha,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="証拠台帳 .strata-evidence.json を作ります。")
    parser.add_argument("--repo", type=pathlib.Path, default=REPO_ROOT)
    parser.add_argument("--strata", type=pathlib.Path, default=default_strata_root())
    parser.add_argument("--revision", help="Strata の基準 revision (既定は索引に書いた SHA)")
    parser.add_argument("--out", type=pathlib.Path, default=REPO_ROOT / ".strata-evidence.json")
    parser.add_argument("--scope", choices=["all", "envvars", "cli"], default="all")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    strata = args.strata.resolve()
    if not strata.is_dir():
        print(f"Strata checkout が見つかりません: {strata}")
        return 2

    index_sha = read_index_sha(repo / ENVVAR_DIR / ENVVAR_INDEX) or read_index_sha(
        repo / CLI_DIR / CLI_INDEX
    )
    revision = args.revision or index_sha or git(strata, "rev-parse", "HEAD").strip()
    if not git_ok(strata, "cat-file", "-e", f"{revision}^{{commit}}"):
        print(f"基準 revision が Strata に実在しません: {revision}")
        return 2

    payload = build_evidence(repo, strata, revision, args.scope)
    payload["index_sha"] = index_sha

    for scope in ("envvars", "cli"):
        docs = payload.get(scope)
        if isinstance(docs, dict):
            coords = sum(len(doc["coords"]) for doc in docs.values())
            print(f"{scope}: {len(docs)} 文書 / 解決できた座標 {coords} 件")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"台帳: {args.out}")
    print(f"基準 revision: {revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
