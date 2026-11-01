"""Strata 調査文書の陳腐化検出で共有する部品。

文書から「調査対象 commit SHA」と「根拠座標 (path:line)」を機械抽出し、Strata checkout の
HEAD ツリーに合わせて正規化する。evidence-index.py / find-stale.py / mark-stale.py から使う。
"""

from __future__ import annotations

import collections
import pathlib
import re
import subprocess
from datetime import datetime
from typing import Iterable

ENVVAR_DIR = "docs/envvars"
ENVVAR_INDEX = "000_envvers.md"
ENVVAR_EXCLUDE = {"001_investigation.md", "STRATA_ADAPT_OVERLAP.md"}
CLI_DIR = "docs/cli"
CLI_INDEX = "README.md"
CLI_SKIP = {"README.md", "000_cli_tools.md", "001_investigation.md"}

META_RE = re.compile(r"調査対象:[^\n]*?\b([0-9a-f]{40})\b")
DATE_RE = re.compile(r"調査対象:[^\n]*?\b(\d{4}-\d{2}-\d{2})\b")
COORD_RE = re.compile(
    r"`?([A-Za-z0-9_./+-]+\.(?:c|cc|cpp|cppm|h|hpp|cu|cuh|hip|py|rs|js|mjs|ts|tsx|jsx|"
    r"sh|bash|zsh|bat|cmd|ps1|cmake|txt|md|json|jsonl|toml|yml|yaml|nsi|nsh|proto|metal|"
    r"mm|m|hppm))`?\s*[:：]\s*(\d+)(?:\s*[-–〜,]\s*(\d+))?"
)
CLI_LINK_RE = re.compile(r"^- \[(.*?)\]\(([^)]+)\)\s*$")
OPTION_NAME_RE = re.compile(r"`([^`]+)`")
THIS_REPO_RE = re.compile(r"^(docs/|\.agents/|README\.md$|create-[a-z-]+\.py$|LICENSE$)")


def sha_distance(a: str, b: str) -> int:
    """同じ長さの commit SHA として、異なる 16 進桁の数。長さが違えば 99。"""
    if len(a) != len(b) or len(b) != 40:
        return 99
    return sum(1 for x, y in zip(a, b) if x != y)


def similar_sha(a: str, b: str, max_diff: int = 3) -> bool:
    """SHA 表記の誤記らしきものだけを拾う。"""
    return 0 < sha_distance(a, b) <= max_diff


QUOTED_RE = re.compile(r'"([A-Z][A-Za-z0-9_]{2,})"')
SHELL_REF_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)")
BAT_REF_RE = re.compile(r"%([A-Z_][A-Za-z0-9_]{2,})%")
GREP_PATTERNS = [
    r'"[A-Z][A-Za-z0-9_]{2,}"',
    r"\$\{?[A-Za-z_][A-Za-z0-9_]*",
    r"%[A-Z_][A-Za-z0-9_]{2,}%",
]
GREP_EXCLUDES = [
    ":(exclude)docs/**",
    ":(exclude)bench/results/**",
    ":(exclude)data/**",
    ":(exclude)ref/**",
    ":(exclude)third_party/**",
]


def build_name_index(strata: pathlib.Path, revision: str) -> dict[str, set[str]]:
    """Strata のある revision で「名前 -> 出現ファイル集合」を 1 回の grep 群で作る。

    Stage 3 の所在追跡を、変数ごとの git grep ではなくこの表の参照で済ませるため。
    """
    index: dict[str, set[str]] = {}
    for pattern in GREP_PATTERNS:
        for raw in git(strata, "grep", "-n", "-E", pattern, revision, "--", *GREP_EXCLUDES).split("\n"):
            if not raw:
                continue
            body = raw[len(revision) + 1 :] if raw.startswith(revision) else raw
            parts = body.split(":", 2)
            if len(parts) < 3:
                continue
            path, text = parts[0], parts[2]
            for match in (*QUOTED_RE.finditer(text), *SHELL_REF_RE.finditer(text), *BAT_REF_RE.finditer(text)):
                index.setdefault(match.group(1), set()).add(path)
    return index


