# 情報抽出の技

Strata checkout を読むときの検索語と機械抽出。索引更新（`index-refresh.md`）と 1 件調査（D/E モード）で使う。
Strata 側の絶対パスは `STRATA=$HOME/src/github.com/Niko1221/Strata` として書く。

## 1. 環境変数の全参照を出す

```bash
rg -n --hidden --glob '!.git/**' 'NAME' "$STRATA"
```

名前の完全一致だけでは helper 経由と動的な名前を落としやすい。読み取り API 側も併せて引く。

```bash
rg -n --hidden --glob '!.git/**' \
  'std::getenv|getenv\(|_wgetenv|setenv|putenv|_putenv_s|unsetenv|env::var|os\.environ|os\.getenv|process\.env|Deno\.env|env_on|_timeout_env' \
  "$STRATA"/src "$STRATA"/include "$STRATA"/sycl "$STRATA"/metal "$STRATA"/serve \
  "$STRATA"/strata_cli "$STRATA"/strata_control "$STRATA"/tools "$STRATA"/apps \
  "$STRATA"/packaging "$STRATA"/docker "$STRATA"/spark "$STRATA"/bin "$STRATA"/cmake "$STRATA"/.github \
  "$STRATA"/setup.py "$STRATA"/setup.sh "$STRATA"/CMakeLists.txt "$STRATA"/Dockerfile
```

helper が見つかったら、その helper の**全呼び出し箇所**も追う（定義だけで判断しない）。
CMake / Docker / CI 側は `$ENV{NAME}`、`ENV NAME=`、`environment:` のキー、`${NAME}`、`${{ env.NAME }}`。
既定値テーブル `{"STRATA_X", "1"}` や `setenv("X=" + v)` で名前が決まるものも拾う。

読み取り方の変換規則は該当箇所のコードを読む: `getenv(...) != nullptr`（設定有無）、`e[0] == '1'`（先頭文字）、
`atoi` / `atof` / `strtol` / `sscanf`（全体 parse か後ろ無視か）、文字列全体の比較、大文字小文字の別。

## 2. 変更範囲だけを拾う（索引更新）

前回索引に書いた commit SHA を `<prev>` として、入口・配布物だけを眺める。

```bash
git -C "$STRATA" diff --name-status <prev>..HEAD -- packaging/ bin/ docker/ spark/ apps/desktop/ docs/ .
git -C "$STRATA" ls-files | grep -E '\.(sh|bash|bat|cmd|ps1|py|js|mjs|c|cc|cpp)$'
```

`git describe --tags` と `git log <tag>..HEAD` で tag と HEAD が同一コミットかを見る（Release とソースの対応の根拠）。

## 3. CLI grammar を機械抽出する（索引の網羅性照合）

Python argparse（Terminal CLI、`setup.py`、`tools/strata_bench.py`）:

```bash
python3 - <<'PY'
import ast, pathlib
root = pathlib.Path.home() / "src/github.com/Niko1221/Strata"
for f in list(root.rglob("*.py")):
    try:
        tree = ast.parse(f.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "add_argument":
            for a in n.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.startswith("-"):
                    print(f"{f.relative_to(root)}:{n.lineno}: {a.value}")
PY
```

`help=argparse.SUPPRESS` で `--help` に出ない option もこれで拾える。
`strata_cli/cli.py` は登録済みの module parser に後から共通 option（`--json` / `--quiet` など）を足すため、
同一 revision の CLI を import して `parser()` を呼び、`_actions` と `_SubParsersAction.choices` を再帰 walk して
最終 grammar を出すのが確実（索引との diff 取りに使う）。

C/C++ エンジンと単体 CLI（`src/program/generate.cpp`、`src/qwen35/q36_engine.cu`、`src/dsv41/ds4_main.cpp`、
`src/plan/plan_main.cpp` など）:

```bash
rg -n --hidden '"--[a-z0-9-]+"' "$STRATA"/src "$STRATA"/sycl "$STRATA"/metal "$STRATA"/tools
rg -n 'std::strcmp\(argv\[|a == "--|argv\[i\] == "--' "$STRATA"/src
```

alias（`|| a == "-h"`）と、`--version` / `-V` / `--families` / `--gpu` のような早期処理フラグを見落とさない。
CMake 生成対象は `add_executable` の場所と条件ブロック（`option(...)`、backend guard、`NOT STRATA_HIP_GFX906` など）を
`CMakeLists.txt`、`sycl/CMakeLists.txt`、`metal/CMakeLists.txt`、`tools/vision/CMakeLists.txt` から読む。

## 4. Release と配布物の実体

```bash
curl -fsSL https://api.github.com/repos/Niko1221/Strata/releases/latest
curl -fsSL 'https://api.github.com/repos/Niko1221/Strata/releases?per_page=15'
```

- asset の `digest` と `name`・サイズを一覧化し、`install-manifest.txt` / `latest.json` / `SHA256SUMS.txt` /
  `strata-feed.json` / `strata-feed-linux-aarch64.json` / `install.sh` / `install.ps1` は本文を取れる。
- 小さな asset（macOS の engine package、`strata-dsv41-*-metal.tar.gz`、macOS の Control archive、
  `Strata.app.tar.gz`）は展開して中身とハッシュを確認すると、archive 内の実行ファイル名や
  `engine-bundle/` のフォルダ名まで実証できる。大きな Windows/Linux archive は未取得のまま制約として書く。
- Docker: `https://ghcr.io/v2/niko1221/strata/tags/list`（anonymous token 付き）で tag 実体を確認する。
- ネットワークで確認できなかった項目は、ソース上の生成規則を実配布物として断定しない。

## 5. 索引 ↔ 実ファイルの突合

自前で見積もらず `scripts/check-docs.py` を使う。件数サマリ、未作成一覧（`--list-missing`）、
孤児・綴り不一致・並び順違反・概要リンク欠落・SHA/調査日欠落、commit 別分布（`--stale`）を出す。
