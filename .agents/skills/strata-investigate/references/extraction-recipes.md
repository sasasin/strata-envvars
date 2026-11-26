# 情報抽出の技

Strata checkout を読むときの検索語と機械抽出。索引更新（`index-refresh.md`）と 1 件調査（D/E モード）で使う。
Strata 側の絶対パスは `STRATA=$HOME/src/github.com/Niko1221/Strata` として書く。

**どの節でも Strata の top-level 階層名を書き置かない。** 階層は Release で作り替わる。
対象を決めるときは必ず `git -C "$STRATA" ls-files` から現在の入口階層を導いてから読む。

```bash
git -C "$STRATA" ls-files | cut -d/ -f1 | sort | uniq -c | sort -rn   # 現在の入口階層
```

## 1. 環境変数の全参照を出す

```bash
rg -n --hidden --glob '!.git/**' 'NAME' "$STRATA"
```

名前の完全一致だけでは helper 経由と動的な名前を落としやすい。読み取り API 側も併せて引く。

```bash
rg -n --hidden \
  -g '!.git/**' -g '!**/docs/**' -g '!**/bench/results/**' -g '!**/data/**' -g '!**/ref/**' -g '!**/third_party/**' \
  'std::getenv|getenv\(|_wgetenv|setenv|putenv|_putenv_s|unsetenv|env::var|os\.environ|os\.getenv|process\.env|Deno\.env|env_on|_timeout_env' \
  "$STRATA"
```

除外は末尾一致（`!**/third_party/**`）で掛ける。checkout 全体を引くようにしておけば、top-level が
どの階層に組み替わっても対象が変わらない。`"$STRATA"/src` のように階層を名指しすると、
消えたパスを rg はエラーだけ出して続行し、対象が大幅に減ったまま進行する。

helper が見つかったら、その helper の**全呼び出し箇所**も追う（定義だけで判断しない）。
CMake / Docker / CI 側は `$ENV{NAME}`、`ENV NAME=`、`environment:` のキー、`${NAME}`、`${{ env.NAME }}`。
既定値テーブル `{"STRATA_X", "1"}` や `setenv("X=" + v)` で名前が決まるものも拾う。

読み取り方の変換規則は該当箇所のコードを読む: `getenv(...) != nullptr`（設定有無）、`e[0] == '1'`（先頭文字）、
`atoi` / `atof` / `strtol` / `sscanf`（全体 parse か後ろ無視か）、文字列全体の比較、大文字小文字の別。

## 2. 変更範囲だけを拾う（索引更新）

前回索引に書いた commit SHA を `<prev>` として、入口まわりだけを眺める。`<prev>` の時点と HEAD で
top-level が違うことがあるので、**パス名を書かず diff の絞り込み方で見る**。

```bash
git -C "$STRATA" diff --name-status --diff-filter=AMD -M <prev>..HEAD   # 増えた / 消えた / 書かれたもの
git -C "$STRATA" ls-files | grep -E '\.(sh|bash|bat|cmd|ps1|py|js|mjs|c|cc|cpp)$'
```

`R` が大量に出たら top-level の作り替え。移動先階層の件数だけ数えて、§1・§3・§5 で読む場所を現行に
切り替える（索引更新で見るのは入口の増減なので、rename の全行を流し読まない）。

```bash
git -C "$STRATA" diff --name-status --diff-filter=R -M <prev>..HEAD \
  | awk -F'\t' '$2 != $3 {print $3}' | cut -d/ -f1 | sort | uniq -c | sort -rn
```

## 3. CLI grammar を機械抽出する（索引の網羅性照合）

Python argparse（Terminal CLI、`terminal/setup.py`、`terminal/tools/strata_bench.py`）:

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
`terminal/strata_cli/cli.py` は登録済みの module parser に後から共通 option（`--json` / `--quiet` など）を足すため、
同一 revision の CLI を import して `parser()` を呼び、`_actions` と `_SubParsersAction.choices` を再帰 walk して
最終 grammar を出すのが確実（索引との diff 取りに使う）。

C/C++ エンジンと単体 CLI（parser の所在は `rg -l 'argv\[i\]|std::strcmp\(argv\[' "$STRATA"` や
`add_executable` を持つファイルから毎回導く。この節に階層名を書き置かない）:

```bash
rg -n --hidden -g '!.git/**' -g '!**/third_party/**' -g '!**/docs/**' '"--[a-z0-9-]+"' "$STRATA"
rg -n --hidden -g '!.git/**' -g '!**/third_party/**' 'std::strcmp\(argv\[|a == "--|argv\[i\] == "--' "$STRATA"
```

alias（`|| a == "-h"`）と、`--version` / `-V` / `--families` / `--gpu` のような早期処理フラグを見落とさない。
CMake 生成対象は `add_executable` の場所と条件ブロック（`option(...)`、backend guard、`NOT STRATA_HIP_GFX906` など）から読む。
`CMakeLists.txt` の所在も名指しせず列挙して決める（`third_party` を含むパスはベンダーコピーなので落とす）。

```bash
git -C "$STRATA" grep -l 'add_executable' -- '*CMakeLists.txt' | grep -v 'third_party/'
```

