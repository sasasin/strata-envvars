# `--feed`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | 署名済み update feed を置く HTTPS URL、許可された HTTP URL、`file://` URL、ローカルのファイルまたはフォルダー |

## 役割

更新情報の取得元を指定します。feed の署名が組み込みの信頼鍵（または明示的に追加されたテスト用鍵）で検証できる必要があります。engine と Control の更新、および `--app` を付けた場合のアプリ更新は、この feed の情報に従います。

## 使い方

```sh
# 指定した配布フォルダーの feed を読み、変更予定だけを確認
strata update --feed /srv/strata-feed --check

# HTTPS の feed JSON を指定して更新
strata update --feed https://updates.example.org/channel/strata-feed.json
```

ローカルフォルダーの場合、`strata-feed.json` とその署名ファイルがフォルダー内に必要です。例の HTTPS ホストは形式を示すためのものです。

## 値と既定値

parser は文字列を受け取り、型・URL・パスの事前 validation や列挙制約は設けません。値を省略したときの参照先は次の順です。

1. `--feed` に指定した非空文字列
2. 環境変数 `STRATA_UPDATE_FEED`
3. コンポーネント状態に記録された前回受理済み feed の source
4. `https://github.com/Niko1221/Strata/releases/latest/download/strata-feed.json`

URL が `.json` で終わらない場合は末尾に `/strata-feed.json` を追加します。ローカルのディレクトリーを指定した場合も `strata-feed.json` を読みます。JSON ファイルを直接指定すると、そのファイルと `.sig` サフィックスの署名ファイルを読みます。文字列の構文や feed 内容の検査は取得時に行われます。

## 実行時の動作

`strata update` は `--feed` を選択した source として更新 context に渡し、feed と署名を取得して検証します。署名が信頼されない、feed の channel が stable と異なる、期限切れ、または前回受理した sequence より古い feed は拒否されます。ローカル feed がネットワーク上のファイルを参照することや、feed の参照先が feed の配置場所から外れることも拒否されます。

明示した feed は、`STRATA_UPDATE_FEED` と保存済み source より優先されます。feed を正常に受理すると、その source、sequence、署名鍵 ID、channel、確認時刻がコンポーネント領域の `.updates/state.json` に保存されます。`--check` は feed 以外の配布物をダウンロードしませんが、受理した feed 情報と確認結果を同じ状態ファイルへ保存します。

`strata components update` も共通 parser を使い、同じ feed 選択・取得処理を行います。一方 `strata components rollback` にも共通 parser 経由で `--feed` は登録されていますが、rollback 分岐は feed source を選ぶ前に処理を終えるため、このオプションは rollback の動作に使われません。

## 適用条件と副作用

- `https://` は許可されます。`http://` は loopback 宛ての場合、または `STRATA_UPDATE_ALLOW_HTTP=1` の場合に限り許可されます。その他の URL scheme は拒否されます。
- ローカル source から feed が参照するファイルは、その feed のフォルダー内に限られます。ネットワーク source では相対参照を URL に解決し、HTTP は同じ loopback / 明示許可の条件に従います。
- feed 取得は `strata update` の明示的な取得操作です。`STRATA_NO_ACQUIRE` で取得が禁止された実行環境では拒否されます。
- `--check` 以外では feed に基づいて engine / Control の取得・検証・適用が進みます。アプリの installer は `--app` も指定した場合に対象となります。

## 出力とエラー

通常出力では更新開始時に選択 source が表示されます。`--output json` / `--json` または `--output jsonl` では機械可読出力になります。取得不能は feed エラー（通常は終了コード 6）、署名・信頼・downgrade 等の拒否は終了コード 5 として処理されます。人向けエラーは stderr、JSON 系ではエラーオブジェクトに出力されます。

`--feed` の値が欠けている場合は argparse が使用法エラーとして終了コード 2 を返します。値の scheme が未対応、許可されない平文 HTTP、feed/署名ファイル不在・不正、または署名検証失敗の場合も更新は進みません。

## 根拠

- `strata_cli/update_cmd.py:23-39,42-59` — 既定 feed、parser の値受け取り、`strata update` / `strata components update` / `rollback` への登録。
- `strata_cli/update_cmd.py:87-95,163-200` — source の優先順位と更新 context への設定。
- `strata_cli/update_cmd.py:203-234` — check/update の分岐、出力、feed・署名・取得拒否のエラー経路。
- `strata_cli/cli.py:508-516,2135-2137` — `--json` / `--quiet` の後付け登録と update 実行への dispatch。
- `strata_control/feed.py:312-360` — feed と署名の取得、source 形式、署名・channel・期限・sequence 検査。
- `strata_control/transfer.py:65-86,108-128,159-187` — scheme と HTTP policy、feed 参照の境界、small document の読み込み失敗。
- `strata_control/updater.py:165-205,355-366,624-640,1274-1296` — 状態ファイル、受理 feed の保存、`--check` の保存動作、更新処理。

調査は指定 commit のソースに限定しました。同一 revision の実行可能な CLI help や Release 配布物との照合は行っていません。
