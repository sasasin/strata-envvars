# `PI_SKIP_VERSION_CHECK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部アプリの環境変数の動作は対象外。

## 役割

Strata の `strata connect pi` が pi 用の接続情報を組み立てるとき、環境変数行 `PI_SKIP_VERSION_CHECK=1` を固定で生成します。これは Strata 自身のバージョン確認を制御する設定ではありません。Strata は同名の値を自身の環境から読み取らず、この変数を設定して pi を起動することもありません。

## 値と判定

| 状況 | Strata の処理 |
|---|---|
| `strata connect pi` 用の設定生成 | `{"PI_SKIP_VERSION_CHECK": "1"}` を返す |
| Strata プロセスでの未設定・空文字・その他の値 | 読み取り箇所がなく、設定生成の値に影響しない |
| 他の harness を選択 | pi 用のこの環境変数は生成しない |

値は環境から parse されず、境界値や無効値の扱いはありません。`"1"` は Strata が出力する文字列値です。

## 有効になる条件

`strata connect pi` または `pi` harness を選んだ接続画面で設定を表示・取得すると生成されます。OS/backend、モデル状態、サーバーの状態、CLI の `--check` / `--write` による値の変更条件はありません。通常表示では Windows 向けに `set PI_SKIP_VERSION_CHECK=1`、それ以外では `PI_SKIP_VERSION_CHECK=1` の形式で出します。JSON 出力では `env` オブジェクトに含めます。TUI のコピー機能でも `PI_SKIP_VERSION_CHECK=1` をコピー対象に含めます。

## 実行時の詳細

`Harness` は `env` を任意の環境設定生成関数として持ち、pi の登録では固定の辞書を返す関数が指定されています。`render()` は選択された harness の `env` 関数を呼び、結果を出力データの `env` に載せます（`strata_cli/launch/harness.py:65-73,235-239,276-281`）。

`strata connect pi` はそのデータを人間向け表示または JSON として出力します。人間向け表示では `Environment:` の下に値を表示し、JSON では `env` フィールドに保持します（`strata_cli/launch/cmd.py:951-957,978-991`）。接続画面の TUI は同じ render 結果を表示し、コピー時にも環境設定行を加えます（`strata_cli/launch/monitor_ext.py:136-149,303-323`）。

`--write` は harness の設定ファイルを対象にし、この環境変数を Strata のプロセス環境や pi の起動環境へ設定しません（`strata_cli/launch/cmd.py:1011-1028`）。この実装から確認できるのは値の生成と提示までです。pi がこの値をどう解釈するか、またバージョン確認を実際に省略するかは Strata の挙動としては記述しません。

## 根拠

- `strata_cli/launch/harness.py:65-73,235-239`: harness の環境設定生成関数と pi 用の固定値。
- `strata_cli/launch/harness.py:276-281`: 選択 harness の環境設定を render 結果に含める処理。
- `strata_cli/launch/cmd.py:951-957,978-991,1011-1028`: CLI の JSON / 人間向け表示、および `--write` の対象。
- `strata_cli/launch/monitor_ext.py:136-149,303-323`: TUI での render、表示、コピー。
