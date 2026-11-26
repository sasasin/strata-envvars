# `--app`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--app` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`）。省略時 `false` |

## 役割

`strata update` が行うエンジンと Control の更新に、デスクトップアプリ installer のダウンロードと検証を追加します。取得物はコンポーネントディレクトリの `.updates/app/` に置かれ、CLI はアプリをインストールしません。installer を実行して更新を完了するのは利用者です。

## 使い方

```sh
# 通常のエンジン／Control 更新に加えて、この PC 向けのアプリ installer を取得・検証する
strata update --app
```

インストーラーの取得先 feed、コンポーネントディレクトリ、インストール済みアプリの版はそれぞれ `--feed`、`--components-dir`、`--app-version` で指定できます。`--check` を付けた場合は feed の確認だけで、`--app` があっても installer はダウンロードされません。

## 値と既定値

- 値を受け取らない真偽値フラグです。明示すると `a.app` が真になり、指定しない場合は偽です。値の形式や範囲の検証はありません（`terminal/strata_cli/update_cmd.py:60-65`）。
- `--app-version` が指定されればその値、指定がなければ `STRATA_APP_VERSION` の値を、インストール済み版として判定に使います。どちらもなければ版は不明として扱います（`terminal/strata_cli/update_cmd.py:64`, `terminal/strata_cli/update_cmd.py:323-325`）。
- `--app` を付けても、feed にアプリ項目がない場合、または feed がこの PC のプラットフォーム向け installer を持たない場合は取得しません。インストール済み版が feed の版以上の場合も取得しません。版が不明の場合は、対象プラットフォームの feed エントリーがあれば取得対象になります（`terminal/strata_control/updater.py:2002-2015`, `terminal/strata_control/feed.py:76-82`）。

## 実行時の動作

parser は `strata update` に `--app` を登録し、通常更新の実行時にその真偽値を `app` 引数として更新処理へ渡します（`terminal/strata_cli/update_cmd.py:59-65`, `terminal/strata_cli/update_cmd.py:368-377`）。更新処理は署名済み feed を読み、エンジン、導入済み形状エンジン、Control の各処理に続けて、`--app` が有効な場合だけアプリ installer の処理を追加します（`terminal/strata_control/updater.py:2109-2129`）。

アプリ処理は feed のプラットフォーム別エントリーを選び、ディスク空き容量を確認してダウンロードします。feed 記載の SHA-256 はダウンロード処理で照合され、さらに feed の署名とは別の minisign 署名をアプリ更新公開鍵で検証します。成功すると installer を `.updates/app/` に移動して `downloaded` と報告します。自動実行・インストール・既存アプリの置換はこの処理にはありません（`terminal/strata_control/updater.py:2018-2049`, `terminal/strata_control/updater.py:574-599`）。

## 適用条件と副作用

- installer は現在のハードウェア情報に含まれるプラットフォーム用のエントリーから選ばれます（`terminal/strata_control/updater.py:2002-2009`, `terminal/strata_control/updater.py:2026`）。
- アプリ更新鍵は `STRATA_APP_UPDATE_PUBKEY` があればそれを使い、なければ同梱 `update_keys.json` の `app_minisign_public` を使います。鍵が得られないと、アプリ installer のダウンロードを始めず終了コード `5` のエラーになります（`terminal/strata_control/updater.py:1989-1999`, `terminal/strata_control/updater.py:2026-2031`）。
- ダウンロードは `.updates/partial/` の一時ファイルを使い、キャンセル時の部分ファイルは次回再開用に残ります。署名不一致時は取得アーカイブを削除します。空き容量不足は終了コード `6`、SHA-256 不一致は `5`、転送エラーは `6` になります（`terminal/strata_control/updater.py:574-599`, `terminal/strata_control/updater.py:552-571`, `terminal/strata_control/updater.py:2037-2041`）。
- アプリ更新処理で失敗しても、すでに成功したエンジンや Control の変更は巻き戻されません。各ステップの失敗を結果に記録して後続ステップを続け、最終的に最初の更新エラーの終了コードを返します（`terminal/strata_control/updater.py:2123-2129`, `terminal/strata_control/updater.py:2138-2139`）。
- `--check` は `updater.check()` に分岐して結果を表示して戻るため、`--app` の有無によらず installer を取得しません。check 結果にはアプリの版・提供状況が含まれます（`terminal/strata_cli/update_cmd.py:361-367`, `terminal/strata_control/updater.py:778-789`）。
- 同じ `--app` は `strata components update` にも別途登録されていますが、この文書は索引で指定された `strata update` のスコープです（`terminal/strata_cli/update_cmd.py:70-79`; 索引: `docs/cli/README.md:257-266`）。

## 出力とエラー

- 成功時は更新結果に `component: app`, `status: downloaded`, バージョン、保存先、installer を実行して完了する旨の note が含まれます。`--output json` では最終結果を JSON で出力します。`jsonl` では進捗イベントが JSON Lines で出力されます（`terminal/strata_control/updater.py:2042-2049`, `terminal/strata_cli/update_cmd.py:117-139`, `terminal/strata_cli/update_cmd.py:373-377`）。
- 通常出力で鍵不在や署名不一致などの更新エラーは `strata: ...` として stderr に出力され、対応する終了コードが返ります。機械可読出力ではエラーオブジェクトが JSON で出力されます（`terminal/strata_cli/update_cmd.py:307-316`, `terminal/strata_cli/update_cmd.py:378-390`）。
- feed のアプリ項目の形式不正は feed 読み込みエラーです。アプリ項目はオブジェクト、版、空でないプラットフォーム一覧を要求し、既知のターゲットについて URL、署名、SHA-256、サイズを読み取ります（`terminal/strata_control/feed.py:548-589`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:59-65` — `strata update` parser の登録、型、既定値、関連版引数。
- `terminal/strata_cli/update_cmd.py:318-325`, `terminal/strata_cli/update_cmd.py:355-377` — コンテキストへの版設定、`--check` 分岐、`app` の転送と出力。
- `terminal/strata_control/updater.py:1989-2049` — アプリ公開鍵の選択、版・プラットフォーム判定、installer の取得・署名検証・配置。
- `terminal/strata_control/updater.py:574-599`, `terminal/strata_control/updater.py:2109-2139` — ダウンロードの失敗経路、更新ステップの順序とエラー集約。
- `terminal/strata_control/feed.py:76-82`, `terminal/strata_control/feed.py:548-589` — アプリ版と feed エントリーの検証。
- `docs/cli/README.md:257-266` — `strata update` 階層と指定文書への索引リンク。
