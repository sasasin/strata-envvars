# `STRATA_MMQ_WS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の実験ビルドで、MoE の prompt 読み込み中に条件を満たす layer の gate/up と down を weight-stationary kernel に切り替える opt-in です。通常の per-group MMQ では 16-expert group ごとに積を処理しますが、この経路では layer の gate/up を一度、全行の SwiGLU 量子化を一度、down を一度実行します。環境変数が有効でも、全 layer や decode 経路を一律に切り替えるものではありません（`include/strata/prefill/moe_ws.hpp:1-9,17-20`、`src/prefill/prefill.cpp:4722-4729,5404-5417`）。

## 値と判定

`src/prefill/moe_ws.cu:51-70` で `std::getenv("STRATA_MMQ_WS")` の戻り値を `std::atoi(e) == 1` と比較します。文字列全体の検証はありません。C の `atoi` が先頭の空白と符号を許し、先頭の数値部分を変換するため、たとえば `1`, `01`, `+1`, `1abc`, `1.5`, ` 1` は値 1 となり有効です。未設定と空文字、数値部分がない文字列、数値部分が 1 以外の文字列は無効です。オーバーフローを含む範囲外入力の結果は `atoi` の仕様上保証されません。

| 状態 | 判定 |
|---|---|
| unset | 無効（既定値 0） |
| 空文字 | 無効（`atoi("") == 0`） |
| 数値部分が 1 | 形式全体が検証されなくても有効 |
| 数値部分が 1 以外、数値部分なし | 無効 |

有効な値でも後述のビルド・GPU・layer 条件を満たさなければ従来の per-group MMQ が使われます。専用 CLI 引数による上書きは確認できません。テスト用 `ws::set_mode()` は別の内部 override ですが、通常の利用者向け CLI ではありません（`src/prefill/moe_ws.cu:45-59`、`include/strata/prefill/moe_ws.hpp:27-30`）。

## 有効になる条件

環境値が有効になるには、CUDA で `STRATA_EXPERIMENTAL_SM60` を有効にしたビルドでなければなりません。この場合にのみ weight-stationary kernel 群が `strata_mmq` に追加され、`STRATA_PREFILL_WS` が定義されます。HIP、gfx906、通常の非実験ビルドでは環境値を読む実装がなく、`prefill.cpp` の stub が `mode() == 0` を返します（`CMakeLists.txt:2151-2159,2299-2304`、`src/prefill/prefill.cpp:131-141`）。実装はさらに `cudaGetDeviceCount` で取得する全可視 GPU が少なくとも 1 台あり、すべて compute capability 6.0 (`major == 6 && minor == 0`) の場合だけ mode を有効にします。問い合わせ失敗、GPU 0 台、または 1 台でも異なる capability の GPU があれば無効です（`src/prefill/moe_ws.cu:60-67`）。

mode が有効でも、prompt の MMQ layer ごとに以下をすべて満たす場合だけ切り替えます（`src/prefill/prefill.cpp:4722-4750`）。

- native expert layout であり、cache と host residency 情報が存在する。
- expert がすべてこの GPU に常駐し、peer 側・CPU 側に割り当てられた expert がなく、全 `T*K` 行をローカル処理する。stream-all の場合も当該 layer に stream 境界がない。
- fused buffer、MMQ direct、WMMA 経路、Hadamard gate/up または down、tail 付き format、FP4 activation を使わない。`STRATA_DBG_NAN` が設定されていない（値内容ではなく設定有無の判定）。
- gate/up と down の形式が kernel 対応形式である。gate/up は IQ2_XXS、IQ2_XS、IQ2_S、IQ3_XXS、IQ3_S、down は Q2_0 または IQ4_NL。
- この layer の routed rows / expert 数 `u` において、両積とも実装内の測定比テーブルによる `faster()` 判定を通る。
- expert cache の base、各 expert offset、down offset が 8-byte alignment 条件を満たす。

このため通常の CUDA build、異なる GPU を混在させた可視デバイス構成、decode、非対応モデル形式、expert が RAM / peer / CPU にある layer などでは切り替わりません。ビルド条件の説明は `docs/OLDER_GPUS.md:186-196` にもあります。

## 実行時の詳細

最初に `ws::mode()` が呼ばれたときに環境値と GPU 条件を判定し、結果を関数内 `static const int` に保存します。以降は同一プロセスで環境値や可視 GPU 構成を変えても再判定されません。最初の呼び出しは、MMQ 用作業領域の必要量計算（`src/prefill/prefill.cpp:1663-1666`）や確保・carve（同 `1842-1845,2576-2585`）を含むため、prompt layer 実行時より前に起こり得ます。各 layer では適格性を確認し、resident expert の offset と chunk 表を組み立てて GPU に渡します。表の upload に失敗すると prefill は `false` を返し、エラー文字列 `prefill: the weight-stationary tables' upload failed` を設定します（同 `4757-4780`）。

選択された layer は gate/up kernel、全行の `mmq::swiglu_quant`、down kernel の順です。gate/up が予期せず対象外を返すと、`prefill: the weight-stationary gate/up declined a layer it was picked for` を設定して `false` を返します。down の未対応型にも stderr へ `prefill ws: down type %d has no kernel` を出して `exit(1)` する分岐がありますが、通常の選択条件では対応 down 型に限定されています（`src/prefill/prefill.cpp:5404-5417`、`src/prefill/moe_ws.cu:122-161`）。切り替えが実際に起きた際、プロセス内で最初の layer について stderr に `strata prefill: a resident layer's experts weight-stationary, one launch per product (STRATA_MMQ_WS=1)` を一度出します。値が無効、GPU 条件が不一致、または適格 layer がない場合にこの機能専用の警告や無効理由ログはありません（同 `4751-4756`）。

## 資料との照合

`docs/OLDER_GPUS.md:186-196` は、4 枚の GP100 で全 expert が常駐する条件の prompt 読み込みについて、著者の測定値として 240-token read が 2,156→1,364 ms、fresh 26K read が 41,231→28,555 ms（31–37%短縮、各 arm 1 回）と記載し、decode は不変、プロジェクト側では未測定としています。この文書は既存資料の記述を照合したもので、測定を再実行・検証したものではありません。weight-stationary kernel 自体は GP100 でチューニング・検証したものとコードに記されています（`src/prefill/moe_ws.cu:18-31,60-67`）。

## 根拠

- 読み取り、値の変換、GPU 条件、cache: `src/prefill/moe_ws.cu:45-73`。
- 対応形式、dispatch の型と `faster()` 判定: `src/prefill/moe_ws.cu:23-41,91-102,122-161`。
- ビルド条件と非対応 build の stub: `CMakeLists.txt:2151-2159,2299-2304`; `src/prefill/prefill.cpp:131-141`。
- workspace の確保、layer 条件、resident 判定、ログ、upload failure、実行順: `src/prefill/prefill.cpp:1663-1666,1842-1845,2576-2585,4722-4780,5404-5417`。
- 実装の役割・資料上の測定: `include/strata/prefill/moe_ws.hpp:1-9,17-20`; `docs/OLDER_GPUS.md:186-196`。
