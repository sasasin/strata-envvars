# `strata components update --app`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--app` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。既定値は `False` |

## 役割

通常の engine と Control の更新に加え、現在のプラットフォーム向けデスクトップアプリのインストーラーもダウンロードして検証する。Terminal はインストーラーを配置するまでを担当し、アプリ自体のインストールは行わない。

## 使い方

```sh
strata components update --app
```

更新を適用せず、feed にあるアプリのバージョン状態を確認する場合は `--check` を使う。この場合 `--app` の指定有無にかかわらず候補情報を表示するだけで、アプリ用インストーラーはダウンロードしない。

## 値と既定値

`argparse` の `action="store_true"` で定義され、値は不要。省略時はアプリインストーラー更新を実行せず、指定時は更新手順に `app` ステップを追加する。アプリの現在バージョンは `--app-version` があればその値、なければ `STRATA_APP_VERSION` から読み取る。どちらもない場合はインストール済みバージョン不明として扱い、対象 platform の feed エントリーがあればダウンロード対象になる。

## 実行時の動作

`strata components update` の parser は `--app` を真偽フラグとして登録する。CLI の dispatch はこのコマンドを `update_cmd.run` に渡し、同処理が `a.app` を `engine_update.update_with_models` 経由で `updater.run_update` に渡す。通常の engine / Control 更新が既定で有効なため、`--app` はそれらを置き換えず追加する。

feed にアプリ項目がない、現在の platform 用エントリーがない、または既知のインストール済みバージョンが feed の版以上の場合、アプリのダウンロード処理は行わない。更新対象なら、インストール先コンポーネント領域の空き容量を確認し、feed 記載のサイズと SHA-256 に基づいてダウンロードする。さらに build が信頼する app minisign 公開鍵で署名を検証し、成功したインストーラーを `<components>/.updates/app/` に配置する。出力は `downloaded and verified` と保存先を報告し、インストーラーを実行して完了するよう案内する。

## 適用条件と副作用

- feed の app エントリーにこの PC の platform が必要。platform は検出された hardware context から選ばれる。
- アプリの署名検証鍵が build の `update_keys.json` にない場合（または `STRATA_APP_UPDATE_PUBKEY` にも有効な明示鍵がない場合）、ダウンロードせず失敗する。
- feed を読み、更新状態を記録するためネットワークアクセスとコンポーネント領域への状態書き込みが発生する。対象時はインストーラーをダウンロードして `.updates/app/` に保存する。デスクトップアプリのインストールや置き換えは行わない。
- 通常の engine / Control 更新も同時に処理される。実行中モデルがあり更新対象がある場合は、更新の gate による待機・確認・拒否条件が適用される。`--app` 単独でモデル稼働中の制御を回避するものではない。
- アプリの版比較には `--app-version` または `STRATA_APP_VERSION` を使う。未指定時は installed version が不明になり、対象プラットフォームの feed エントリーがあると最新版を取得する。

## 出力とエラー

成功した取得は人間向け出力でバージョン、検証済みであること、保存先を表示する。JSON / JSONL 指定時は結果を構造化出力する。鍵がない、SHA-256 / minisign 検証に失敗した場合は exit 5。ネットワーク転送失敗や空き容量不足は exit 6。キャンセル時は exit 130 で、部分ダウンロードは次回再開用に保持される。アプリを含む各更新ステップは個別に処理され、成功済みの他ステップを巻き戻さず、失敗時は最も重大な step の終了コードを返す。

## 根拠

- `terminal/strata_cli/update_cmd.py:70-79` — `components update` の parser 定義と `--app` の真偽フラグ登録。
- `terminal/strata_cli/cli.py:2208-2212` — `components update` を `update_cmd.run` へ dispatch。
- `terminal/strata_cli/update_cmd.py:318-325, 368-377` — installed app version の引き渡し、`--check` と通常更新の分岐、`a.app` の転送。
- `terminal/strata_control/updater.py:2002-2015` — platform エントリーとアプリ版の状態判定。
- `terminal/strata_control/updater.py:2018-2049` — 鍵の確認、空き容量・ダウンロード・署名検証、配置先と成功結果。
- `terminal/strata_control/updater.py:574-599` — feed 記載 SHA-256 を使う転送と転送・checksum エラーの分類。
- `terminal/strata_control/updater.py:2109-2138` — `app=True` の場合に app ステップを追加し、各 step を個別実行して状態を保存。
- `terminal/strata_control/engine_update.py:405-425` — モデル停止後の更新実行と再起動処理。
- `terminal/strata_control/feed.py:76-82` — インストール済みアプリバージョンの比較形式。
- `terminal/strata_control/signing.py:294-330` — minisign 署名の検証と失敗条件。

同じ `--app` は `strata update` にも定義されるが、ここでは索引上の scope である `strata components update` の経路だけを記述した。