def default_strata_root() -> pathlib.Path:
    return pathlib.Path.home() / "src" / "github.com" / "Niko1221" / "Strata"


def git(cwd: pathlib.Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(cwd)) + args,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    return result.stdout


def git_ok(cwd: pathlib.Path, *args: str) -> bool:
    result = subprocess.run(
        ("git", "-C", str(cwd)) + args,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    return result.returncode == 0


def read_index_sha(index_path: pathlib.Path) -> str:
    """索引の「調査対象:」行から Strata の commit SHA を読む（突合の基準 HEAD）。"""
    if not index_path.is_file():
        return ""
    for line in index_path.read_text(encoding="utf-8", errors="replace").splitlines()[:20]:
        if line.startswith("調査対象:"):
            match = META_RE.search(line)
            if match:
                return match.group(1)
    return ""


class StrataTree:
    """Strata のある revision のファイルツリーと、basename からの解決表。"""

    def __init__(self, strata: pathlib.Path, revision: str) -> None:
        self.strata = strata
        self.revision = revision
        listing = git(strata, "ls-tree", "-r", "--name-only", revision).split("\n")
        self.paths = {p for p in listing if p}
        self.by_base: dict[str, list[str]] = collections.defaultdict(list)
        for path in self.paths:
            self.by_base[pathlib.PurePosixPath(path).name].append(path)

    def exists(self, path: str) -> bool:
        return path in self.paths

    def resolve(self, cited: str) -> tuple[str, list[str]]:
        """引用されたパスを (解決状態, Strata 上の候補パス) に直す。

        解決状態は this-repo | exact | basename-unique | basename-multi | absent。
        """
        if THIS_REPO_RE.match(cited) or cited in {ENVVAR_INDEX, "001_investigation.md"}:
            return ("this-repo", [])
        if cited in self.paths:
            return ("exact", [cited])
        hits = sorted(self.by_base.get(pathlib.PurePosixPath(cited).name, []))
        if len(hits) == 1:
            return ("basename-unique", hits)
        if len(hits) > 1:
            return ("basename-multi", hits)
        return ("absent", [])

    def commits_touching(self, since: str, paths: Iterable[str]) -> list[str]:
        """`since..HEAD` でそのパス群に触れたコミット一覧（報告に添える）。"""
        out = git(
            self.strata,
            "log",
            "--oneline",
            f"{since}..{self.revision}",
            "--",
            *paths,
        )
        return [line for line in out.split("\n") if line]

    def hunk_data(self, since: str, paths: list[str]) -> dict[str, list[tuple[int, int, int, int, list[str]]]]:
        """`since..HEAD` の hunk を行範囲と差分テキストで集める（1 回の diff）。"""
        if not paths:
            return {}
        per: dict[str, list[tuple[int, int, int, int, list[str]]]] = collections.defaultdict(list)
        cur_path: str | None = None
        pending: tuple[int, int, int, int] | None = None
        lines: list[str] = []
        out = git(self.strata, "diff", "-U0", "--no-color", f"{since}..{self.revision}", "--", *paths)
        for line in out.split("\n"):
            if line.startswith("+++ b/"):
                if cur_path and pending:
                    per[cur_path].append((*pending, lines))
                cur_path = line[6:].strip()
                pending = None
                lines = []
            elif line.startswith("@@") and cur_path:
                if pending:
                    per[cur_path].append((*pending, lines))
                match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                if not match:
                    pending = None
                    lines = []
                    continue
                old_start = int(match.group(1))
                old_count = int(match.group(2) or 1)
                new_start = int(match.group(3))
                new_count = int(match.group(4) or 1)
                pending = (
                    old_start,
                    old_start + max(old_count, 1) - 1,
                    new_start,
                    new_start + max(new_count, 1) - 1,
                )
                lines = []
            elif line[:1] in "+-" and not line.startswith(("+++", "---")):
                if pending:
                    lines.append(line)
        if cur_path and pending:
            per[cur_path].append((*pending, lines))
        return per


def envvar_docs(repo: pathlib.Path, tree: StrataTree) -> dict[str, dict[str, object]]:
    """docs/envvars の文書を {変数名: {doc_sha, date, coords, cites}} にする。"""
    docs: dict[str, dict[str, object]] = {}
    doc_root = repo / ENVVAR_DIR
    for path in sorted(doc_root.glob("*.md")):
        if path.name.startswith("000_") or path.name in ENVVAR_EXCLUDE:
            continue
        name = path.stem
        text = path.read_text(encoding="utf-8", errors="replace")
        meta = META_RE.search(text)
        date = DATE_RE.search(text)
        coords: list[tuple[str, int, int]] = []
        cites: dict[str, tuple[str, list[str]]] = {}
        for match in COORD_RE.finditer(text):
            cited = match.group(1)
            start = int(match.group(2))
            end = int(match.group(3) or match.group(2))
            state, hits = tree.resolve(cited)
            cites[cited] = (state, hits)
            if state in {"exact", "basename-unique"}:
                coords.append((hits[0], start, end))
            elif state == "basename-multi":
                for hit in hits:
                    coords.append((hit, start, end))
        docs[name] = {
            "file": str(path.relative_to(repo)),
            "doc_sha": meta.group(1) if meta else "",
            "doc_date": date.group(1) if date else "",
            "token": name,
            "coords": coords,
            "cites": cites,
        }
    return docs


def cli_docs(repo: pathlib.Path, tree: StrataTree) -> dict[str, dict[str, object]]:
    """docs/cli の文書を索引リンクから {相対パス: {...}} にする。"""
    index_path = repo / CLI_DIR / CLI_INDEX
    linked: list[str] = []
    if index_path.is_file():
        for line in index_path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = CLI_LINK_RE.match(line)
            if match:
                linked.append(match.group(2))
    docs: dict[str, dict[str, object]] = {}
    for rel in linked:
        path = repo / CLI_DIR / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        meta = META_RE.search(text)
        date = DATE_RE.search(text)
        parts = pathlib.PurePosixPath(rel).parts
        option = parts[-1]
        if option.endswith(".md"):
            option = option[:-3]
        if option == "README":
            option = ""
        coords: list[tuple[str, int, int]] = []
        cites: dict[str, tuple[str, list[str]]] = {}
        for match in COORD_RE.finditer(text):
            cited = match.group(1)
            start = int(match.group(2))
            end = int(match.group(3) or match.group(2))
            state, hits = tree.resolve(cited)
            cites[cited] = (state, hits)
            if state in {"exact", "basename-unique"}:
                coords.append((hits[0], start, end))
            elif state == "basename-multi":
                for hit in hits:
                    coords.append((hit, start, end))
        docs[rel] = {
            "file": str(path.relative_to(repo)),
            "doc_sha": meta.group(1) if meta else "",
            "doc_date": date.group(1) if date else "",
            "token": option,
            "tool_id": parts[0] if parts else "",
            "command_path": "/".join(parts[1:-1]) if len(parts) > 2 else "",
            "coords": coords,
            "cites": cites,
        }
    return docs


def build_evidence(
    repo: pathlib.Path,
    strata: pathlib.Path,
    revision: str,
    scope: str = "all",
) -> dict[str, object]:
    """証拠台帳の dict を作る（evidence-index.py と find-stale.py 共通）。"""
    tree = StrataTree(strata, revision)
    payload: dict[str, object] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "strata_root": str(strata),
        "revision": revision,
    }
    if scope in {"all", "envvars"}:
        payload["envvars"] = envvar_docs(repo, tree)
    if scope in {"all", "cli"}:
        payload["cli"] = cli_docs(repo, tree)
    return payload


def all_doc_files(docs: Iterable[dict[str, object]]) -> list[str]:
    paths: set[str] = set()
    for doc in docs:
        for path, _, _ in doc["coords"]:  # type: ignore[attr-defined]
            paths.add(path)
    return sorted(paths)


def doc_cite_files(doc: dict[str, object]) -> list[str]:
    return sorted({path for path, _, _ in doc["coords"]})  # type: ignore[attr-defined]
