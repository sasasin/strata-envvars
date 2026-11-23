# `source-setup setup.py --feed`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などから起動） |
| オプション | `--feed` |
| 別名 | なし |
| 値 | `URL` または `DIR`。署名付き更新 feed の URL、ファイル、または格納フォルダー |

## 役割

セットアップ時に参照する署名付き更新 feed の場所を指定します。feed に含まれるモデル一覧をメニューへ加えるための任意読込と、feed 登録モデルに専用の shape engine が必要な場合の取得に使われます。通常の組み込みモデルを明示してセットアップするだけなら、この値は通常のモデルファイルのダウンロード先を変更しません（parser は `a.feed` を shape engine の取得と feed モデル読込へ渡します）。`terminal/setup.py` は Windows/Linux 用セットアップの入口で、Apple Silicon の通常経路は `engine/metal/setup_mac.py` へ委譲され、同じ feed モデル読込が行われます（`terminal/setup.py:1-4`, `terminal/setup.py:11218-11223`, `terminal/setup.py:9408-9417`, `engine/metal/setup_mac.py:361-374`）。

## 使い方

```sh
# feed のモデルも選べるように対話セットアップを開始
python3 terminal/setup.py --feed ./test-feed

# 公開 feed を使って、feed にあるモデルを指定してセットアップ
python3 terminal/setup.py --feed https://github.com/Niko1221/Strata/releases/latest/download/strata-feed.json --family "$FEED_FAMILY" --model "$FEED_QUANT"
```

2つ目の例では `FEED_FAMILY` と `FEED_QUANT` に、その feed のモデル定義にある値を設定します。ローカルの検証用ディレクトリを使う場合は、feed JSON と対応する署名ファイルを同じ場所に置きます。

## 値と既定値

`argparse` は値を文字列として受け取り、`choices` や専用の `type` validator は付けていません。既定値は未指定時の `None` です（`terminal/setup.py:11301-11303`）。

feed の取得元は、空でない明示値 `--feed`、環境変数 `STRATA_UPDATE_FEED`、前回記録された HTTPS feed、それらがない場合のプロジェクト既定 feed の順です。明示値が空文字列なら `if a.feed` が偽になるため、次の候補へ進みます。記録済み URL は HTTPS のものだけ再利用し、ローカルパスや loopback URL は次回へ持ち越さず、再度指定しなければ既定 feed に戻ります（`terminal/strata_cli/update_cmd.py:142-158`）。

値がフォルダーなら、ホスト用 feed 名（通常 `strata-feed.json`、Linux ARM64 では `strata-feed-linux-aarch64.json`）を探し、見つからず `strata-feed.json` があればそちらを使います。`.json` で終わる HTTP(S) URL はそのまま使い、それ以外の HTTP(S) URL にはホスト用 feed 名を追加します。署名ファイルは feed の場所に `.sig` を付けて読みます（`terminal/strata_control/feed.py:680-688`, `terminal/strata_control/feed.py:691-717`）。

重複指定を拒否する処理はありません。`argparse` が作る引数値は最後の指定ですが、引数解析前に行う feed モデル探索の `_peek` は最初に現れた `--feed` を読むため、重複指定時には探索と後続処理で参照先が異なることがあります（`terminal/setup.py:11206-11210`, `terminal/setup.py:11223`, `terminal/setup.py:11301-11303`）。

## 実行時の動作

feed モデルを必要とする未知の `--family` / `--model` を指定した場合、または対話式でモデル選択メニューを出す場合に feed を読み、検証済みのモデルを既存カタログへ加えます。`--yes` で family が未指定の場合はこのメニュー用 feed 読込を行わず、feed モデルを選ぶ対話メニューにも入りません。feed にモデル一覧がなければカタログは変わらず、確認済みの一覧キャッシュがあればオフライン時にそれを使います（`terminal/setup.py:11220-11225`, `terminal/setup.py:11767-11772`, `terminal/setup.py:9593-9607`, `terminal/strata_control/feed_models.py:110-137`, `terminal/strata_control/feed_models.py:204-220`）。

指定元は `strata_control/feed.py` の取得処理へ渡され、信頼鍵による署名、stable channel、期限、最後に受理した sequence との比較を通過した feed だけが使われます。モデル一覧キャッシュは `<components>/.updates/feed-models.json` に保存され、読込時にも署名を再検証します。既存モデルとの ID・タグ・ファイル pin の衝突や不正な個別エントリーは警告ログを出して除外されます（`terminal/strata_control/feed.py:650-677`, `terminal/strata_control/feed.py:691-717`, `terminal/strata_control/feed_models.py:32-58`, `terminal/strata_control/feed_models.py:61-99`, `terminal/strata_control/feed_models.py:521-545`）。

