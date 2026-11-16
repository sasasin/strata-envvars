---
name: strata-investigate
description: |
  strata-envvars リポジトリの調査・更新運用。Strata のリリースや checkout 更新後に、環境変数一覧
  (docs/envvars/000_envvers.md) と CLI ツール一覧・索引 (docs/cli/000_cli_tools.md、docs/cli/README.md) を
  最新化し、増減に合わせて docs/envvars/<NAME>.md と
  docs/cli/<tool-id>/<command-path>/<option>.md を 1 件 1 セッションで作成・削除する。
  create-envvars-docs.py / create-cli-docs.py の並列実行と飽和判定、索引と実ファイルの突合
  (scripts/check-docs.py)、既存文書の陳腐化検出と再作成 (scripts/cli-grammar.py、
  evidence-index.py、find-stale.py、mark-stale.py) も扱う。
  以下で使用:「Strata が更新された」「環境変数一覧を最新化して」「この環境変数の調査文書を作って」
  「CLI オプションの文書を作って」「未作成の文書をまとめて作る」
  「消えた環境変数・コマンドの md を消して」「docs が追従しているか点検して」
  「既存文書が古くなっていないか調べたい」「Strata を速くする環境変数を提案して」
  以下には使用しない: Strata 本体のコード変更・build・GPU 実行・性能測定・テスト追加
  （調査では行わない）／ Strata 以外のリポジトリの調査 ／ 既にある文書の要約や解説を書くこと。
---

# Strata 調査文書の更新 runbook

Strata ソースコード（作業開始時点の checkout）だけを一次情報にして、このリポジトリの `docs/` を最新のソースに追従させる手順。GitHub Release の配布物は調査対象にも根拠にもしない。
**詳細な調査仕様は `docs/` 側の文書が正**であり、本書は「どの順序で・何を読み・何を叩くか」だけを定める。

## 前提の絶対パス

| 役割 | パス |
| --- | --- |
| 調査対象の Strata checkout | `$HOME/src/github.com/Niko1221/Strata` |
| 環境変数文書 | `$HOME/src/github.com/sasasin/strata-envvars/docs/envvars/` |
| CLI 文書 | `$HOME/src/github.com/sasasin/strata-envvars/docs/cli/` |

Strata 側を最新化してから始める。

```bash
git -C "$HOME/src/github.com/Niko1221/Strata" pull --ff-only
git -C "$HOME/src/github.com/Niko1221/Strata" rev-parse HEAD
git -C "$HOME/src/github.com/Niko1221/Strata" describe --tags
```

## 共通原則（どのモードでも）

1. 作業前に Strata の `git rev-parse HEAD` と `git status --short --branch` を取る。各文書に完全な commit SHA と調査日を書く。異なる commit の調査を 1 文書に混ぜない。
2. 根拠は Strata 所有ソースの `path:line`。コメント・docs・索引の名前だけ・外部ライブラリや driver の挙動から現在の動作を決めない。
3. 確認できない点は推測で埋めず、制約として書く。索引との食い違いは報告し、存在しない項目の文書を作らない。
4. Strata ソースを変更しない。build・GPU 実行・性能測定・テストの追加実行は依頼があるまでやらない。
5. 1 セッションで編集するのは指定された 1 ファイルだけ。索引や他文書は書き換えない（索引更新モードでは逆に、索引だけを更新し本文は作らない）。
6. 完全な原則と不変条件は `references/principles.md`。

## モード選択

| 依頼 | モード | 読むもの |
| --- | --- | --- |
| Strata のリリースが来た／一覧が古い | A 索引の最新化 | `references/index-refresh.md` |
| 索引から消えた項目の後始末 | B 削除（prune） | `references/prune.md` |
| 未作成の envvars / CLI 文書をまとめて作る | C 一括作成 | `references/runner.md` |
| 環境変数 1 個を調べてほしい | D envvars 1 件 | `docs/envvars/001_investigation.md` + `assets/envvar-doc.md` |
| CLI のオプション 1 個を調べてほしい | E CLI 1 件 | `docs/cli/001_investigation.md` + `assets/cli-option-doc.md`（概要なら `assets/cli-command-readme.md`） |
| 追従状況・リンク切れ・重複を点検 | F 突合 | `scripts/check-docs.py` |
| 既存文書の中身が古くなっていないか | H 陳腐化検出 | `references/staleness.md` |
| 速度改善に効く変数を相談したい | G 提案セッション | `references/prompts.md` の依頼文 |

どのモードでも、コードからの情報抽出は `references/extraction-recipes.md` の検索語・抽出技を使う。

## A. 索引の最新化（リリース追従の入口）

