#!/usr/bin/env python3
"""Stage 1/2/3 で既存文書の陳腐化を検出し、削除候補を .strata-stale.json に書く。

- Stage 1: 文書の「調査対象 commit SHA」から現行 HEAD までの差分で、根拠座標の行範囲が hunk と
  交差するかを見る。
- Stage 2: 交差した hunk の +/- 行に主題トークン（環境変数名 / option 文字列）が出るかを見る。
- Stage 3: envvars は所在移動と引用シンボルの現存、cli は option inventory (S-c) と突合する。
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
from datetime import datetime

from staleness_lib import (
    build_name_index,
    sha_distance,
    similar_sha,
    CLI_DIR,
    CLI_INDEX,
    ENVVAR_DIR,
    ENVVAR_INDEX,
    StrataTree,
    build_evidence,
    default_strata_root,
    doc_cite_files,
    git,
    git_ok,
    read_index_sha,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]

CANDIDATE_VERDICTS = [
    "token-in-diff",
    "option-absent-in-grammar",
    "symbol-gone",
    "name-gone",
    "cited-file-gone",
    "unknown-sha",
    "no-meta",
]
FUNC_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{5,})\s*\(")
QUALIFIED_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]{2,}(?:::[A-Za-z_][A-Za-z0-9_]{2,})+)`")
DETAIL_SECTIONS = ("## 実行時の詳細", "## 有効になる条件", "## 実行時の動作", "## 適用条件と副作用", "## 根拠")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="既存文書の陳腐化を検出します。")
    parser.add_argument("--repo", type=pathlib.Path, default=REPO_ROOT)
    parser.add_argument("--strata", type=pathlib.Path, default=default_strata_root())
    parser.add_argument("--evidence", type=pathlib.Path, help=".strata-evidence.json (既定は場で構築)")
    parser.add_argument("--revision", help="基準 revision (既定は索引に書いた SHA)")
    parser.add_argument("--scope", choices=["all", "envvars", "cli"], default="all")
    parser.add_argument(
        "--stage3",
        action="store_true",
        help="所在移動 / 引用シンボル / option inventory の補助判定を行う",
    )
    parser.add_argument(
        "--with-symbols",
        action="store_true",
        help="--stage3 の envvars で、引用シンボルの現存も見る (git grep が増える)",
    )
    parser.add_argument("--grammar", type=pathlib.Path, default=REPO_ROOT / ".cli-grammar.json")
    parser.add_argument(
        "--symbol-limit",
        type=int,
        default=200,
        metavar="N",
        help="--with-symbols で 引用シンボル現存を見る文書数の上限 (git grep が増える)",
    )
    parser.add_argument("--report", type=pathlib.Path, default=REPO_ROOT / ".strata-stale.json")
    parser.add_argument("--list", action="store_true", help="候補を一覧する")
    parser.add_argument("--limit", type=int, default=30, metavar="N")
    return parser.parse_args()


def load_evidence(args: argparse.Namespace, revision: str) -> dict[str, object]:
    if args.evidence and args.evidence.is_file():
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
        if payload.get("revision") == revision:
            return payload
        print(f"台帳の revision ({payload.get('revision')}) が基準 ({revision}) と違うので作り直します")
    return build_evidence(args.repo.resolve(), args.strata.resolve(), revision, args.scope)


def section_text(text: str) -> str:
    """詳細・根拠節あたりの本文だけ返す（シンボル抽出のノイズ削減）。"""
    chunks: list[str] = []
    keep = False
    for line in text.split("\n"):
        if line.startswith("## "):
            keep = line in DETAIL_SECTIONS
        elif keep:
            chunks.append(line)
    return "\n".join(chunks) if chunks else text


def doc_symbols(path: pathlib.Path, limit: int = 12) -> list[str]:
    text = section_text(path.read_text(encoding="utf-8", errors="replace"))
    found = [m.group(1) for m in FUNC_RE.finditer(text)] + [m.group(1) for m in QUALIFIED_RE.finditer(text)]
    unique = sorted({name for name in found if name not in {"getenv", "strlen", "printf", "main"}}, key=len, reverse=True)
    return unique[:limit]


def stage1_2(
    docs: dict[str, dict[str, object]],
    revision: str,
    tree: StrataTree,
    strata: pathlib.Path,
    grammar_files: dict[str, set[str]] | None = None,
) -> dict[str, dict[str, object]]:
    """Stage 1 / Stage 2 の判定を doc に書き込む。"""
    by_sha: dict[str, list[str]] = collections.defaultdict(list)
    for key, doc in docs.items():
        by_sha[str(doc["doc_sha"])].append(key)

    known_shas = {
        sha for sha in by_sha if sha and git_ok(strata, "cat-file", "-e", f"{sha}^{{commit}}")
    }
    hunk_cache: dict[str, dict[str, list[tuple[int, int, int, int, list[str]]]]] = {}
    for sha, keys in by_sha.items():
        if sha == revision or not sha or not git_ok(strata, "cat-file", "-e", f"{sha}^{{commit}}"):
            continue
        files = sorted({path for key in keys for path in doc_cite_files(docs[key])})
        hunk_cache[sha] = tree.hunk_data(sha, files)

    for key, doc in docs.items():
        sha = str(doc["doc_sha"])
        if not sha:
            doc["verdict"] = "no-meta"
            continue
        if sha == revision:
            doc["verdict"] = "same-revision"
            continue
        if sha not in hunk_cache:
            doc["verdict"] = "unknown-sha"
            near = [ref for ref in (revision, *sorted(known_shas)) if similar_sha(sha, ref)]
            if near:
                best = min(near, key=lambda ref: sha_distance(sha, ref))
                doc["sha_suggestion"] = f"{best}（{sha_distance(sha, best)} 文字差）"
            continue
        per = hunk_cache[sha]
        token = str(doc["token"])
        touched: list[str] = []
        token_lines: list[str] = []
        token_re = re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(token) + r"(?![A-Za-z0-9_-])") if token else None
        for path, start, end in doc["coords"]:  # type: ignore[misc]
            for old_a, old_b, new_a, new_b, lines in per.get(path, ()):
                if not (end < new_a or start > new_b):
                    touched.append(path)
                    if token_re:
                        token_lines += [line for line in lines if token_re.search(line)]
                    break
        unresolved = [cited for cited, (state, _) in doc["cites"].items() if state in {"absent"}]  # type: ignore[attr-defined]
        # option 文字列を宣言するファイルの差分でなければ、別名・usage 文言の揺れとみなす
        if grammar_files is not None and token_lines:
            declared = grammar_files.get(token, set())
            if declared and not (declared & set(touched)):
                token_lines = []
        doc["touched_files"] = sorted(set(touched))
        doc["token_lines"] = token_lines[:6]
        doc["unresolved_cites"] = sorted(unresolved)
        if not touched:
            if doc["coords"]:
                doc["verdict"] = "hunk-intact"
            elif unresolved:
                doc["verdict"] = "cited-file-gone"
            else:
                doc["verdict"] = "no-coords"
        elif token_lines:
            doc["verdict"] = "token-in-diff"
        else:
            doc["verdict"] = "file-only"
    return docs


def add_changed_commits(
    docs: dict[str, dict[str, object]],
    tree: StrataTree,
) -> None:
    """削除候補に、触れたコミット一覧を添える (--stale-report で codex に渡す)。"""
    for doc in docs.values():
        if doc["verdict"] not in CANDIDATE_VERDICTS:
            continue
        files = [path for path, _, _ in doc["coords"]]
        doc["changed_commits"] = tree.commits_touching(str(doc["doc_sha"]), sorted(set(files))[:10])[:12]


def stage3_envvars(
    docs: dict[str, dict[str, object]],
    revision: str,
    strata: pathlib.Path,
    name_index: dict[str, set[str]],
    with_symbols: bool,
    symbol_budget: int,
) -> None:
    """S-a 所在移動 / S-b 引用シンボル / 名前の消失を見る。

    名前の所在は build_name_index の表で引く（変数ごとの git grep は避ける）。
    """
    for key, doc in docs.items():
        if doc["verdict"] not in {"file-only", "cited-file-gone"}:
            continue
        token = str(doc["token"])
        hits = sorted(name_index.get(token, set()))
        cited = set(doc_cite_files(doc))
        doc["found_now"] = hits[:8]
        doc["found_in"] = len(hits)
        if not hits:
            doc["verdict"] = "name-gone"
            continue
        if not (cited & set(hits)):
            doc["verdict"] = "moved"
            continue
        if with_symbols and symbol_budget > 0:
            symbol_budget -= 1
            symbols = doc_symbols(pathlib.Path(str(doc["file"])))
            gone = [
                name
                for name in symbols
                if not git(strata, "grep", "-l", "-F", name, revision).strip()
            ]
            if symbols and len(gone) >= max(2, (len(symbols) + 1) // 2):
                doc["symbols_missing"] = gone[:12]
                doc["verdict"] = "symbol-gone"


def stage3_cli(docs: dict[str, dict[str, object]], grammar_path: pathlib.Path, revision: str) -> None:
    """S-c option inventory と突合する。"""
    if not grammar_path.is_file():
        print(f"option inventory がありません: {grammar_path} (cli-grammar.py で生成)")
        return
    payload = json.loads(grammar_path.read_text(encoding="utf-8"))
    if payload.get("revision") != revision:
        print(f"inventory の revision ({payload.get('revision')}) が基準 ({revision}) と違います")
        return
    options = payload.get("options", {})
    for key, doc in docs.items():
        if doc["verdict"] not in {"file-only", "cited-file-gone", "hunk-intact", "token-in-diff"}:
            continue
        token = str(doc["token"])
        if not token:
            continue
        where = options.get(token, [])
        doc["grammar_hits"] = len(where)
        if not where:
            doc["verdict"] = "option-absent-in-grammar"


def summarize(docs: dict[str, dict[str, object]], limit: int, list_candidates: bool) -> dict[str, int]:
    counts = collections.Counter(str(doc["verdict"]) for doc in docs.values())
    for verdict, count in counts.most_common():
        print(f"  {verdict:28} {count:5}")
    if list_candidates:
        for verdict in CANDIDATE_VERDICTS:
            keys = [key for key, doc in docs.items() if doc["verdict"] == verdict]
            if not keys:
                continue
            print(f"\n候補 {verdict} ({len(keys)} 件):")
            for key in keys[:limit]:
                doc = docs[key]
                print(f"  {key}\t{doc['file']}\tdoc_sha={str(doc['doc_sha'])[:7]}")
    return dict(counts)


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    strata = args.strata.resolve()
    if not strata.is_dir():
        print(f"Strata checkout が見つかりません: {strata}")
        return 2

    index_sha = read_index_sha(repo / ENVVAR_DIR / ENVVAR_INDEX) or read_index_sha(repo / CLI_DIR / CLI_INDEX)
    revision = args.revision or index_sha or git(strata, "rev-parse", "HEAD").strip()
    if not git_ok(strata, "cat-file", "-e", f"{revision}^{{commit}}"):
        print(f"基準 revision が Strata に実在しません: {revision}")
        return 2

    payload = load_evidence(args, revision)
    tree = StrataTree(strata, revision)
    report: dict[str, object] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "strata_root": str(strata),
        "revision": revision,
        "scopes": {},
    }

    grammar_files: dict[str, set[str]] | None = None
    if args.grammar.is_file():
        gp = json.loads(args.grammar.read_text(encoding="utf-8"))
        if gp.get("revision") == revision:
            grammar_files = {
                name: {item["file"] for item in where}
                for name, where in gp.get("options", {}).items()
            }

    all_candidates: list[dict[str, object]] = []
    for scope in ("envvars", "cli"):
        docs_raw = payload.get(scope)
        if not isinstance(docs_raw, dict):
            continue
        docs = {key: dict(value) for key, value in docs_raw.items()}
        stage1_2(docs, revision, tree, strata, grammar_files if scope == "cli" else None)
        add_changed_commits(docs, tree)
        if args.stage3:
            if scope == "envvars":
                name_index = build_name_index(strata, revision)
                print(f"[name index] {len(name_index)} 名")
                stage3_envvars(docs, revision, strata, name_index, args.with_symbols, args.symbol_limit)
            else:
                stage3_cli(docs, args.grammar.resolve(), revision)
        print(f"\n[{scope}] 文書 {len(docs)} 件の判定")
        counts = summarize(docs, args.limit, args.list)
        candidates = [
            {"scope": scope, "key": key, **{k: v for k, v in doc.items() if k != "cites"}}
            for key, doc in docs.items()
            if doc["verdict"] in CANDIDATE_VERDICTS
        ]
        all_candidates.extend(candidates)
        report["scopes"][scope] = {"counts": counts, "candidate_count": len(candidates)}

    report["candidates"] = all_candidates
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n候補 {len(all_candidates)} 件 / 台帳: {args.report}")
    print("mark-stale.py --from-report で削除へ進めます（既定は dry-run）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
