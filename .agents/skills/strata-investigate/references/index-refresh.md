# 索引 3 種の最新化

リリースが来るたびに、まず索引 3 ファイルを現在の checkout に合わせる。索引は**一覧**であり、
この作業で個別の環境変数・オプション文書は作らない（未作成でも予定パスを Markdown リンクで置く）。

| 索引 | 更新手順の本文（正） | skill 側の補足 |
| --- | --- | --- |
| `docs/envvars/000_envvers.md` | `extraction-recipes.md` §6（生成範囲。索引ファイル側には書かない） | 下記 §1 |
| `docs/cli/000_cli_tools.md` | 下記 §2（索引ファイル側には手順を書かない） | `extraction-recipes.md` §2・§3 |
| `docs/cli/README.md` | 下記 §3（索引ファイル側には手順を書かない） | `extraction-recipes.md` §3 |

3 ファイルとも**一覧だけ**を置く。生成方法・手順・依頼文・前回からの変化・履歴・Release の実測値は索引に書かない。
差分は `git diff` / `git log` で見て、説明が要るならコミットメッセージに書く。

更新順序は §1 → §2 → §3。§2 の tool-id 一覧が §3 の tool-id 集合を決める。

## 1. 環境変数一覧（`docs/envvars/000_envvers.md`）

- 索引は**一覧だけ**のファイルにする。中身は次の 3 つに限り、これ以外（生成方法・検索 API・除外条件・総数・内訳・前版との差分・履歴・運用メモ）は書かない。

  ```markdown
  # 環境変数一覧

  調査対象: Strata `main` の HEAD `<完全な commit SHA>`（`YYYY-MM-DD` 時点）。

  ## 環境変数

  - `NAME`
  ```

  `調査対象:` 行は `scripts/check-docs.py --stale` が基準 SHA として読む。一覧は 1 行 1 名の `- \`NAME\``（ASCII 順、重複なし）。この形を崩すと `create-envvars-docs.py` と `scripts/check-docs.py` が読めなくなる。
- 検索対象 API・除外条件・見る場所は `extraction-recipes.md` §6 が正。再生成時はその範囲で grep する。
- 前版との差分・件数は `git diff` / `git log` で見る（索引には書き残さない）。減った名前は `prune.md` §1、増えた名前は `runner.md` へ渡す。差分の説明が要るならコミットメッセージに書く。
- 環境変数名の大小が異なる同名（Windows の `PATH` と `Path` など）は索引では 1 名に正規化されることがある。ファイル名は Strata が実際に読む綴りを使うので、`check-docs.py` が「索引名と綴りの違うファイル」を出す場合はどちらの綴りがソース上の実綴りか確認して寄せる。

## 2. CLI ツール一覧（`docs/cli/000_cli_tools.md`）

- `docs/cli/<tool-id>/` を切る単位の一覧。envvars の `000_envvers.md` に相当し、`docs/cli/001_investigation.md` が tool-id の起点として読む。
- 中身は次に限る: 見出し、`調査対象:` 行（HEAD の完全な commit SHA と日付）、`## tool-id` 表（tool-id / 入口 / parser の所在 / scope）、`## 対象外`（入口と一行の理由）。
- 書かないもの: 設置先・配布経路・Release asset の名前・サイズ・digest、feed の中身、Docker の flavor、`add_executable` の件数、前回からの変化、調べたソース一覧、更新手順・依頼文。
- 更新時は Strata ルート・`bin/`・`packaging/`・`tools/`・`strata_cli/`・`src/`・各 `CMakeLists.txt` を見て、tool-id の追加・削除・改名と parser の所在を確かめる（`extraction-recipes.md` §2・§3）。名前だけで分類せず、呼び出し先と parser を読む。
- `*_test` / `*_parity` / `*_bench`、probe・harness、配布物を作る helper、CLI 引数を持たない installer は対象外に置く。対象外から tool-id に昇格させる場合は利用者・build target・parser を確認する。

## 3. CLI 索引（`docs/cli/README.md`）

- 中身は次に限る: 見出し、`調査対象:` 行、`## \`tool-id\``（グループ見出しも可）→ `### \`コマンド\`` → リンク行。リンクの無いコマンドは `- オプションなし（位置引数のみ）` のような 1 行だけ置いてよい。
- 書かないもの: 前置きの説明、対象境界（`000_cli_tools.md` に置く）、`### 索引更新 <日付>` のような履歴、inventory の件数、コマンド節の注記・根拠の行番号（コマンド概要 `README.md` に置く）、更新手順・依頼文。
- `調査対象:` 行は `check-docs.py`・`staleness_lib.py`・`cli-grammar.py`（`--revision` 既定）が基準 SHA として読む。見出しとリンク行の形は `create-cli-docs.py` と `check-docs.py` が読む。
- 各コマンド節は `- [コマンド概要](<tool-id>/<command-path>/README.md)` を先頭に 1 つ、その後 `- [\`--option\`（alias: \`-o\`）](<...>/--option.md)` を**表示される正規名の ASCII 順**（`--replica-profile` は `--replicas` より前）。
- 配置規約と一意性（`tool-id + command-path + option identity`）は `docs/cli/001_investigation.md` が正。ラッパーが委譲だけなら重複登録せず、委譲先が独自 parser を持つ場合は別 scope（例 `source-setup/mac/`、`strata-engine/qwen36/`）。
- 更新時は `strata_cli/cli.py` の root parser と各 module の登録 parser、`cli.py` が後から足す共通 option（`--json` / `--quiet` など）、C/C++ の手書き `argv` 解析と parser 前に処理される引数、`help=argparse.SUPPRESS` の option をたどる。
- 網羅性は機械照合する: parser 側から抽出した option 集合（`extraction-recipes.md` §3）と索引のリンク集合を突き合わせ、追加・削除・改名・alias 表記の漏れと重複を見る。
- 索引更新のたびに option inventory も保存する（陳腐化検出 S-c が使う）。

  ```bash
  python3 .agents/skills/strata-investigate/scripts/cli-grammar.py    # → .cli-grammar.json
  ```

## 更新後の自己点検

```bash
python3 .agents/skills/strata-investigate/scripts/check-docs.py
```

索引の並び順違反・概要リンクの欠落・孤児ファイル・リンク切れが 0 になることを確認する（`--strict` で終了コードでも確かめられる）。