1. `docs/envvars/000_envvers.md`（環境変数一覧）を再生成する。
2. `docs/cli/000_cli_tools.md`（CLI ツール一覧。tool-id と parser の所在）を更新する。
3. `docs/cli/README.md`（CLI 索引）を更新する。
4. 更新後に F（突合）を走らせ、増減件数を確認する。
5. 減った項目は B に進み、増えた項目は C に進む。

各索引の更新手順と、索引に書いてよい中身は `references/index-refresh.md` が正（環境変数一覧の生成範囲は `references/extraction-recipes.md` §5）。索引 3 ファイルには調査対象行と一覧だけを置き、手順・依頼文・差分・履歴・Release の実測値は書かない。索引は**予定リンクを含んだ一覧**であって、この段階で個別文書は作らない。

CLI 索引を更新したときは option inventory も再生成する（`scripts/cli-grammar.py`）。H の陳腐化検出 (S-c) がこれを使う。

## H. 陳腐化検出（索引更新の直後に回す）

```bash
python3 .agents/skills/strata-investigate/scripts/cli-grammar.py       # option inventory
python3 .agents/skills/strata-investigate/scripts/evidence-index.py    # 証拠台帳
python3 .agents/skills/strata-investigate/scripts/find-stale.py --stage3
python3 .agents/skills/strata-investigate/scripts/mark-stale.py --limit 20          # dry-run
python3 .agents/skills/strata-investigate/scripts/mark-stale.py --apply --limit 20  # 削除
uv run ./create-envvars-docs.py -p 5 -l 20                                          # 再作成
uv run ./create-cli-docs.py -p 12 -l 40
python3 .agents/skills/strata-investigate/scripts/check-docs.py
```

要点は「文書が引用した行範囲が Strata 側で動いたか」（Stage 1）を見てから、「その差分に環境変数名・
option 文字列そのものが出るか」（Stage 2）で候補を絞ること。判定の意味と確度、安全弁は
`references/staleness.md`。削除した項目は索引に残したまま試行記録から消すと、既存の C（一括作成）がそのまま拾う。

2026-11-02 の一巡実測: 全走査（Stage 1/2/3）は約 3 秒。envvars の候補 13 件（`token-in-diff` 12 と
`unknown-sha` 1）を削除して再作成するのに 4 分 27 秒（5 並列、全件 created）。CLI は 115 件のうち
`--help` の 97 件を後回しにし、18 件を 2 分 42 秒で回した。この結果を受けて 2026-11-17 に
`--help` の文書自体を廃止した（索引に載せず作らない。`references/index-refresh.md` §3）ので、
現在は CLI の候補に `--help` は出ない。`moved` 判定の項目は削除しない（引用座標だけが古い）。

## B. 削除（prune）

索引との git diff から消えた名前・オプションを拾い、対応する本文だけを削除し、索引のリンク残骸を確認する。手順の本体は `references/prune.md`。

## C. 一括作成

```bash
cd "$HOME/src/github.com/sasasin/strata-envvars"
uv run ./create-envvars-docs.py --dry-run        # 対象を確認
uv run ./create-envvars-docs.py -p 5 -l 100      # envvars
uv run ./create-cli-docs.py -p 12 -l 100         # CLI
```

1 変数（1 オプション）= 1 codex セッション。CLI の `--help` は索引に載せないので作成されない。飽和判定・state ファイル・並列数の目安は `references/runner.md`。

## D / E. 1 件の調査

対象を 1 つ指定して実行する。D は `docs/envvars/001_investigation.md`、E は `docs/cli/001_investigation.md` の調査範囲・品質基準・配置規約にそのまま従う。文体と詳しさの基準は、D が `docs/envvars/001_investigation.md` の「文書フォーマット」「詳しさの基準」（特定の文書を手本にしない）、E のコマンド概要が `docs/cli/001_investigation.md` の「コマンド概要の内容」（同じく特定の文書を手本にしない）。雛形は `assets/` に置いた。

codex に投げる場合の依頼文は `references/prompts.md` にある。

## F. 突合チェック

```bash
python3 .agents/skills/strata-investigate/scripts/check-docs.py            # サマリ
python3 .agents/skills/strata-investigate/scripts/check-docs.py --stale    # 古い commit の文書
python3 .agents/skills/strata-investigate/scripts/check-docs.py --list-missing --strict
```

未作成・孤児・索引と綴りの違うファイル名・索引の並び順違反・コマンド節の概要リンク欠落・SHA/調査日の absence を報告する。終了コード 0 以外は何か問題がある意味（`--strict` 指定時）。

## 現状スコープ外

- 索引更新より前に陳腐化を先取りする運用（索引 SHA と Strata HEAD がずれた状態での判定）はしない。
- 差分に出ていない場所の記述が変わったケースは Stage 1/2 では拾えない。そういう項目は `file-only` /
  `hunk-intact` として残り、`--stage3` の所在追跡と option inventory で補助する。
- 性能測定のやり直しは依頼があるまで行わない（`references/principles.md`）。
