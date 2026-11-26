# `--browser`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（トップレベル） |
| オプション | `--browser` |
| 別名 | なし |
| 値 | 値を取らない真偽スイッチ |

## 役割

モデルの起動準備または既存モデルの起動時に、準備完了後チャットページをブラウザーで開く設定を明示的に有効にします。対になる `--no-browser` で保存した設定を解除する用途があります。一般的な Linux / Windows の `setup.py` 経路で有効です。通常の macOS 経路は別の parser に引数を渡し、そこで未知引数として警告されるため、このオプションは適用されません。

## 使い方

```sh
# Strata の checkout 内で、モデルを通常起動し、チャットページを開く
./setup.sh --browser

# Windows で同じ設定を明示する
START-HERE.bat --browser
```

## 値と既定値

値は不要です。parser は `store_true` として登録され、`--no-browser` も同じ `browser` 属性を使って `store_false` に設定されます。どちらも指定しない場合の属性値は `None` で、既存の `open_browser` 設定を変えません。設定に `open_browser: false` がなければ起動側の既定ではブラウザーを開きます。両方を指定した場合は、引数列で後に現れたスイッチの値が使われます (`terminal/setup.py:11505-11509`, `terminal/setup.py:11606`)。

## 実行時の動作

- 既存モデルを起動する経路では、明示された値だけを `keep` に渡します。`start()` は `None` を除外し、保存済み値と異なる場合は設定 JSON の `open_browser` を更新して保存します。値が変わったときは「the browser opens」などの保存通知が出ます (`terminal/setup.py:11761-11766`, `terminal/setup.py:8577-8595`)。
- セットアップ経路では、明示値をモデル設定の `open_browser` に入れて設定を書きます。これは Linux / Windows の複数モデル導入経路と Intel Arc、macOS の一部モデル経路にもあります (`terminal/setup.py:9445-9448`, `terminal/setup.py:10012-10018`, `terminal/setup.py:10404-10412`, `terminal/setup.py:10943-10951`, `terminal/setup.py:11341-11361`)。
- 起動時に `open_browser` が false でなければ `setup.py` はサーバー起動引数へ `--open` を加えます。サーバーはモデルの準備完了後、ローカルページの URL を `webbrowser.open` に渡す daemon thread を開始します (`terminal/setup.py:8670-8672`, `terminal/serve/server.py:9746-9751`)。
- セットアップで生成する `run-<model>.sh` / `.bat` も保存設定に応じて `--open` を含めます (`terminal/setup.py:9233-9246`)。

## 適用条件と副作用

- 通常の Linux / Windows の root parser では利用できます。起動時に明示すると、そのモデルの設定 JSON を更新することがあります。セットアップ時は生成・更新されるモデル設定へ記録され、起動スクリプトにも反映されます (`terminal/setup.py:8590-8595`, `terminal/setup.py:9445-9448`, `terminal/setup.py:9233-9246`)。
- `setup.py` は通常の macOS では独自 parser を実行する前に `engine/metal/setup_mac.py` へ引数を委譲します。同 parser は `--no-browser` を登録しますが `--browser` は登録せず、未知引数を「not used on a Mac」と警告して処理を続けます (`terminal/setup.py:11434-11437`, `terminal/setup.py:9290-9294`, `engine/metal/setup_mac.py:375-405`)。ただし Control モード、Hy4-Flash、Inkling-2-Mini などは通常の委譲条件から外れ root parser 側を通る場合があります (`terminal/setup.py:11434-11437`)。
- ブラウザー起動を要求するだけで、ブラウザー自体の起動成功は保証しません。起動先サーバーの `open_browser: false` は `--open` を受け取っても優先して開きません (`terminal/serve/server.py:9746-9751`)。

## 出力とエラー

このオプション固有の値検証やエラー分岐はありません。値を取らないため、値を後置する形式は parser の引数解釈対象外です。通常の起動時、設定値が変更された場合は保存通知が出ますが、同じ値ならその変更通知は出ません (`terminal/setup.py:8590-8595`)。macOS の委譲経路では `--browser` は未知引数として警告され、無視されます (`engine/metal/setup_mac.py:403-405`)。

## 根拠

- `terminal/setup.py:11505-11509` — `--no-browser` / `--browser` の parser 定義、同一 dest、既定値と説明。
- `terminal/setup.py:8577-8595`, `terminal/setup.py:11758-11766` — 起動時に明示値を設定へ反映して保存する処理。
- `terminal/strata_control/setup_config.py:531-538`, `terminal/setup.py:9445-9448`, `terminal/setup.py:10012-10018`, `terminal/setup.py:10404-10412`, `terminal/setup.py:10943-10951`, `terminal/setup.py:11341-11361` — セットアップ時の設定反映。
- `terminal/setup.py:8670-8672`, `terminal/serve/server.py:9746-9751` — `--open` の転送とサーバー側のブラウザー起動。
- `terminal/setup.py:9233-9246` — 保存設定を使った起動スクリプトの生成。
- `terminal/setup.py:11434-11437`, `terminal/setup.py:9290-9294`, `engine/metal/setup_mac.py:375-405` — 通常の macOS 経路の委譲と未知引数の扱い。
