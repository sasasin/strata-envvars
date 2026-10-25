# `strata update --app-version`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--app-version` |
| 別名 | なし |
| 値 | インストール済み Strata Desktop の version 文字列 |

## 役割

`strata update` が把握している Strata Desktop のインストール済み version を渡します。署名付き update feed の Desktop version と比較し、`--check` の結果や `--app` による installer 取得の要否を決めるために使われます。Terminal CLI や Control の version を指定するオプションではありません（`strata_cli/update_cmd.py:47,163-184`、`strata_control/updater.py:1210-1223`）。

## 使い方

```sh
# Desktop の更新状況だけを確認する（feed の取得は行う）
strata update --check --app-version 0.2.0

# エンジンと Control に加え、Desktop installer も取得・検証する
strata update --app --app-version 0.2.0
```

## 値と既定値

- parser は文字列を受け取り、既定値は `None` です。parser 自体では形式検証しません（`strata_cli/update_cmd.py:42-48`）。
- オプションを省略した場合は環境変数 `STRATA_APP_VERSION` を使います。明示値が空文字列の場合も Python の `or` によって環境変数へフォールバックします。明示した空でない値は環境変数より優先されます（`strata_cli/update_cmd.py:27,182-184`）。
- 比較時の version は `0.2.0`、`0.2.0.1` のように数字3要素と任意の第4要素を持つ形式です。インストール済み version には `0.2.0-beta` のような prerelease suffix も許され、同じ数値部分の通常 version より低く並びます。suffix 内の文字列による大小順までは比較しません（`strata_control/feed.py:40,59-72`）。
- 指定値の空白除去や補正はありません。形式が不正な値は、Desktop の feed entry と当該 platform 用 entry がある場合に比較時点で `FeedError` になります（`strata_control/updater.py:1210-1223`、`strata_control/feed.py:59-72`）。

## 実行時の動作

`strata update --check` は feed を読み、エンジン・Control・Desktop の更新状況を常に報告します。Desktop の現行 version が不明なら status は `unknown-installed`、feed の version が現行値より新しければ `available`、それ以外は `current` です。`--check` は `--app` の有無にかかわらず Desktop を報告します。feed の取得後には check 結果の一部を状態ファイルへ保存します（`strata_control/updater.py:624-640,1210-1223`）。

通常の更新では `--app` を付けたときだけ Desktop installer の取得処理が加わります。`--app-version` は `--app` の代わりにはならず、このフラグだけで installer を取得しません。比較結果が `current`、feed に Desktop がない、または当該 platform 向け entry がない場合、installer は取得されません。`available` または version 不明の場合は installer をダウンロードして SHA-256 と minisign signature を検証し、components directory の `.updates/app` に保存します。CLI は installer を実行しません（`strata_control/updater.py:1226-1257,1274-1288`）。

同じ `--app-version` は `strata components update` の parser にも登録されていますが、この文書の対象 scope は索引に従い `strata update` です（`strata_cli/update_cmd.py:42-59`、[`CLI 索引`](../../README.md)）。

## 適用条件と副作用

- Desktop の version 比較は feed に Desktop entry があり、かつ現在の PC に対応する platform entry がある場合にだけ行われます。該当 entry がなければ `--app-version` の値はその判定で使われません（`strata_control/updater.py:1210-1223`）。
- version 不明の状態で `--app` を指定すると、更新済みかどうか判定できないため取得・検証処理へ進みます。version が `current` なら取得を省略します（`strata_control/updater.py:1230-1234`）。
- `--check` は feed 以外をダウンロードしませんが、最後の check 情報を update state に保存します。通常の update では feed と選択された component を取得します（`strata_control/updater.py:624-640,1274-1285`）。
- `strata update` と `strata components update` は、更新がエンジンを利用中の場合に待機・拒否となることがあり、取得処理は `STRATA_NO_ACQUIRE` により拒否されることがあります。これらは `--app-version` 固有の副作用ではありません（`strata_cli/update_cmd.py:9-11,197-210,237-252`）。

## 出力とエラー

- `--check` の人向け出力では Desktop のインストール済み version と提示 version、status が表示されます。JSON/JSONL 出力では同じ Desktop 判定が `app` レポートに含まれます（`strata_cli/update_cmd.py:132-160,163-209`、`strata_control/updater.py:1210-1223`）。
- 不正な version 文字列や feed エラーは `FeedError` として処理され、既定の終了コードは 5 です。人向け出力は stderr の `strata: ...`、JSON/JSONL 指定時はエラー object を stdout に出します（`strata_control/feed.py:44-49,59-72`、`strata_cli/update_cmd.py:163-172,225-234`）。
- `--app` で公開鍵がなく installer を検証できない場合や signature 検証に失敗した場合も、終了コード 5 で失敗します。signature 不一致の installer archive は削除されます（`strata_control/updater.py:1235-1249`）。

## 根拠

- `strata_cli/update_cmd.py:42-59` — `strata update` と `strata components update` の parser 定義。
- `strata_cli/update_cmd.py:163-184,197-234` — 環境変数との優先関係、check/update 分岐、エラー・終了コード処理。
- `strata_control/updater.py:624-640,1210-1257,1274-1296` — Desktop version 判定、check state 保存、installer 取得条件と副作用。
- `strata_control/feed.py:40,59-72,243-260` — version 形式・比較方法と feed 内 Desktop version の検証。
- 索引: [`docs/cli/README.md`](../../README.md) の `strata update` scope。
