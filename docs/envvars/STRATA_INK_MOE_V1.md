# `STRATA_INK_MOE_V1`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling-2 MoE の CUDA ディスパッチで、条件を満たす SF4-only または MX8-only 層について、書き換え版 `k_ink_moe_fp16tc_v2` の代わりに共通カーネル `k_ink_moe_sf4_mx8_fp16tc` を選ぶための切替です。`STRATA_INK_MOE_V1` の有効値は旧側の共通カーネルを選びます。未設定または無効値では、残りの条件も満たせば形式別の v2 カーネルを選びます（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3747-3766`）。

この判定はルーターや Top-8 選択の後、専門家の計算カーネルを決める段階にあります。ルーターの計算・選択と最終的な 8 スロットの加重和はこの変数による分岐の外です（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3637-3663, 3864-3889`）。実装コメントは v2 を「same results bit for bit」と説明していますが、ここでは性能差を示す測定値は確認できません（同 `:3751-3752`）。

## 値と判定

`std::getenv` の結果が null でなく、先頭 1 文字が ASCII の `'1'` のときだけ真です。文字列全体の比較や数値変換はしません（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3750`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `launch_ink_moe_dispatch_only` の該当分岐に到達 | false | `1`, `10`, `1anything` | 空文字, `0`, `0anything`, `true`, ` 1`, `01` |

無効値はエラーや fallback ログを出さず、`moe_v1 == false` として扱われます。そこから v2 が選ばれるかどうかは下記の層形式などの条件にも依存します（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3750-3766`）。

## 有効になる条件

- Inkling-2 CUDA 実装の `launch_ink_moe_dispatch_only` で、SF4 または MX8 の expert を処理すること（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3665-3675, 3724-3726`）。
- `use_fp16_tc` が真であること。これは `M >= 24`、`ink_has_int8_tc()` が真、かつ Blackwell `sm120` 分岐を使わないときに成立します。能力判定は CUDA device capability をデバイスごとに cache します（同 `:3678-3680, 2305-2311`）。
- 64-token prefill カーネルの `use_pf_tile` 分岐を通らないこと。同分岐は `STRATA_INK_PF_TILE` が先頭 `'0'` でなく、`M >= kInkPrefillTileMinM`（256）で、SF4/MX8 層がある場合に選ばれます。したがって環境変数の判定がある 16-row FP16 TC 分岐は、これらの条件に該当しないときだけです（同 `:3681-3687, 3740-3750`; `engine/src/inkling2/cuda/ink_moe_prefill.cuh:17`）。
- この FP16 TC 分岐の中で、v2 の条件 `info.has_sf4 != info.has_mx8 && !info.has_sk && !info.has_gguf && !info.mixed_gu_dn` を満たす場合に限り、値の違いでカーネル選択が変わります。有効値なら条件末尾の `!moe_v1` が偽となり共通カーネルへ進みます。無効値なら SF4-only/MX8-only の v2 に進みます。混在形式、S_K/GGUF expert、混合 gate/up と down の層では、値にかかわらず共通カーネルです（同 `:3750-3766`）。
- `use_sm120_tc` 分岐、prefill tile 分岐、Tensor Core を使わない分岐、WMMA 専用の別経路ではこの変数は選択に使われません（同 `:3678-3687, 3724-3782`）。
- ソース内の候補名検索では、実際の環境読み取りはこの CUDA ヘッダーの 1 箇所です。`docs/SETTINGS.md:399` は対象を「NVIDIA and AMD」と記載していますが、確認した読み取り・利用箇所は CUDA 実装です。この実装だけから AMD backend での有効性は確認できません。

## 実行時の詳細

ルーターを実行した後に dispatcher が expert を binning し、上記の hardware・token 数・layer 条件を選びます。該当する FP16 TC 分岐に初めて到達した時点で、関数ローカル `static const bool moe_v1` の初期化として環境を読みます。同一プロセス内の以後の呼び出しでは値を再読しないため、その初期化後に環境を変更しても反映されません。該当分岐に一度も到達しなければ、この変数は読まれません（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3665-3687, 3740-3766`）。

この設定に対応する CLI 引数、別環境変数による上書き、子プロセスへの転送処理は、対象名の全参照と dispatcher の呼び出し経路では確認できません。通常経路は `launch_ink_moe` から router、dispatcher、reduce へ進みます（同 `:3864-3889`）。通常の runner もこの関数を呼びます（`engine/src/inkling2/cuda/ink_runner.cuh:3505-3512`）。

切替自体に伴うログ、警告、終了処理はありません。ここでの差は選択される GPU kernel です。該当する二つの kernel launch の後にこの箇所で結果コードを調べる処理はなく、後続の同期・runtime error の扱いは呼び出し側の一般的な CUDA 経路に委ねられます（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3751-3766`）。

## ログと測定値

この変数の読み取りや選択を知らせるログはありません。調査対象 commit の説明資料から、`STRATA_INK_MOE_V1` の設定別性能測定値は確認できません。カーネルコメントにある同一結果の記述は実装コメントであり、本調査で独立に測定した結果ではありません（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3751-3766`）。

## 根拠

- `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3665-3687` — dispatcher、GPU capability、prefill 条件。
- `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3724-3782` — SF4/MX8 分岐、環境変数による kernel 選択と他経路。
- `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3864-3889` — router・dispatch・reduce の呼び出し順。
- `engine/src/inkling2/cuda/ink_moe_prefill.cuh:17` — prefill tile の最小 token 数。
- `engine/src/inkling2/cuda/ink_runner.cuh:3505-3512` — 通常 runner からの呼び出し。
- `docs/SETTINGS.md:399` — 環境変数一覧の backend 表記との照合。
