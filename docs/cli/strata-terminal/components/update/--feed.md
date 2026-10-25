# `--feed`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update`（同じ実装を使う `strata update` にも存在） |
| オプション | `--feed` |
| 別名 | なし |
| 値 | URL、ディレクトリ、または feed ファイルのパス。値は必須。parser に型・選択肢の制約なし |

## 役割

更新情報を取得する署名付き feed の場所を指定します。feed には engine、Control、デスクトップアプリ installer などの配布情報が含まれ、実際にどのコンポーネントを更新するかは他のオプションと PC の状態で決まります。`strata components update` と `strata update` は同じ `_common` parser と実行関数を使います（`strata_cli/update_cmd.py:30-59, 163-165`）。

## 使い方

```sh
strata components update --feed https://updates.example.test/strata-feed.json --check
```

ディレクトリを指定する場合は、その中に `strata-feed.json` と `strata-feed.json.sig` が必要です。ファイルを直接指定すると、そのファイルと末尾に `.sig` を付けた署名ファイルを読みます（`strata_control/feed.py:342-360`）。

## 値と既定値

- `--feed` は値を一つ取ります。parser 自体は文字列をそのまま保持し、URL/path の形式検証は feed 取得時に行います（`strata_cli/update_cmd.py:30-32`）。
- 省略時は `STRATA_UPDATE_FEED`、コンポーネント状態ファイルに記録された前回の feed source、プロジェクト既定 URL の順で選びます。空文字列も falsy として扱われるため、実質的に省略時の選択へ進みます（`strata_cli/update_cmd.py:23-27, 87-95`）。
- プロジェクト既定 URL は `https://github.com/Niko1221/Strata/releases/latest/download/strata-feed.json` です（`strata_cli/update_cmd.py:23-25`）。
- URL が HTTP(S) で末尾が `.json` でなければ `/strata-feed.json` を補います。ローカルのディレクトリには `strata-feed.json` を補います（`strata_control/feed.py:347-353`）。

## 実行時の動作

指定 source から feed と署名ファイルを読み、信頼鍵による署名検証、feed schema の検査、有効期限と前回受理 sequence の検査を行います。信頼鍵がない場合や署名が正しくない場合は受け付けません（`strata_control/feed.py:312-339, 342-360`）。HTTP(S) feed の取得は各ファイル最大 8 MiB、timeout 30 秒です（`strata_control/transfer.py:32-34, 159-187`）。

feed 内の相対ファイル参照は feed の場所を基準に解決されます。HTTPS URL は許可され、HTTP は loopback 宛て、または `STRATA_UPDATE_ALLOW_HTTP=1` の場合に許可されます。ローカル feed から remote URL を参照すること、および feed の基準ディレクトリ外への相対参照は拒否されます（`strata_control/transfer.py:77-86, 99-128`; `strata_control/feed.py:153-161`）。

`--check` と通常更新の両方で feed を読みます。`--check` は更新内容を表示し、feed 情報と `last_check` をコンポーネント状態ファイルへ保存しますが、取得するのは feed のみです（`strata_cli/update_cmd.py:197-209`; `strata_control/updater.py:624-640`）。通常更新では受理した feed source/sequence 等を保存してから、指定された engine、Control、必要なら `--app` の installer を処理します（`strata_control/updater.py:355-366, 1274-1297`）。

`--feed` は `strata components rollback` にも共通 parser により登録されていますが、rollback 分岐は feed source を選ぶ前に戻るため、rollback の処理には使われません（`strata_cli/update_cmd.py:50-59, 185-196, 197-200`）。

## 適用条件と副作用

- update は明示的なダウンロード操作であり、`STRATA_NO_ACQUIRE` による取得禁止時は拒否されます。`--check` も feed を取得するため同じ条件に従います（`strata_cli/update_cmd.py:197-200`; `strata_control/updater.py:355-360`）。
- HTTP(S) を指定すればネットワークから feed と署名を読みます。通常更新では feed が指すパッケージ等も取得対象になります。署名検証に成功した feed の情報はコンポーネント領域の `.updates/state.json` に記録されます。`--check` も同ファイルを更新します（`strata_control/feed.py:342-360`; `strata_control/updater.py:165-180, 363-366, 633-640, 1280-1285`）。
- ローカルパスも指定できます。ローカル source の feed が remote の配布 URL を指す構成は拒否されます（`strata_control/transfer.py:108-128`）。

## 出力とエラー

通常の update では人向け出力に選択された feed source と feed sequence/key ID を表示します。`--output json` / `jsonl` では機械向け出力になります（`strata_cli/update_cmd.py:39, 167-172, 211-224`）。feed の読み込み失敗は `FeedError` として処理され、通常出力では `strata: <理由>` を stderr に、JSON 系では error object を出力します。読み込み失敗は feed 層で終了コード 6、署名・feed 内容・sequence の拒否は通常 5 です（`strata_control/feed.py:342-360, 312-339`; `strata_cli/update_cmd.py:167-172, 225-234`）。

## 根拠

- parser と共通スコープ: `strata_cli/update_cmd.py:30-59`
- source の優先順位と既定値: `strata_cli/update_cmd.py:23-27, 87-95`
- update 実行とエラー整形: `strata_cli/update_cmd.py:163-234`
- feed の場所解決、署名・sequence 検証: `strata_control/feed.py:312-360`
- URL policy と相対参照制約: `strata_control/transfer.py:65-128`
- feed/署名ファイルのサイズと timeout: `strata_control/transfer.py:159-187`
- 状態保存と check/update の処理: `strata_control/updater.py:165-204, 355-366, 624-640, 1274-1297`

調査範囲は上記 revision の Terminal CLI と feed/update 実装です。CLI を実行した help やネットワーク先の Release feed は調査していません。URL・ローカル source の解決と許可条件はソースコードを根拠に記載しています。
