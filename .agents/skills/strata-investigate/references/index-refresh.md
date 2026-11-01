# 索引 3 種の最新化

リリースが来るたびに、まず索引 3 ファイルを現在の checkout に合わせる。索引は**一覧**であり、
この作業で個別の環境変数・オプション文書は作らない（未作成でも予定パスを Markdown リンクで置く）。

| 索引 | 更新手順の本文（正） | skill 側の補足 |
| --- | --- | --- |
| `docs/envvars/000_envvers.md` | 冒頭の「生成方法」節（検索した API / 構文の一覧） | 下記 §1 と `extraction-recipes.md` |
| `docs/cli/000_cli_tools.md` | 「更新手順と次回の調査指示」節（8 手順）＋「次回の依頼文」 | 下記 §2 |
| `docs/cli/README.md` | 「更新手順と次回の調査指示」節（8 手順）＋「次回の依頼文」 | 下記 §3 |

更新順序は §1 → §2 → §3。§2 の配布物・入口の一覧が §3 の tool-id 集合を決める。

## 1. 環境変数一覧（`docs/envvars/000_envvers.md`）

- 索引の形は 1 行 1 名の `- \`NAME\``（ASCII 順、重複なし）。冒頭に Strata の commit SHA・コミット日・一覧生成日・総数・生成方法・内訳を書く。この形式を崩すと `create-envvars-docs.py` と `scripts/check-docs.py` が読めなくなる。
- 検索対象 API と除外条件の完全な一覧は索引自身の冒頭に書いてある（C/C++/CUDA/HIP/SYCL/Metal/Rust、Python、JS/TS、shell/batch/PowerShell、CMake/Docker/Compose/GitHub Actions）。再生成時も同じ範囲で grep し、`bench/results/`、`docs/`、`data/`、`ref/`、`third_party/` を落とす。
- 既定値テーブル（`{"STRATA_X", "1"}`）や `setenv("X=" + v)` 経由の名前も拾う。コメント・docs・ビルド `#define`・コマンドライン引数名・CMake 変数・テスト内のダミー文字列は落とす。
- 前版との差分は `git diff` で見る。減った名前は `prune.md` §1、増えた名前は `runner.md` へ渡す。
- 環境変数名の大小が異なる同名（Windows の `PATH` と `Path` など）は索引では 1 名に正規化されることがある。ファイル名は Strata が実際に読む綴りを使うので、`check-docs.py` が「索引名と綴りの違うファイル」を出す場合はどちらの綴りがソース上の実綴りか確認して寄せる。

## 2. CLI 入口・配布物（`docs/cli/000_cli_tools.md`）

- 「利用者向け入口と設置先」表の 5 列（役割 / ソース上の入口 / 生成・配布経路 / 配布時の名前 / 主な設置・実行場所）を維持し、推測で埋めない列は「実体を確認できていない項目（推測しない）」節に回す。
- 「現行 GitHub Release の実物」節は Releases API の実測で更新する（tag、公開日、asset 名・サイズ・digest、`install-manifest.txt`、`latest.json`、`SHA256SUMS.txt`、feed JSON）。小さな asset は展開して中身とハッシュを確認する。`*.ps1` は `.gitattributes` で CRLF 化されるため、asset の SHA-256 は git オブジェクト（LF）側と比べる。
- 「直前の調査からの変化」節を追記し、「調査で確認した主なソース」と末尾の commit hash・調査日を更新する。
- CLI 引数の網羅はこのファイルではやらない（§3 と個別文書の仕事）。

## 3. CLI 索引（`docs/cli/README.md`）

- 冒頭に調査対象 commit SHA と調査日、`## 索引の対象境界` に各 tool-id の parser 所在を書く。
- `## \`tool-id\`` → `### \`コマンド\``（command path）→ `- [コマンド概要](<...>/README.md)` を節の先頭に 1 つ → `- [\`--option\`（alias: \`-o\`）](<...>/--option.md)` を**表示される正規名の ASCII 順**。
- 配置規約と一意性（`tool-id + command-path + option identity`）は `docs/cli/001_investigation.md` が正。ラッパーが委譲だけなら重複登録せず、委譲先が独自 parser を持つ場合は別 scope（例 `source-setup/mac/`、`strata-engine/qwen36/`）。
- 網羅性は機械照合する: parser 側から抽出した option 集合（`extraction-recipes.md` §3）と索引のリンク集合を突き合わせ、追加・削除・改名・alias 表記の漏れと重複を見る。
- Release installer（`install.sh` / `install.ps1`）は CLI 引数を持たないので option 文書を作らず、その事実を書く。

## 更新後の自己点検

```bash
python3 .agents/skills/strata-investigate/scripts/check-docs.py
```

索引の並び順違反・概要リンクの欠落・孤児ファイル・リンク切れが 0 になることを確認する（`--strict` で終了コードでも確かめられる）。
