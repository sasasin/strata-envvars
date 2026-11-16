# `strata launch --backend`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | GPU メーカー名。実装上 `nvidia`、`amd`、`intel` と `auto` を案内。前後空白と大文字小文字は正規化される。 |

## 役割

`--backend` は Strata が使用するエンジンの GPU 系統を選びます。複数メーカーの GPU がある PC で選択を固定したい場合に使います。`auto` は保存済みの選択を解除し、PC の検出結果に戻します。parser は値を列挙制約で制限せず、実行処理で検証します。

## 使い方

```sh
# Intel GPU を選び、通常起動の選択として保存する
strata launch --backend intel --model q2_0 --no-tui

# 選択を保存せず、計画上だけ AMD を指定する
strata launch --backend amd --plan --model q2_0

# 保存済み選択を解除して自動選択に戻す
strata launch --backend auto --model q2_0 --no-tui
```

## 値と既定値

値は文字列として受け取り、実行時に `strip().lower()` で正規化します。`auto`、`default`、`none` は自動選択として扱います。その他は `clean_backend_name()` に渡され、別名 `nvidia`→`cuda`、`amd`→`hip`、`intel`→`sycl` に変換されます。受理されるのは最終的に `cuda`、`hip`、`sycl` に対応する入力です（`strata_control/engine_component.py:488-496`）。未指定時の選択はこのオプションでは上書きされず、環境変数・保存済み選択・プラットフォームや GPU 検出の順で決まります（同 `:528-549`）。

空文字列は `getattr(a, "backend", None)` の真偽値判定を通らず、明示指定処理が行われません。重複指定時の argparse は単一値引数のため、最後の指定値が Namespace に残る通常の挙動です。

## 実行時の動作

parser は `--backend` を `metavar="nvidia|amd|intel|auto"` の文字列引数として登録し、default は指定していません（`strata_cli/launch/cmd.py:113-115`）。起動処理は値を小文字化し、`auto` / `default` / `none` の場合、通常実行では保存済みメーカー選択を削除して、現在のプロセスの `STRATA_ENGINE_BACKEND` も環境から除きます。`--plan` の場合は保存設定を変更せず、プロセス環境からの除去だけを行います（同 `:771-780`）。

その他の値はメーカー別名をエンジン系統名に変換します。変換できない値ならコード 2 で失敗します。正常な値は `STRATA_ENGINE_BACKEND` に設定され、この起動とそこから開始する処理に適用されます。通常実行では設定ファイルにも保存され、次回起動や更新・アプリでも選択に使われます。`--plan` では保存されません（同 `:781-791`）。保存関数は設定 JSON の `engine_backend` キーだけを更新・削除し、親ディレクトリを作成して JSON を書き戻します（`strata_control/engine_component.py:513-525`）。保存された選択は、そのメーカーの GPU が現在の PC にない場合は無視されます（同 `:499-510`）。

## 適用条件と副作用

メーカー選択が利用可能な GPU に一致しない場合の後続エンジン選択・起動結果は、検出・コンポーネント処理に依存します。`--backend` 自体に GPU の有無を事前検証する処理は見当たりません。通常実行の明示値はユーザー設定ファイルを書き換えます。`auto` 等は通常実行時に保存選択を削除します。`--plan` ではこれらの永続的な設定変更を行いません。

ソースでは `auto` 時の案内文を「NVIDIA、AMD、Intel の順」としています（`strata_cli/launch/cmd.py:775-780`）。ただし macOS 等のプラットフォーム選択や環境変数による上書きもあるため、この順序だけで全環境の最終 backend が決まるとは限りません（`strata_control/engine_component.py:528-549`）。

## 出力とエラー

無効な値は `'<入力>' is not a make of graphics card Strata knows. Use nvidia, amd, intel or auto.` として失敗し、終了コード 2 を返します。通常出力では `strata:` を付けて stderr に出し、`--output json` では `ok: false` とエラー情報を JSON で stdout に出します（`strata_cli/launch/cmd.py:716-721, 781-783`）。値が受理されると選択結果に関する警告通知が追加されます（同 `:785-800`）。

## 根拠

- `strata_cli/launch/cmd.py:73-80` — `launch` parser の説明とコマンド概要。
- `strata_cli/launch/cmd.py:113-115` — `--backend` の parser 定義、案内値、既定動作の説明。
- `strata_cli/launch/cmd.py:716-721, 771-800` — エラー出力、値の分岐、環境変数設定、保存、通知。
- `strata_control/engine_component.py:488-496` — メーカー名から engine backend 名への変換。
- `strata_control/engine_component.py:499-525` — 保存値の適用条件と設定ファイル更新。
- `strata_control/engine_component.py:528-549` — 環境変数・保存選択・プラットフォーム・検出による backend 決定。
