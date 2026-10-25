# `STRATA_DS4_NO_LIGHT`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 エンジンのプロンプト処理で、小さい expert set 用の light kernel を使わず、対象 expert を GEMM tile kernel に回します。light kernel は最大 16 行の expert set を扱います。対象は `src/dsv41/ds4_iq.cu` の IQ/K 量子化形式および MXFP4 の set 処理で、CPU 経路や通常の token/decode kernel を切り替える変数ではありません。

## 値と判定

`light_on()` は環境変数の値全体を parse せず、先頭文字が `'1'` かどうかだけを判定します。`'1'` で始まる場合に light kernel を無効化します。

| 値 | light kernel |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効 |
| 先頭が `1`（例: `1`, `10`, `1abc`） | 無効 |
| その他の文字列（例: `0`, `true`, ` 1`） | 有効 |

数値変換、大文字小文字変換、空白除去はありません。判定結果は `light_on()` 内の `static const bool` に保存されるため、最初の呼び出し後にプロセス内で環境値を変更しても反映されません。

## 有効になる条件

DeepSeek-V4.1 エンジンを含むビルドが必要です（CMake の `STRATA_BUILD_DSV41` が有効で、`STRATA_HIP_GFX906` ではない構成）。環境変数が未設定または先頭が `1` 以外の場合でも、light kernel が呼ばれるには expert 数が 512 以下で、`n_embd` と `n_ff` がともに 256 の倍数である必要があります。また TQ 形式は light kernel の対象外です。これらの条件を満たさない set は、変数値に関係なく既存の tile 経路になります。

## 実行時の詳細

プロンプトの gate/up または down set 処理で `light_gate_up()` / `light_down()` が `false` を返すと、呼び出し側は `skip_le = 0` のまま GEMM tile kernel を起動し、light kernel の担当範囲も含めて tile 側で処理します。light kernel が有効で成功した場合は、最大 16 行の expert を light kernel が担当し、残りの行があれば tile kernel が担当します。全行が 16 行以下なら light kernel のみで set 処理が完了します。

この変数を読むのは `light_on()` の一箇所です。該当箇所に環境変数に関するログ出力はありません。カーネル選択が変わることは確認できますが、この調査対象 commit のソースだけから数値結果の同一性や性能差は断定しません。

## 根拠

- `src/dsv41/ds4_iq.cu:1222-1228` — 先頭文字 `'1'` による無効化と初回評価後の static cache。
- `src/dsv41/ds4_iq.cu:1417-1425` — light kernel の実行条件と gate/up、down の判定。
- `src/dsv41/ds4_iq.cu:1428-1454` — light kernel が使われないときは `skip_le = 0` の tile kernel が set 全体を処理すること。
- `src/dsv41/ds4_iq.cuh:73-100` — 対象が prompt expert sets であり、最大 16 行を light kernel が扱うこと。
- `src/dsv41/ds4_gguf.cu:1350-1386,1412-1444` — GGUF set 処理から IQ/MXFP4 の light kernel と tile 経路へつながる呼び出し。
- `CMakeLists.txt:800-811` — DeepSeek-V4.1 実行ファイルを含めるビルド条件。
