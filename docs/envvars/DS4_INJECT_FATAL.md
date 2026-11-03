# `DS4_INJECT_FATAL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 (`strata-dsv41`) engine のテスト用フックです。指定した回数目の GEN/GENI リクエストで、実際の GPU fatal error と同じ終了経路を人工的に発生させます。通常の設定項目ではなく、テスト目的のコードとしてコメントされています。読み取り・発火箇所は engine の `src/dsv41/ds4_main.cpp` にあります（`src/dsv41/ds4_main.cpp:398-409,1318-1319`）。

## 値と判定

値は `std::atol` で `long` に変換され、変換結果が正数の場合だけカウント・発火します。文字列全体の検証はありません。

| 設定値 | 結果 |
|---|---|
| 未設定 | `0` として無効 |
| 空文字、数値で始まらない文字列 | `atol` の結果が `0` となり無効 |
| 正の整数 `N` | 対象となる N 回目の prompt 処理で発火 |
| `0`、負数 | 無効 |
| 数字の後に文字が続く値 | `atol` が読める先頭の数値部分で判定（例: `2abc` は `2`） |

`atol` の範囲外入力について、実装に明示的な検証や fallback はありません。CLI 引数や他の設定値による上書きはありません。発火対象の回に `DS4_INJECT_FATAL_ONCE` も設定されている場合だけ、同変数のファイル判定で発火を抑止できます（同ファイル `:400-408`）。

## 有効になる条件

- `strata-dsv41` の `--serve` 経路で、`GEN` または `GENI` コマンドが受理され、prompt 全体の処理が完了すること。通常の単一会話では `prompt_in()` が prompt 処理を行い、完了後に生成へ進みます（`src/dsv41/ds4_main.cpp:1349-1353,1355-1378,2629`）。
- prompt の途中で停止・失敗して早期 return する経路では、このフックの呼び出しまで到達しません（`src/dsv41/ds4_main.cpp:1312-1319`）。
- この判定箇所に OS、GPU backend、モデル状態、CLI の別フラグによる追加条件はありません。`--serve` を使わない standalone / その他の処理経路では呼ばれません。

## 実行時の詳細

関数内の `static const long n` は、`inject_fatal_now()` が初めて呼ばれたときに環境から読み、そのプロセス中はキャッシュされます。起動後に環境を書き換えても再評価されません。`static long seen` はプロセス内で共有され、`n > 0` の場合に限って呼び出しごとに増え、`seen == n` の回だけ発火します。従って、カウント対象は起動後の全 GEN/GENI ではなく、フックまで到達した完了済み prompt 処理です（`src/dsv41/ds4_main.cpp:398-408,1316-1319`）。

発火回に `DS4_INJECT_FATAL_ONCE=<file>` が空でない値で設定されている場合、engine はそのパスを `rb` で開いて既存ファイルを確認します。開ければ発火せず、開けなければ `wb` でファイル作成を試みてから発火します。作成に失敗しても発火は続きます。この補助変数は対象回にのみ評価されます（`src/dsv41/ds4_main.cpp:403-408`）。

発火すると、通常の GPU fatal 判定より先に `die_gpu_fatal()` を呼びます。stderr に `ds4: fatal GPU error (...)`、stdout に `ERR fatal GPU error: ...` を出して flush し、`std::_Exit(3)` でプロセスを終了します。人工エラー文は `injected (DS4_INJECT_FATAL): an illegal memory access was encountered` です（`src/dsv41/ds4_main.cpp:390-396,1318-1319`）。Strata の Python サーバーは engine の予期しない終了を `EngineDied` として扱い、応答開始前のリクエストには HTTP 503 と「次のリクエストで再起動する」旨を返します。次のリクエストで停止済み engine を再起動します（`serve/server.py:1692-1695,5060-5065,7986-7987`）。

## 根拠

- 値の読み取り、キャッシュ、回数判定、補助ファイル判定: `src/dsv41/ds4_main.cpp:398-409`
- fatal の標準出力・標準エラーと終了コード: `src/dsv41/ds4_main.cpp:390-396,1318-1319`
- prompt 完了後の呼び出しと `--serve` 分岐: `src/dsv41/ds4_main.cpp:1312-1319,1349-1378,2629`
- サーバー側の engine 終了検出、再起動、503: `serve/server.py:1692-1695,5060-5065,7986-7987`
