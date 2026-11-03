# `strata components engines --wait`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数。`float` に変換される数値 |

## 役割

このコマンドで `--wait` は構文上受理されますが、エンジン一覧処理は指定値を待機処理に使いません。稼働中のモデルがあっても、停止を待たずに導入済みエンジンの一覧を表示します。

## 使い方

```sh
strata components engines --wait 30
```

`30` は引数として受理されますが、一覧を出す前に最大30秒待つ、という動作にはなりません。待機を目的にこのオプションを付けても効果はありません。

## 値と既定値

- parser は `type=float`、`default=None`、表示用 metavar `SECONDS` として定義されています。したがって未指定時は `None` です。
- コマンド実行時には値が `a.wait or 0.0` として `Context.wait` に格納されます。ただし `engines` 分岐ではこのフィールドを参照しません。
- この parser 定義に秒数の範囲・正数・有限値などの追加 validation はありません。数値へ変換できない値や値の欠落は `argparse` の引数解析段階で拒否されます。

## 実行時の動作

`strata components engines` の実行分岐は `_engines_command()` を呼び、`ctx.serving` を現在の稼働状況取得関数に設定します。その後 `engine_library.list_engines()` を呼び出し、テキストまたは JSON の一覧を出力します。この経路に `_maybe_wait()` や `wait_until_idle()` の呼び出しはありません。`list_engines()` は稼働状況を結果に含めるために読み取りますが、待機や状態変更はしません。

同じ `_common()` が `--wait` を `strata components use` にも追加しますが、そちらは選択処理の前に `_maybe_wait()` を通し、切替処理で `wait_until_idle()` を呼びます。この動作は `strata components engines` の一覧コマンドには適用されません。

## 適用条件と副作用

`--wait` の値は `engines` 一覧の走査、稼働中表示、出力形式に影響しません。`list_engines()` は導入済みファイルを読み取り、各エンジンの状態を一覧にまとめます。ソースの docstring では、この一覧処理はファイルを読むだけで変更・ダウンロードをしないとされています。

## 出力とエラー

- 一覧は既定の human 出力、または共通 option `--output json` / `--output jsonl` で機械向けに出力されます。`--json` も one-shot parser に後から追加されます。
- `--wait` 自体について、一覧経路に待機タイムアウトや待機固有の失敗出力はありません。
- `--wait` に数値へ変換できない値を渡した場合などは、コマンド本体へ入る前の引数解析で失敗します。実行時の `UpdateError` はテキスト時 stderr、機械出力時 JSON に出す共通ハンドラがありますが、一覧処理における `--wait` 固有の失敗経路は確認できません。

## 根拠

- `strata_cli/update_cmd.py:47-58` — `_common()` における `--wait` の `float` 型、既定値 `None`、metavar と説明。
- `strata_cli/update_cmd.py:82-83` — `engines` parser の登録と `_common()` の適用。
- `strata_cli/update_cmd.py:244-256` — `a.wait or 0.0` を含む `Context` の生成。
- `strata_cli/update_cmd.py:272-273,358-377` — `engines` / `use` / `remove` の分岐と、一覧コマンドが `list_engines()` を呼んで出力する経路。
- `strata_cli/update_cmd.py:403-418` — `_maybe_wait()` が待機する条件。`engines` 分岐からは呼ばれません。
- `strata_control/engine_library.py:180-195` — `list_engines()` が稼働状況を読み、一覧情報を組み立てる処理。
- `strata_control/engine_library.py:225-239` — `use_engine()` が `wait_until_idle()` を呼ぶ別コマンド側の処理。
- `strata_cli/cli.py:508-515` — one-shot parser に対する `--json` / `--quiet` の追加。
