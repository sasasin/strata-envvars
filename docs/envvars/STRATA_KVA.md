# `STRATA_KVA`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA/HIP の prefill で、長い cold prompt の先頭側を late layer で近似実行する KVA（approximate late-layer prompt read）の要求スイッチです。既定は OFF です。ON の条件を満たすと、設定された split layer 以降の対象層について、prompt の末尾 suffix 以外を state-only などの近似経路に通します。条件を満たさない prompt は通常どおり正確に読み取ります。`STRATA_KVA=1` は機能を要求しますが、それだけではすべての prompt に適用されません。実装の概要は `include/strata/prefill/kva.hpp:1-21, 43-49` にあります。

## 値と判定

`include/strata/prefill/kva.hpp:152-156` で値を読みます。文字列全体や数値としては parse せず、環境変数が未設定でなく、かつ空文字でなく、先頭文字が `0` 以外なら ON です。

| 値 | 要求状態 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| `0`、`0anything` | OFF |
| `1`、`true`、`false`、`2`、先頭が `0` 以外の任意の非空文字列 | ON |

空白や大文字小文字の検査、末尾文字の検査はありません。したがって文字列 `false` も ON です。ON/OFF を反転する CLI 引数や、別の環境変数との優先順位処理はこのスイッチにはありません。設定値は `KvaConfig` の初期化時に一度取り込まれ、`kva_config()` の関数内 `static const` にプロセス内で保持されます。通常の実行中に環境を変更しても再読込されません（`include/strata/prefill/kva.hpp:191-195`）。

Metal build では `kKvaBackend` が false なので、値が ON 相当でも `k.on` は false にされます。一方 `explicit_on` は backend 判定前に保存されるため、要求の有無を診断ログに使えます（`include/strata/prefill/kva.hpp:43-49, 152-156`）。

## 有効になる条件

`kva_config().on` が true でも、個別の prefill が次の条件を満たさなければ近似は適用されません（`include/strata/prefill/kva.hpp:104-133`; `src/prefill/prefill.cpp:2947-2966`）。

- 対象実装に state-only late-layer 経路があること。CUDA/HIP は対応し、Metal は非対応です。SYCL engine は独自の prefill 経路で KVA を実装していません（`include/strata/prefill/kva.hpp:43-49`; `docs/KVA.md:102-103`）。
- engine 起動時に batch slots（`--batch`）、複数 GPU の layer split、peer device（`--peer-device`）で全体無効化されていないこと。要求時は起動時に理由を stderr に出します（`src/program/generate.cpp:6257-6278`）。
- cold read であること（`pos0 == 0`）、一段で trunk 全体を読むこと、画像 prompt でないこと、DFlash2 drafter 用 tap がないこと（`include/strata/prefill/kva.hpp:115-121`）。
- prompt 長 `n` が `STRATA_KVA_MIN_PROMPT` 以上で、かつ `n > effective_suffix() + 64` であること。既定の最小長は 4096、suffix は 2048 token です（`include/strata/prefill/kva.hpp:54-57, 85-96, 122-129`）。
- モデル形状が既定の測定対象（48 layers、512 experts）であること。異なる形状では通常適用されず、`STRATA_KVA_ANY_MODEL` が有効なら適用を許可して一度警告します（`include/strata/prefill/kva.hpp:130-133`; `src/prefill/prefill.cpp:2953-2962`）。

batch、layer split、peer device による全体無効化は `KvaEngine::blocked` に保存され、prefill の decline 判定に渡されます。モデル形状や prompt の条件は各 read の判定です。近似位置の frontier は `max(0, n - suffix)`、split は `STRATA_KVA_SPLIT` を `[1, layer数]` に clamp した値で、chunk 全体が frontier より前にある場合に近似対象となります（`src/prefill/prefill.cpp:2947-2966, 3116, 3382-3389, 3621-3628`）。

## 実行時の詳細

設定の取得は `kva_config()` の初回呼び出し時です。generate 起動時に backend と `--batch` / multi-GPU / `--peer-device` の条件を確認し、個々の prompt は `Prefill::run_impl()` 内で条件判定します（`include/strata/prefill/kva.hpp:191-195`; `src/program/generate.cpp:6263-6278`; `src/prefill/prefill.cpp:2936-2966`）。KVA が選ばれた範囲は、layer split 以降の対象層で近似実行されます。既定では state-only 経路で late layer の状態を進めます。近似しない suffix は完全計算されます（`include/strata/prefill/kva.hpp:3-9, 72-90`; `src/prefill/prefill.cpp:3116, 3382-3389, 3621-3628`）。

CLI に同名の優先設定はありません。Strata Terminal の「Faster long prompts」設定は `STRATA_KVA=1` を環境へ書き込む UI 経路です（`apps/host/server/native-settings.mjs:34-42`）。

KVA が実行された read は stderr に `strata prefill: KVA on: ...` と、適用された場合の近似位置に関する説明を出します。要求が ON でも条件不成立なら `strata prefill: KVA configured but NOT applied: ...` と理由を出します。batch / peer device 等でプロセス全体が無効の場合は `strata generate: KVA ... is off here: ...`、Metal で要求した場合は `strata generate: STRATA_KVA is set, but this build has no state-only late-layer path; every prompt is read exactly` を stderr に出します（`src/prefill/prefill.cpp:5820-5856`; `src/program/generate.cpp:6266-6277`）。KVA を要求しない通常状態では、この KVA 設定・不適用ログは出ません。

## 根拠

- 値の読み取り・判定、backend 条件、設定 cache: `include/strata/prefill/kva.hpp:43-49, 137-156, 191-195`。
- KVA の read 条件、既定値、suffix、形状制限: `include/strata/prefill/kva.hpp:54-57, 104-133`。
- generate 起動時の全体無効条件とログ: `src/program/generate.cpp:6257-6278`。
- 個別 read の条件、適用位置、モデル形状警告、stderr の適用・不適用ログ: `src/prefill/prefill.cpp:2936-2966, 3116, 3382-3389, 3621-3628, 5820-5856`。
- SYCL 実装についての記述: `docs/KVA.md:102-103`。
- Terminal 設定からの値の設定: `apps/host/server/native-settings.mjs:34-42`。
