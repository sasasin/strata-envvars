# codex / pi に投げる依頼文

`README.md` に置いてあったプロンプト集の最新版。パスは実体（`docs/envvars/…`、`docs/cli/…`）に直してある。
索引の中身に関する指示は `docs/` 側の「更新手順と次回の調査指示」節を参照する形に統一した。
ファイル名は `000_envvers.md`（綴りは envvars ではない）が実在名なので、そのまま使う。

## 環境変数一覧の再生成

```bash
codex exec --skip-git-repo-check --sandbox 'workspace-write' '
調査依頼です。調査対象ソースコードは `$HOME/src/github.com/Niko1221/Strata` です。
ソースコードを網羅的に grep して、使用可能な環境変数を一覧化しただけの Markdown ファイルを作成してください。
Markdown ファイル名は `$HOME/src/github.com/sasasin/strata-envvars/docs/envvars/000_envvers.md` としてください。
環境変数名でソートしてください。冒頭の生成方法・検索した API・除外条件の記述形式は既存ファイルを維持し、
1 行 1 名の一覧形式（`- ` 始まりのバッククォート付き）を崩さないでください。'
```

## 消えた環境変数の本文削除

索引更新後は `references/prune.md` §1 が手順の正。codex にやらせる場合:

```bash
codex exec --skip-git-repo-check --sandbox 'workspace-write' '
`$HOME/src/github.com/sasasin/strata-envvars/docs/envvars/000_envvers.md` の git diff にもとづいて、
削除された環境変数に対応する docs/envvars/${環境変数名}.md を削除してください。
削除の前に、現行 Strata checkout でその名前が実際に読まれなくなったことを rg で確認してください。
まだ読み取り箇所がある場合は削除せず、索引の落ち度として報告してください。'
```

## CLI 入口・配布物一覧の更新

```bash
codex exec --skip-git-repo-check --sandbox 'workspace-write' '
調査依頼です。Strata ソースコードが更新されたので、
`$HOME/src/github.com/sasasin/strata-envvars/docs/cli/000_cli_tools.md` の「更新手順と次回の調査指示」に従って、
`$HOME/src/github.com/Niko1221/Strata` を調査し、`000_cli_tools.md` を最新の内容に更新してください。
CLI 入口、ビルド生成物、GitHub Release の配布物、ファイル名、インストール先を根拠となるソースから確認し、
現行 Release の実体を確認できない項目は推測で埋めず、その制約を記載してください。'
```

## CLI 索引の更新

```bash
codex exec --skip-git-repo-check --sandbox 'workspace-write' '
Strata ソースコードが更新されたので、
`$HOME/src/github.com/sasasin/strata-envvars/docs/cli/README.md` の「更新手順と次回の調査指示」に従って、
`$HOME/src/github.com/Niko1221/Strata` を調査し、`docs/cli/README.md` を最新の内容に更新してください。
全 CLI tool-id とコマンド階層、各 parser のオプションと alias、条件付き engine parser、CMake 生成の対象 CLI を確認してください。
全コマンドに `README.md` の概要リンクを置き、各コマンド節では概要リンクを先頭、その後のオプションを ASCII コード順にしてください。
オプション文書と概要ページが未作成の場合も、規約どおりの Markdown 予定リンクとして列挙し、
現行 Release を確認できない内容は推測で補わないでください。'
```

## 環境変数 1 件

通常は `uv run ./create-envvars-docs.py -l 1`（`PROMPT_TEMPLATE` が手順を組み立てる）。
手で行う／他のエージェントに頼む場合は:

```bash
codex exec --skip-git-repo-check --sandbox 'workspace-write' \
  --cd "$HOME/src/github.com/sasasin/strata-envvars" '
調査依頼です。Strata の環境変数 1 個について調査文書を作成してください。
調査対象ソースコード: `$HOME/src/github.com/Niko1221/Strata`
対象環境変数: `STRATA_XXXX`
作成対象文書: `$HOME/src/github.com/sasasin/strata-envvars/docs/envvars/STRATA_XXXX.md`
`docs/envvars/001_investigation.md` の調査範囲・手法・文書フォーマット・品質基準に従ってください。
書式と詳しさの基準文書は `docs/envvars/STRATA_ADAPT_OVERLAP.md` です。
Strata が実際には読まない名前なら、空の文書を作らず索引との食い違いとして報告してください。
索引・001_investigation.md・他の文書・Strata ソースは変更しないでください。'
```

## CLI 文書 1 件

通常は `uv run ./create-cli-docs.py -l 1`。索引に決めた予定パス 1 件を指定して投げる場合は
`create-cli-docs.py` の `PROMPT_TEMPLATE` と同じ手順（配置規約は `docs/cli/001_investigation.md`、
コマンド概要の基準は `docs/cli/strata-terminal/launch/README.md`）に従う。

## 速度改善に効く設定を相談する（G モード）

このリポジトリの md を材料に、Strata の prefill / decode を速める設定を出させる依頼文（`README.md` 由来）。

> このパソコンには AMD Radeon AI PRO R9700 を1枚だけ挿してあり、推論エンジン Strata の GPU として利用しています。
> Strata の実行には run-iq2_xs.sh を用いています。prefill や decode の高速化のため、
> どのようなコマンドラインオプションや環境変数を利用できるか、Strata ソースコードを詳しく読解して、
> いくつか提案してください

提案された項目の裏取りは `docs/envvars/<NAME>.md` と `docs/cli/**` を読む。
この依頼は Strata ソースの読解なので、`principles.md` の「実行してよいこと」の範囲に収める
（提案の実適用・ベンチマークはユーザーが明示的に依頼した場合だけ）。