索引更新のたびに、この抽出結果の要として option 文字列 inventory を保存する（`scripts/cli-grammar.py` →
`.cli-grammar.json`）。`find-stale.py` の S-c（既存 CLI 文書の option が現行 parser から消えたか）がこれを使う。

## 4. 索引 ↔ 実ファイルの突合

自前で見積もらず `scripts/check-docs.py` を使う。件数サマリ、未作成一覧（`--list-missing`）、
孤児・綴り不一致・並び順違反・概要リンク欠落・SHA/調査日欠落、commit 別分布（`--stale`）を出す。

## 5. 環境変数一覧（`docs/envvars/000_envvers.md`）の生成範囲

索引の再生成はこの節が正。索引ファイル自身には生成方法・内訳・差分・履歴を書かない（`index-refresh.md` §1）。

ソースを grep し、環境変数を実際に読み書きしている箇所から名前を拾う。同じ名前の全参照を集約し、
環境変数ではない識別子（文字列定数・ログ文言・量子化形式名・シグナル名・テスト内のダミー）は落とす。

検索する API / 構文:

- C/C++/CUDA/HIP/SYCL/Metal/Rust: `std::getenv` / `getenv` / `_wgetenv` / `setenv` / `putenv` / `_putenv_s` / `unsetenv` / `std::env::var` / `std::env::var_os`
- Python: `os.environ[...]` / `os.environ.get` / `os.environ.setdefault` / `os.environ.pop` / `os.getenv` / 名前を引数に取る env helper（呼び出し側で解決）
- JavaScript / TypeScript: `process.env.NAME` / `process.env["NAME"]` / `Deno.env.get`
- shell / batch / PowerShell: スクリプト内で代入されずに環境から読む `$NAME` / `${NAME:-既定}` / `${NAME:?必須}` / `%NAME%` / `$env:NAME`。bat の `if defined NAME` と `if "%NAME%"==""` も読み取りとして数える。`eval "v=\${$legacy:-}"` のような間接参照も追う
- CMake / Docker / Compose / GitHub Actions: `$ENV{...}` / `ENV 変数=` / `environment:` のキーと `${VAR}` 参照 / `${{ env.VAR }}` / workflow の `env:` キー
- NSIS インストーラ: `SetEnvironmentVariableW` で環境に書き込む名前

名前が間接的に決まるものも拾う: 既定値テーブル（`{"STRATA_X", "1"}`）、`push_back({"STRATA_X", "2"})`、
子プロセスへの `setenv("X=" + v)`、Python / JS の env dict の key、getenv へ渡す名前の配列
（`for (const char* k : {"FNX_PF_SKIP", ...})`）、定数名経由（`ENV_CHECKOUT = "STRATA_HANDOVER_IN_CHECKOUT"`）。
`getenv` に identifier を渡す helper（`env_on` / `env_int` / `env_flag` / `pipe_dbg_env` / `bm_default_on` /
`strata_metal::resource` など）はソースから毎回割り出し、その呼び出し引数も検索対象にする。

除外するもの: コメント・ドキュメント・ビルド用 `#define`・CMake 変数（`STRATA_PORTABLE` など）・Dockerfile の `ARG` だけの名前・
コマンドライン引数名・量子化形式名・ファイルヘッダの magic 文字列・shell 内蔵変数（`PWD` `RANDOM` `PIPESTATUS`
`ERRORLEVEL` `BASH_SOURCE` `BASH_REMATCH`）・スクリプトが自分で代入するだけの内部変数・テスト内のダミー文字列。

対象外: 追跡ファイルのうち、パスのどこかに `docs/` `bench/results/` `data/` `ref/` `third_party/` を含む場所。
除外は**末尾一致で書く**（`rg -g '!**/third_party/**'`、`git grep -- ':(exclude,glob)**/third_party/**'`）。
top-level 固定の名前だと階層の移動に追随せず、ベンダーコピーが候補に混入する。
見る場所: `git -C "$STRATA" ls-files` の追跡ファイル全部（上の対象外を除く）。索引再生成のたびに
入口階層と直下のスクリプト入口を Strata から導いて読む。

```bash
git -C "$STRATA" ls-files | cut -d/ -f1 | sort -u   # 入口階層
git -C "$STRATA" ls-files | awk -F/ 'NF == 1'       # 直下ファイル
```
検索する拡張子: `.c .cc .cpp .cxx .h .hpp .hxx .cu .cuh .metal .rs .mm .m .inc .cppm .tpp .nsi .py .js .mjs .cjs .ts .tsx .jsx .sh .bash .zsh .bat .cmd .ps1 .psm1 .yml .yaml .cmake .txt`。

綴りは Strata が実際に読む形のまま載せる（`Path` `SystemDrive` `VCToolsRedistDir` など）。例外として
`SystemRoot` は `SYSTEMROOT` に正規化し、大文字形と小文字形を両方読む proxy 系（`HTTPS_PROXY` / `https_proxy` など）は大文字形に寄せる。
`PATH` と `Path` のように両綴りの本文が別にある名前はそれぞれ載せる。

テスト・開発/e2e・parity・bench・probe スクリプトだけが読む名前も索引には載せる（索引は候補一覧。本文を作るかは `runner.md` の no-doc 判定で決める）。
