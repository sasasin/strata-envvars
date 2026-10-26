# `DS4_MX_PF`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DS4 の MXFP4 expert を CPU で計算する際、ベクトル化された重み行カーネルが、処理中の重み位置から何バイト先へ prefetch 命令を出すかを指定します。対象は CPU lane の MXFP4 gate/up/down 行計算です。GPU 側の計算や、低 bit IQ expert の CPU lane にはこの変数は使われません。

## 値と判定

`std::getenv()` で値を読み、`std::atoi()` の結果を `std::max(0, ...)` で 0 以上にします。文字列全体の妥当性検査や上限 clamp はありません。

| 環境変数の状態 | `pf` の値 |
|---|---:|
| 未設定 | 0 |
| 空文字、`atoi` が数値として変換できない文字列 | 0 |
| 整数として読める文字列 | `atoi` の結果。ただし負数は 0 |

`atoi` のため、先頭の空白と符号は許され、数値の後ろの文字は無視されます（例: `" 16bytes"` は 16、`"-4"` は 0）。小数の小数部も解釈されません（例: `"3.5"` は 3）。整数範囲を超える入力の結果は C ライブラリの `atoi` の範囲外動作に依存するため、設定値としては扱えません。

根拠: `src/dsv41/ds4_gguf_cpu.cpp:323-326`。

## 有効になる条件

- `mx_rows()` を通る DS4 の MXFP4 CPU expert 計算で使われます。モデル処理側では MXFP4 expert の gate/up と down の行計算からこの関数を呼びます。
- `mx_rows()` は `mx_tier()` が選んだ CPU tier に処理を渡します。ベクトル tier は x86 の対応命令と CPU 機能がある場合だけ選択されます。
- 行列の内側次元 `k` が 256 の倍数でない場合、または指定 tier が CPU で利用できない場合は scalar 経路に切り替わり、先読み距離は使われません。
- scalar 経路では `pf` は参照されず、先読み命令もありません。したがって、値を正にしても全 CPU・全モデルで先読みが行われるわけではありません。

根拠: `src/dsv41/ds4_gguf_cpu.cpp:350-374,393-415`、`src/dsv41/ds4_mx_kern.inc:71-77,186-192`、`src/dsv41/ds4_model.cu:5678-5694,5712-5724`。

## 実行時の詳細

`mx_rows()` 内の関数 static `pf` を初期化するときに一度だけ読み取ります。C++ の関数 static 初期化後に環境変数を変更しても、そのプロセスでは値が再評価されません。`mx_rows_tier()` は選ばれた tier が 256 bit / 512 bit のベクトル kernel の場合に `pf` を kernel へ渡します。各出力行について、内側ループが 256 weight values（8 blocks）進むたびに、現在位置 `p` から `pf` bytes 先へ `_mm_prefetch(..., _MM_HINT_T0)` を発行します。`pf <= 0` では命令を発行しません。

この関数は DS4 model CPU expert path の MXFP4 gate/up 行と down 行の両方で呼ばれます。ソース内の `docs/DETAILS.md` にはこの変数の値や性能測定の説明が見当たらず、既定値以外の推奨値や速度への効果は資料から確認できません。

根拠: `src/dsv41/ds4_gguf_cpu.cpp:323-326,393-415`、`src/dsv41/ds4_mx_kern.inc:71-77,186-192`、`src/dsv41/ds4_model.cu:5680-5693,5712-5724`。

## 根拠

- 環境値の parse と負数の処理: `src/dsv41/ds4_gguf_cpu.cpp:323-326`。
- 値を一度キャッシュして kernel に渡す処理、scalar fallback: `src/dsv41/ds4_gguf_cpu.cpp:393-415`。
- ベクトル kernel における先読み命令: `src/dsv41/ds4_mx_kern.inc:71-77,186-192`。
- DS4 の MXFP4 CPU expert 経路から gate/up と down の計算を呼ぶ箇所: `src/dsv41/ds4_model.cu:5678-5694,5712-5724`。
