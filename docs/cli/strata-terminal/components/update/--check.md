# `--check`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--check` |
| 別名 | なし |
| 値 | 値を取らないフラグ。`store_true`、既定値は `False` |

## 役割

署名付き update feed を読み、現在の PC で engine・Control・app に何が適用されるかを報告します。feed 以外のパッケージはダウンロードせず、インストール処理にも進みません。`strata update --check` も同じ実装を使います。

## 使い方

```sh
strata components update --check
```

feed や出力形式を指定する場合:

```sh
strata components update --check --feed ./release-feed --output json
```

## 値と既定値

`--check` は値なしの真偽フラグです。省略時は通常の更新処理へ進みます。引数 parser は `action="store_true"` で登録されています。`--check=value` のような値付き指定はこの parser の構文ではありません。

feed の選択は `--feed`、`STRATA_UPDATE_FEED`、components state に記録された直近の source、既定の GitHub latest release feed の順です。署名検証には組み込み鍵と、設定されていれば `STRATA_UPDATE_TRUSTED_KEYS` の追加鍵を使います。`--output` は `human`（既定）、`json`、`jsonl` を選べます。

## 実行時の動作

オプションが指定されると、共通の前処理で components root と hardware 情報を得て、`--backend` があれば検出 backend をその値で上書きします。その後、acquisition の許可確認、信頼鍵の読み込み、feed source の決定を行い、`updater.check(ctx)` を呼びます。この処理は署名付き feed と署名ファイルを読み、feed の有効性・channel・期限・sequence を検証し、engine/Control/app の状態を選択・比較してレポートを作ります。

engine の選択・状態表示には `--backend`、`--force`、ハードウェア、インストール済み engine と記録状態が影響します。`--force` は `failed-before` または rollback 後の `skipped` 判定を再試行可能な判定に戻すためのものです。app のインストール済み version が不明な場合、その状態は `--app-version` または `STRATA_APP_VERSION` で与えられます。`--components-dir` は参照・更新する components と updater state の場所を変えます。

`--wait` はこの分岐では使用されません。待機処理は `--check` 分岐の後にあります。また、`--app`、`--no-engine`、`--no-control` は check 分岐より後の `run_update()` に渡されるため、check レポートの対象を除外しません。check は3種類の decision をレポートに含めます。

human 出力は feed sequence/channel/署名鍵、engine の状態と選択理由、Control と app の状態、engine serving 状態を表示します。`--output json` は一つの JSON レポート、`jsonl` も成功時に一つの JSON 行を出します。

## 適用条件と副作用

このオプションも更新入口の acquisition 制約と署名検証を受けます。acquisition が禁止されている環境では feed 読み込み前に拒否され、追加鍵ファイルの不正や信頼鍵のない状態、署名不一致、feed の期限切れ・channel 不一致・巻き戻しなども失敗します。feed は URL、file URL、ローカルの feed ファイルまたはフォルダーから読み取れます。

パッケージのダウンロード・展開・engine/Control の切り替え・app installer の取得は行いません。ただし完全な読み取り専用ではありません。check は components ごとの update lock 用ディレクトリと `update.lock` を開き、feed の sequence/source/channel/確認時刻を state に記録し、`last_check` を保存します。ローカル feed の選択や署名鍵ファイルの読み込み、hardware probe、serving 状態の照会も行います。

## 出力とエラー

human 出力では失敗を stderr に `strata: ...` と表示します。`json` / `jsonl` では `ok: false`、エラーコード、メッセージを含む JSON を stdout に出します。署名エラーと acquisition 拒否は終了コード 5、feed 転送エラーは feed 層で 6、同じ components folder の updater lock 取得失敗は 7 です。feed の他の検証エラーは検出内容に応じた feed error code を返します。Ctrl-C は共通処理で終了コード 130 と「部分ダウンロードを保持し次回再開」という文面を返しますが、check 分岐自体は feed 以外をダウンロードしないため、この文面は通常の package update に対する共通メッセージです。

## 根拠

- parser と既定値、`strata update` との同一オプション登録: `strata_cli/update_cmd.py:42-59`
- feed source の優先順位と信頼鍵読み込み後の check 分岐、`--wait` / update 実行との順序: `strata_cli/update_cmd.py:87-95`, `strata_cli/update_cmd.py:163-224`
- human check レポートと出力形式: `strata_cli/update_cmd.py:62-84`, `strata_cli/update_cmd.py:132-161`, `strata_cli/update_cmd.py:203-209`
- acquisition 制約と例外の出力・終了コード: `strata_cli/update_cmd.py:167-172`, `strata_cli/update_cmd.py:197-209`, `strata_cli/update_cmd.py:225-234`; `strata_control/acquisition.py:70-84`
- state / update lock の作成・保存: `strata_control/updater.py:133-162`, `strata_control/updater.py:165-205`, `strata_control/updater.py:355-366`, `strata_control/updater.py:624-640`
- feed 読み込み、署名確認、期限・sequence 検証: `strata_control/feed.py:330-360`; trusted key 読み込み: `strata_control/signing.py:194-216`, `strata_control/signing.py:234-245`
- hardware 情報、engine decision、`--force` の影響: `strata_control/updater.py:249-270`, `strata_control/updater.py:566-614`
- Control / app decision: `strata_control/updater.py:1095-1108`, `strata_control/updater.py:1210-1223`
- CLI 階層での parser 登録: `strata_cli/cli.py:139-140`