選ばれたモデルに shape engine が必要なら、同じ `--feed` 値が engine の feed 読込にも渡ります。対応する engine が新しければ取得・検証・配置し、テスト起動が通ってから使います。既存 engine があれば feed 読込や更新に失敗しても既存 engine を返して続行します。未導入で取得に失敗した場合は失敗文を表示してセットアップを止めます。通常の feed モデルの GGUF はモデル定義の固定 revision / SHA-256 pin で扱われ、`--feed` 自体はその GGUF のホストを指定しません（`terminal/setup.py:9408-9424`, `terminal/strata_control/shape_engine.py:289-343`, `terminal/strata_control/shape_engine.py:349-410`, `terminal/strata_control/feed_models.py:3-7`）。

## 適用条件と副作用

- `--feed` のモデル一覧読込は任意です。`STRATA_FEED_MODELS=0`、信頼鍵なし、feed の取得・検証エラー時は新しい一覧を使わず、利用可能なら最後の署名検証済みキャッシュを使います。セットアップのこのカタログ読込は feed 失敗を致命エラーとして表示しません（`terminal/strata_control/feed_models.py:110-137`, `terminal/setup.py:9593-9607`）。
- `https`、loopback の `http`、`file:`、ローカルパスが扱われます。非 loopback の平文 HTTP は通常拒否されますが、`STRATA_UPDATE_ALLOW_HTTP=1` の場合は許可されます。不明な URL scheme は拒否されます（`terminal/strata_control/transfer.py:154-175`）。
- feed モデルの新規一覧取得は最大5秒の timeout で行われ、成功時にはキャッシュを書き換えます。モデル専用 engine の初回取得は別経路で、未導入なら最大30秒の feed timeout で取得・検証・配置・テスト起動します（`terminal/strata_control/feed_models.py:34`, `terminal/strata_control/feed_models.py:124-134`, `terminal/strata_control/shape_engine.py:349-366`）。
- モデル専用 engine の取得は既存 engine 置換後にテスト起動し、失敗した新しい配置は削除します。古い engine は成功した場合のみ保持数に従って整理されます（`terminal/strata_control/shape_engine.py:289-343`）。
- Apple Silicon の通常セットアップでは `setup_mac.py` が引数解析前に `--feed` をモデルカタログ用に読みます。Metal 用 parser は未知引数を残す `parse_known_args` を使うため、この値を feed 探索後の通常処理へ渡さなくてもカタログ読込に使えます。Metal 側の通常モデルも同じ feed モデル一覧へ加えられます（`engine/metal/setup_mac.py:361-374`, `engine/metal/setup_mac.py:403`, `terminal/strata_control/feed_models.py:334-348`）。

## 出力とエラー

カタログ用 feed の失敗はログに記録されるだけで、最後の検証済み一覧があればそれにフォールバックします。カタログが空の場合はフィードモデルが表示されません（`terminal/strata_control/feed_models.py:123-137`）。

専用 engine が必要な場合は挙動が異なります。未導入の engine を取得できない、feed に当該 engine がない、または当該 PC に合う package がない場合、`shape_engine.ensure` は失敗理由を出力し、セットアップ側は engine がない状態を許可する `STRATA_ALLOW_NO_ENGINE=1` がなければ `fail(...)` で停止します。既存 engine がある場合は feed が読めなくても既存 engine で続行します（`terminal/strata_control/shape_engine.py:349-410`, `terminal/setup.py:9408-9424`）。

## 根拠

- `terminal/setup.py:11218-11225` — OS 別の委譲と、未知 family/model のときの引数解析前 feed 探索。
- `terminal/setup.py:11301-11303` — root parser の `--feed` 登録と表示形式。
- `terminal/setup.py:11767-11772` — 対話メニューでの条件付き feed モデル読込。
- `terminal/setup.py:9593-9607` — feed source の解決と任意カタログ読込。
- `terminal/strata_cli/update_cmd.py:142-158` — 明示値・環境変数・記憶値・既定値の優先順。
- `terminal/strata_control/feed.py:691-717` — URL/フォルダーから feed と署名を読み、署名・有効性を検証。
- `terminal/strata_control/feed_models.py:110-137` — cache fallback とモデル一覧の保存。
- `terminal/setup.py:9408-9424`, `terminal/strata_control/shape_engine.py:289-343`, `terminal/strata_control/shape_engine.py:349-410` — 選択モデルの専用 engine 取得、検証、失敗時の扱い。
- `terminal/strata_control/transfer.py:154-175` — source scheme と HTTP policy。
- `engine/metal/setup_mac.py:361-390` — Mac 側での feed モデル探索と parser 経路。
