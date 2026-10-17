# `SPLIT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

この変数を読むのは同梱のテスト用スクリプト `tools/batch_groups_cache_test.py` だけです。`GPUS` で複数 GPU を指定したとき、層分割の境界を `cfg["layer_split"]` に設定します。Strata エンジン本体が `SPLIT` を直接読む実装は確認できません。

スクリプトの目的は、層分割と batch groups を有効にした状態で、交互に続ける会話の prompt cache が再利用されることを確認することです。このスクリプトは3ラウンドで2会話を並行実行し、ログの再利用 token 数を検査します。`SPLIT` はそのテスト実行で層分割境界を指定する補助入力です（`tools/batch_groups_cache_test.py:1-11,57-87`）。

## 値と判定

環境変数を調べるのは `GPUS` が空でない場合だけです（`tools/batch_groups_cache_test.py:28-30`）。その場合の扱いは次のとおりです。

| `SPLIT` の状態 | 設定される値と結果 |
|---|---|
| 未設定 | Python の `os.environ.get("SPLIT", "auto")` により `"auto"`。空でない `GPUS` があれば設定自動決定を要求する |
| 空文字 | 空文字を `layer_split` に設定する。サーバー側で空白除去後に空と判定され、`"auto"` に正規化される |
| `auto`（大文字小文字を問わない。前後の空白も許容） | サーバー側で `"auto"` に正規化される |
| 整数またはカンマ区切り整数 | 整数化され、前後空白が除かれたカンマ区切り文字列になる。例: `24, 36` → `24,36` |
| その他 | `layer_split_value()` の形式検査で `ValueError` になる。数値でない項目、float/bool、要素数不一致、2未満の先頭値、昇順でない境界は拒否される |

サーバー側では GPU 数を `n` として、境界値は原則 `n - 1` 個必要です。設定値は各後続 GPU が担当を開始する最初の layer 番号であり、各 GPU の layer 数ではありません（`serve/server.py:2604-2634`）。

## 有効になる条件

- `GPUS` が空でないこと。未設定または空文字ならこのスクリプトは `SPLIT` を参照せず、設定ファイルの `gpu` / `layer_split` をそのまま使います。
- `GPUS` はカンマ区切りで `int()` 変換され、`cfg["gpu"]` を上書きします。そのときだけ `SPLIT` の値で `cfg["layer_split"]` も上書きします（`tools/batch_groups_cache_test.py:28-30`）。
- `serve.server.engine_args()` は複数 GPU の layer split と判定され、かつ `cfg["args"]` に既に `--layer-split` がない場合に `layer_split_value()` を呼び、値をエンジン CLI 引数へ追加します。`--peer-device` が args にある場合は layer split と判定されません（`serve/server.py:2637-2661`）。
- args に `--layer-split` が既にあれば、`engine_args()` は環境変数由来の `cfg["layer_split"]` を CLI 引数として追加しません。このとき `SPLIT` の値は当該起動引数を上書きしません。

## 実行時の詳細

スクリプトは `SPLIT` を読み取った後、`engine_args(cfg)` の戻り値に `STRATA_EXTRA_ARGS` の引数を連結して `StrataEngine` を作ります。エンジンに渡るのは `SPLIT` という環境変数そのものではなく、条件を満たす場合に生成された `--layer-split <値>` です（`tools/batch_groups_cache_test.py:28-33`, `serve/server.py:2643-2661`）。`SPLIT` の値はスクリプト実行時に読み取られ、その後の環境変更を再評価するコードはありません。

無効な境界値の場合、`engine_args()` の評価中に `layer_split_value()` が `ValueError` を送出するため、このスクリプトはエンジン起動前に失敗します。値の形式エラーを出すメッセージには、必要な数と例が含まれます（`serve/server.py:2623-2634`）。

## 根拠

- `tools/batch_groups_cache_test.py:1-11`: テストツールの目的と実行条件。
- `tools/batch_groups_cache_test.py:28-33`: `GPUS` 条件、`SPLIT` の既定値、設定と起動引数の構築。
- `serve/server.py:2604-2634`: `layer_split` の正規化、境界値の数・順序・範囲検査。
- `serve/server.py:2637-2661`: 複数 GPU を layer split と判定する条件と、`--layer-split` の追加条件。
- `tools/batch_groups_cache_test.py:57-87`: 3ラウンドの実行と prompt 再利用率による結果判定。

`docs/DETAILS.md` などの設計資料には、このテストツールの `SPLIT` 環境変数についての独立した説明や測定値は確認できませんでした。したがって、ここではコードにある用途と処理だけを記載しています。
