# `STRATA_KQ_GU_LANES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の grouped expert kernel が gate/up 行を処理する lane kernel で、K-quant 系など `KqSplit<TG>::has` が真の形式に使う lane 数を個別に選ぶ。共通設定 `STRATA_GU_LANES` とは別の値を指定できる。1 work-group は 256 work-item で、選んだ lane 数が 1 行を分担し、1 work-group あたりの行数は `256 / lanes` となる。lane 数は dot の分割と reduction にも使われるため、単なる並列度の設定ではない。実装は `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4478-4487, 2618-2633, 5940-5949`。

これは環境変数を読む Strata の SYCL 実装に対する設定であり、CUDA・HIP・Metal 実装の設定ではない。SYCL の grouped expert 経路が lane kernel を選んだ場合に限り、gate/up の計算分割を変える。down 行の lane 数には `STRATA_DOWN_LANES` が使われ、この変数は影響しない（同 `:5991-5999`）。

## 値と判定

`kq_gu_lanes()` は初回呼び出し時に `std::getenv` で設定有無を確認する。未設定なら `gu_lanes()` の値を使い、設定されていれば `lanes_env()` が `std::atoi` で整数変換する。変換結果が `4`, `8`, `16`, `32` のいずれかなら採用し、それ以外は compile-time 定数 `kExpertLanes` に戻す。空文字も「設定あり」なので `atoi("") == 0` から `kExpertLanes` へ戻る。`atoi` は文字列全体の厳密な検証ではなく、先頭の空白・符号や数値部分の後ろの文字を許す（例: `" 16x"` は 16）。大文字小文字の概念はない。実装位置: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4481-4487, 4518`。

| 条件 | unset | 有効になる値（例） | 無効値の例と結果 |
|---|---|---|---|
| SYCL lane kernel で `TG != 23` かつ `KqSplit<TG>::has` | `STRATA_GU_LANES` を同じ規則で評価した値 | `4`, `8`, `16`, `32`; `"16x"` や `" 4"` も `atoi` 結果が許可値なら採用 | `""`, `0`, `1`, `3`, `33`, `-4`, `true`, `0anything` は `kExpertLanes` に戻る |
| 上記以外（形式または経路が対象外） | `STRATA_KQ_GU_LANES` を参照しない | なし | lane 選択は通常経路側の規則に従う |

`STRATA_GU_LANES` が未設定・無効の場合の既定は `kExpertLanes` であり、ソースでは `STRATA_EXPERT_LANES` がビルド時に上書きされない限り 8（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1173-1180, 4486`）。注意点として、`STRATA_KQ_GU_LANES` を明示して無効値にした場合は `STRATA_GU_LANES` へ戻らず、直接 `kExpertLanes` へ戻る。

## 有効になる条件

- Strata が SYCL backend を含めてビルドされ、その grouped expert 実装が呼ばれること。このファイルは SYCL の `iq_kernels` 構成に含まれる（`engine/sycl/CMakeLists.txt:273-282`）。
- gate/up の lane dispatch が `launch_gu_lanes()` に到達すること。通常の `launch_gu()` は形式・旧 kernel 設定・`STRATA_EXPERT_SPLIT` の状態に応じて lane kernel または multi-entry kernel を選ぶ（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3932-3937, 6053-6067`）。multi-entry kernel 側に進む場合、この変数で lane 数を選ばない。
- lane dispatch された形式で `KqSplit<TG>::has` が真で、かつ `TG != 23` であること。trait は Q4_0/Q4_1、Q5_0/Q5_1、Q8_0、Q4_K/Q5_K/Q6_K、NVFP4 および trellis 形式などに定義されている。IQ4_XS (`TG == 23`) は明示的に `STRATA_GU_LANES` を使う（同 `:2592-2616, 5940-5949`）。
- fused GU 経路に入ると、この変数は参照されず lane dispatch を通らない。たとえば `STRATA_EXP_MODE` が 8 で、他の fused 条件も満たす経路は `gu_lanes() == 8` を条件に fused kernel を起動する（同 `:7740-7751, 7797-7819`）。
- この変数を unset にした場合の継承元は `STRATA_GU_LANES`。明示した許可値はその値に置き換わり、`STRATA_GU_LANES` より優先される。CLI 引数による上書きはこの関数内にはない。

## 実行時の詳細

読み取り値は `kq_gu_lanes()` 内の関数ローカル `static const int` に初回呼び出し時だけ保存される。`gu_lanes()` も別の static 値として初回評価されるため、プロセス実行中に環境を変更しても、評価済みの lane 数は更新されない（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4486-4487, 4518`）。

lane kernel では各行の dot work を選択 lane 数に分け、`lanes_sum<LANES>` で部分和をまとめる（同 `:2618-2633`）。ソースコメントは lane split により reduction order が異なる旨を明記しているため、異なる lane 数で浮動小数点結果が bitwise 同一とは限らない（同 `:4515-4518`）。値は gate/up 出力の計算に関わるが、この環境変数について token 選択や生成結果の同一性を保証する記述は確認できない。

K-quant split 自体の選択には別状態 `g_kq_split`（環境変数 `STRATA_KQ_SPLIT` または `native_expert_set_kq_split()`）も関係する。一方、この変数の lane 数判定は `KqSplit<TG>::has` を見ており、`STRATA_KQ_SPLIT=0` のときも lane kernel を通る経路では lane 数の選択が残る（同 `:5920-5937, 5940-5949`）。

## ログと測定値

この変数の読み取り、許可値への fallback、lane 選択に固有のログ・警告・エラーはない。無効値でも値を `kExpertLanes` に戻して処理を続ける。kernel 起動後には grouped GU の通常の `check("native_expert_grouped/gu")` が呼ばれるが、これはこの変数固有の検査ではない（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4481-4485, 7883`）。

ソースコメントには B70 の 4-token window における 8/16 lane の比較値があるが、この文書では現行環境での測定結果として扱わない（同 `:4515-4518`）。

## 根拠

- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1173-1180` — compile-time 既定 lane 数。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:2592-2616` — `KqSplit<TG>::has` の対象型。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:2618-2633` — lane ごとの dot 分割と reduction。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4478-4487, 4515-4518` — env 値の変換、fallback、対象変数の cache。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5920-5949, 6053-6067` — split/lane kernel の選択。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7740-7751, 7797-7819, 7849-7879` — fused・専用経路と lane dispatch。
- `engine/sycl/CMakeLists.txt:273-282` — SYCL kernel 構成。
