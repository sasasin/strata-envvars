# `strata components update --feed`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | URL または feed を含むフォルダー／feed ファイルの場所 |

## 役割

更新時に読む署名付き update feed の場所を指定する。未指定なら環境変数、前回採用した HTTPS feed、プロジェクト既定 feed の順で決まる。`strata components update` と `strata update` は同じ共通 parser と feed 選択処理を使う。

## 使い方

```sh
strata components update --feed https://updates.example.invalid/strata-feed.json
```

HTTPS 上の署名付き feed を指定する例。実際の feed URL として利用できる値は feed の配置先に依存する。

```sh
strata components update --feed /srv/strata-feed
```

ローカル feed フォルダーを指定する例。フォルダーには対象 feed JSON と対応する `.sig` ファイルが必要。

## 値と既定値

`--feed` は値を1つ取り、parser では `default=None`、型変換や選択肢による validation は行わない。値は文字列として feed source に渡される。空文字列は `_feed_source` の真偽判定で未指定相当になる。

feed source の決定順は次のとおり。

1. `--feed` に空でない値を指定した場合はその値。
2. `STRATA_UPDATE_FEED` が設定されていればその値。
3. 保存済み feed source が `https://` で始まる場合はそれを利用する。ただし保存値が標準 release URL なら、当該マシン向け feed 名に置き換える。
4. それ以外（ローカル path、HTTP、その他の保存値）はプロジェクト既定 feed。

標準 feed は GitHub の最新 release にある JSON で、Linux ARM64 では `strata-feed-linux-aarch64.json`、その他では `strata-feed.json` が選ばれる。環境変数は `--feed` より優先度が低い。

## 実行時の動作

`--feed` の文字列は `ctx.source` に設定され、通常更新では署名付き feed の取得に使われる。入力がフォルダーならその中のプラットフォーム別 feed を探し、該当ファイルがなく `strata-feed.json` があればそれを使用する。URL が `.json` で終わらなければ、選ばれた feed 名を URL の末尾に加える。feed JSON と同じ場所の `.sig` を読み、信頼済み鍵による署名確認、feed の parse、channel・期限・sequence の検査を行う。受理した feed の source と sequence 等は更新 state に記録される。feed に model 一覧がある場合は、その署名付き内容をオフライン表示用に記憶する。

`--check` と併用した場合は feed を読んで変更予定を表示するだけで、コンポーネントのダウンロード・更新処理には進まない。

## 適用条件と副作用

- HTTPS、ローカル path／folder、`file:` URL を source として扱う。HTTP は loopback 宛ての場合に許可され、その他は `STRATA_UPDATE_ALLOW_HTTP=1` の明示設定がない限り拒否される。
- HTTPS 以外の source は後続実行の保存 feed として引き継がれない。ローカル feed や loopback feed を再利用する場合は、次回も `--feed` または `STRATA_UPDATE_FEED` で指定する。
- feed と署名を読むためネットワークまたはローカルファイルへのアクセスが発生する。署名鍵がない、署名が不正、channel 不一致、期限切れ、受理済み sequence より古い feed などは拒否される。
- feed の読込不能・到達不能は更新エラーとなる。到達不能は exit code 6。source の形式・HTTP policy など feed transfer の拒否も feed 読込エラーになる。
- feed を受理すると更新状態ファイルが更新される。コンポーネントの取得・入替は `--check` でない通常更新処理の後続段階で行われる。

## 出力とエラー

通常の人向け出力では更新開始時に選択された source が `Strata update (<source>)` として表示される。feed の読込時には `Reading the signed update feed` が通知される。JSON 出力では `--feed` 自体の説明行はなく、更新結果が構造化出力される。

feed 到達不能は exit code 6、署名・feed 内容等の拒否は feed error として報告される。feed 検査処理の全ての例外に対する CLI 終了コードはこの文書では網羅せず、更新全体のエラー変換・終了コードを参照されたい。

## 根拠

- `strata_cli/update_cmd.py:47-56` — 共通 parser における `--feed` の値・既定値。`strata_cli/update_cmd.py:70-79` — 同じ共通 parser を `components update` に適用。
- `strata_cli/update_cmd.py:138-154` — `--feed`、環境変数、保存値、既定値の選択と HTTPS のみを保存 source として再利用する条件。
- `strata_cli/update_cmd.py:345-362` — 選択した source を context に設定し、`--check` と通常更新を分岐。
- `strata_control/feed.py:680-688, 691-717` — feed ファイル名選択、JSON と署名の取得、署名・feed 検証。
- `strata_control/feed.py:650-677` — 信頼鍵、署名、channel、期限、sequence の検査。
- `strata_control/transfer.py:154-175` — source 種別と URL policy（HTTP の例外条件）。
- `strata_control/updater.py:433-452` — feed 読込、model feed の記憶、採用 feed 情報の state 記録。
- `strata_control/updater.py:1723-1736` — 通常更新で feed を読み、後続 component step を開始する位置。
