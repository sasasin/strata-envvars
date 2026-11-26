# `source-setup` `--no-browser`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` / update wrappers の root parser |
| オプション | `--no-browser` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

モデルのセットアップまたは起動後、チャットページをブラウザーで開かないようにします。API を利用する harness やアプリからの利用を想定した設定です。セットアップ時にはモデルの run config と生成 start script に記録され、既存モデルの通常起動時には server へブラウザーを開く指定を渡しません。

## 使い方

```sh
# 既定モデルのセットアップ／起動をブラウザーなしで行う
./setup.sh --no-browser

# Windows のセットアップ／起動
START-HERE.bat --no-browser
```

## 値と既定値

値は不要です。省略時の parser 値は `None` で、コマンドライン上で `--no-browser` を指定すると `False` になります。反対の `--browser` は同じ `browser` 属性を `True` にし、後から指定された方が有効です（`terminal/setup.py:11505-11509`）。オプションに値を続けると余分な引数として argparse が usage とエラーを出し、通常は終了コード 2 になります。

明示指定がない場合、既存設定の `open_browser` 値は再セットアップ時に保持されます。新規設定では `open_browser` が省略され、通常起動時の既定はブラウザーを開く動作です（`terminal/setup.py:7540-7545, 7557-7568, 7715-7733, 8670-8672`）。

## 実行時の動作

- モデルをセットアップする経路では、指定値を `open_browser` として run config に保存します。指定しなければ既存の `open_browser` は carry-over されます（`terminal/strata_control/setup_config.py:531-538`; `terminal/setup.py:7557-7568, 7715-7736`）。
- セットアップで書かれる `run-<model>.bat` / `.sh` は、設定が `False` のとき server 起動引数から `--open` を外します（`terminal/setup.py:9233-9246, 12521-12527`）。
- 既存モデルの通常起動では `--no-browser` が `start()` に渡され、設定の `open_browser` を `False` に更新して保存します。server 起動コマンドに `--open` が付かず、チャットページを自動で開きません（`terminal/setup.py:11761-11775, 8558-8563, 8590-8595, 8601-8602, 8670-8672`）。
- `--browser` を併記する場合は指定順が結果を決めます。例えば `--no-browser --browser` はブラウザーを開く設定になります（`terminal/setup.py:11505-11509`）。

## 適用条件と副作用

このオプションは root parser の設定・起動経路に適用されます。通常の macOS 起動は `setup.py` から `engine/metal/setup_mac.py` に委譲されるため、そちらの parser と設定経路は別 scope です（`terminal/setup.py:11434-11437`; 索引上の `source-setup/mac/`）。

設定・起動時にブラウザーを自動で開かないことが効果です。モデルのセットアップ、run config の書き込み、および server 起動自体は抑止しません。セットアップの再実行で既存設定が変わる場合、run config は書き換えられ、変更前のファイルは `.bak` として保存されます（`terminal/setup.py:7715-7744`）。通常起動時にも明示した設定は run config に保存されます（`terminal/setup.py:8590-8595`）。

## 出力とエラー

起動時の説明文はブラウザーが開く代わりに「server が準備完了を知らせる」と案内し、設定サマリーには `no browser` と表示します（`terminal/setup.py:8546-8555, 8690-8697`）。フラグ自体に専用の validation や失敗経路はありません。余分な値など parser が受け付けない引数は argparse のエラーになります。

## 根拠

- `terminal/setup.py:11505-11509` — `--no-browser` / `--browser` の parser 定義、既定値、反転動作。
- `terminal/setup.py:11434-11437` — 通常の macOS 経路が Metal setup へ委譲される条件。
- `terminal/strata_control/setup_config.py:531-538` — 指定値を設定へ反映。
- `terminal/setup.py:7540-7545, 7557-7568, 7715-7736` — 未指定時の既存キー引継ぎと設定書き込み。
- `terminal/setup.py:9233-9246, 12521-12527` — run script 生成時に `--open` を含める条件。
- `terminal/setup.py:8558-8563, 8590-8595, 8601-8602, 8670-8672` — 通常起動での設定保存、server 引数、ブラウザー起動条件。
- `terminal/setup.py:8546-8555, 8690-8697` — 設定サマリーと起動時メッセージ。
