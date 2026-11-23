# `STRATA_GROUPED_V1`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP と SYCL の native grouped expert カーネルで、グループ方向の起動グリッドと関連する融合経路を選ぶ A/B 用スイッチです。値を有効にすると旧 grouped 経路（V1）を選び、処理対象グループ数 `cap_groups` 分の block row を起動します。未設定時などは、呼び出し側から渡される `grid_groups` が有効ならその値を使います。入力や出力の選択条件を変更する設定ではありません。ヘッダーの説明では V1 と既定経路は bitwise 同じ結果で、A/B timing 用とされています（`engine/include/strata/kernels/iq_kernels.hpp:140-143`）。

環境からの読み取りは CUDA/HIP 実装と SYCL 実装に各 1 箇所あり、いずれも `env_on` を通じて `g_grouped_v1` の初期値を設定します（`engine/src/kernels/cuda/iq_kernels.cu:3689-3692,6831-6833`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3930,7761-7765`）。

## 値と判定

`env_on(name)` は `std::getenv(name)` の結果が null でなく、先頭文字が NUL でも `'0'` でもない場合に true を返します。文字列全体の parse、数値変換、trim、大文字小文字変換はしません（`engine/src/kernels/cuda/iq_kernels.cu:3689-3692`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3930`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP または SYCL の grouped kernel 実装 | false | `1`, `2`, `true`, `false`, ` 0`（先頭文字が空白） | 空文字, `0`, `0anything`, `0.5` |

したがって `false` という文字列も true 扱いです。先頭文字だけを見るため、後続文字や数値としての妥当性は判定されません。境界値の数値範囲はありません。空文字は「設定済み」でも false です。

## 有効になる条件

- 対象コードを含む CUDA/HIP または SYCL engine が実行され、`native_expert_grouped` まで到達すること。サーバー専用の設定ではなく、このカーネル実装側で読みます（`engine/src/kernels/cuda/iq_kernels.cu:7085-7089`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7767-7775`）。
- 有効値の場合、V1 の group grid は `cap_groups` です。無効値の場合は `grid_groups <= 0` または `grid_groups > cap_groups` なら `cap_groups`、それ以外なら `grid_groups` になります（`engine/src/kernels/cuda/iq_kernels.cu:7184-7185`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7791-7795`）。
- CUDA/HIP では `!g_grouped_v1` が条件に含まれる NVFP4 grouped decode 経路（`cap_entries > 10`、format/type、block/tail、phase、GPU 対応条件を満たすもの）を、有効値で迂回します（`engine/src/kernels/cuda/iq_kernels.cu:7092-7102`）。また V1 は `gu_swiglu_on()` を使う GU+SwiGLU の経路を抑止します（`engine/src/kernels/cuda/iq_kernels.cu:7241-7255`）。
- SYCL では V1 が `STRATA_EXP_MODE=8` 等で選択可能な fused GU 経路を抑止します（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7797-7801`）。また、特定 layout/device 条件に限定された追加 GU 経路も `!v1` を条件とするため、有効値では選ばれません（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7849-7872`）。
- SYCL の `native_expert_grouped_staged` は `g_grouped_v1` が true なら staging 条件を満たさない扱いとして、通常の `native_expert_grouped` に fallback します（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:8427-8443`）。
- 両 backend で V1 は SwiGLU と q8_1 量子化を別 kernel にする側を選びます。gfx906 では `STRATA_HIP_SWIGLU_FUSED` が有効でも `v1` が true なら別経路です（`engine/src/kernels/cuda/iq_kernels.cu:7317-7337`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7884-7946`）。APR の `had_block > 0` も別 kernel 経路を必要とします（同上）。
- V1 でないときも、上記の融合経路が選ばれるにはそれぞれの format、layout、GPU、phase、他スイッチ条件を満たす必要があります。条件不足なら通常の grouped 実装へ進みます。

## 実行時の詳細

`g_grouped_v1` は CUDA/HIP と SYCL の各翻訳単位にある namespace-scope 変数で、ライブラリの静的初期化時に環境を一度読みます。`native_expert_grouped` の各呼び出しでは保存済み bool を使い、環境を再読しません。そのためプロセス起動後に環境を変更しても、この値には反映されません（`engine/src/kernels/cuda/iq_kernels.cu:6831-6832,7184`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7761-7765,7791`）。

CLI 引数、設定ファイル、別の環境変数からこの値を上書きする読み取り経路は見つかりませんでした。宣言済みの `native_grouped_set_v1(bool)` は保存値を書き換えられますが、対象 commit 内でその関数を呼ぶ箇所は宣言・定義以外に見つかりませんでした（`engine/include/strata/kernels/iq_kernels.hpp:140-143`; `engine/src/kernels/cuda/iq_kernels.cu:6891`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7765`）。ヘッダーは graph capture 前の設定を想定し、capture 済み graph は自身の起動構成を保持すると記しています（同ヘッダー:140-143）。

`native_expert_grouped` は GU 計算後に SwiGLU/q8_1 化を行い、その後 down projection を起動します。V1 は GU と down の group grid に `cap_groups` を用い、通常経路の選択にも関わります。CUDA/HIP と SYCL のソースコメントは group grid による結果は変わらないと説明していますが、この調査では build や parity 実行をしていないため、実行結果を独立検証したものではありません（`engine/src/kernels/cuda/iq_kernels.cu:7184-7195,7327-7343`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7791-7795,7893-7950`; `engine/include/strata/kernels/iq_kernels.hpp:140-143`）。

## ログと測定値

この環境変数を読み取ったことや V1 が選ばれたことを示す専用ログはありません。後続 kernel は `check("native_expert_grouped/gu")`、`check("native_expert_grouped/swiglu")`、down の check に渡されますが、チェックの表示内容はここでは変数固有のものではありません（`engine/src/kernels/cuda/iq_kernels.cu:7316-7337,7343-7354`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7883-7982`）。

`docs/DETAILS.md` に本変数の記述は見つかりませんでした。ソースヘッダーは A/B timing 用と説明しますが、本変数による性能測定値は同資料から確認できないため記載しません（`engine/include/strata/kernels/iq_kernels.hpp:140-143`）。

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:3689-3692,6831-6833,7085-7102,7184-7195,7241-7255,7317-7354` — CUDA/HIP の値判定、グリッド、特化経路、SwiGLU/q8_1 化。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3930,7761-7801,7849-7872,7883-7982,8427-8462` — SYCL の値判定、グリッド、融合・特化経路、staged 経路の fallback。
- `engine/include/strata/kernels/iq_kernels.hpp:140-143` — V1 の説明、同一結果との説明、graph capture に関する注記。
