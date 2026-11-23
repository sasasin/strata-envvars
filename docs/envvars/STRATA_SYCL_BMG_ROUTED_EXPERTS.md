# `STRATA_SYCL_BMG_ROUTED_EXPERTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

SYCL 実装で Battlemage（Intel GPU 世代）向け routed-expert の最適化を許可する切り替えです。unset は `Auto` として有効扱いになり、無効にすると対象コードは従来の gather・dequant・projection 経路へ戻ります。この変数自体が routed expert の選択や数を変える処理はありません。読み取りと有効判定は `strata::bmg::experts_enabled()` に集約されています（`engine/sycl/src/bmg_prefill_options.hpp:10-19`）。

有効時は、条件に合う routed row の scatter（`engine/sycl/src/prefill/bmg_expert_rows.hpp:41-51`）、expert 重みの転送と FP16 expert group pipeline（`engine/sycl/src/prefill/prefill.cpp:4656-4689,4806-4849`）、ビルドされている場合の TLA gate/up・direct expert kernel（同 `4806-4830,4945-4984`）、特定形状の Battlemage native dequant kernel（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6995-7016`）が選択可能になります。実際に使うかは各節の backend・shape・workspace 条件にも依存します。

## 値と判定

`env_tri()` は `std::getenv()` の結果を未設定なら `Auto`、設定済みで文字列全体が厳密に `"1"` なら `Enabled`、それ以外なら `Disabled` にします。`experts_enabled()` は `Disabled` 以外を true とし、その結果を関数内 `static const` に保存します（`engine/sycl/src/bmg_prefill_options.hpp:10-19`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL 実行時 | `Auto`。有効扱い | `1`（文字列全体の完全一致） | 空文字、`0`、`01`、`true`、`on`、` 1` など、`1` と完全一致しない設定値 |

数値変換、空白除去、大文字小文字変換、範囲検査はありません。設定済みで値が空でも無効です。CLI 引数や別設定による値の上書きはこの helper にはありません（同 `10-19`）。

## 有効になる条件

- 対象は Strata の SYCL engine 内の分岐です。特に Battlemage 専用処理は Level Zero backend と `IntelGpuGen::Battlemage` の両方を検査します（`engine/sycl/src/prefill/bmg_expert_rows.hpp:43-49`; `engine/sycl/src/prefill/prefill.cpp:4656-4659,4832-4835`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7002-7015`）。
- row scatter の専用実装は `tokens` が 1〜8192、expert 数が 10、幅が 2560、input/output が 32-byte aligned で、Level Zero 上の Battlemage の場合だけ使われます。条件を満たさない場合は呼び出し元で `gather_rows16()` に戻ります。peer/multi-GPU prefill (`m.pp`) も専用 scatter を呼ばず従来経路です（`engine/sycl/src/prefill/bmg_expert_rows.hpp:41-51`; `engine/sycl/src/prefill/prefill.cpp:4256-4266`）。
- Battlemage prefetch / pipeline には in-order compute queue、必要な場合は in-order copy queue、非 `stream_all` など追加条件があります。FP16 group はさらに長さ、format、workspace、診断設定などで制限されます。条件外では通常の staging・FP16 chain が続きます（`engine/sycl/src/prefill/prefill.cpp:4656-4689,4832-4849,4931-5020`）。
- TLA gate/up と direct expert kernels は `STRATA_HAS_TLA_EXPERT_GU` が定義された build でのみコードに含まれます。CMake は `STRATA_SYCL_TLA_EXPERT_GU`、Level Zero、portable/Battlemage AOT target、および必要な sycl-tla header に応じてこの macro と kernel source を有効化します（`engine/sycl/CMakeLists.txt:338-373`）。実行時も `bmg_gate_up::supported(queue)` 等の判定が必要で、TLA gate/up が実行できない場合は FP16 GEMM と SwiGLU に進みます（`engine/sycl/src/prefill/prefill.cpp:4806-4830`）。
- expert window は別の `STRATA_SYCL_BMG_EXPERT_WINDOW` が `1`（または未設定の Auto）であることも必要です。この対象変数が無効なら window を有効化せず、さらに非 split・非 batched、TLA build、in-order Level Zero Battlemage queue が必要です（`engine/sycl/src/bmg_prefill_options.hpp:21-24`; `engine/sycl/src/prefill/prefill.cpp:5819-5835`）。window が有効でも、streaming model/cache、8192-token chunk plan、対応 expert geometry・workspace などを満たさなければ通常の `run()` に戻ります（同 `5841-5848,5945-5956`）。

## 実行時の詳細

設定は `experts_enabled()` の最初の呼び出し時に一度読み取られ、`static const` の値としてプロセス内に保持されます。したがって、その後の環境変更はこの判定に反映されません（`engine/sycl/src/bmg_prefill_options.hpp:16-19`）。

環境変数は複数の prefill 層で同じ判定に使われます。専用 row scatter が選ばれないときは通常の `gather_rows16()` に戻り、TLA gate/up が未ビルド・非対応・実行失敗の場合は FP16 GEMM/SwiGLU 経路を使います（`engine/sycl/src/prefill/prefill.cpp:4256-4266,4822-4830,4917-4931`）。有効値でもこれらの条件を満たさない経路では専用処理は実行されません。

## ログと測定値

この変数の値を直接表示するログはありません。関連する expert window は、window mode が明示的に `1` で有効条件を満たさない場合、stderr に `strata: expert window disabled: <理由>` を出します。理由は `routed experts are disabled`、`split or batched execution`、`TLA expert kernels were not built`、または queue/backend/device の条件文です。Auto の window mode ではこの理由ログを出しません（`engine/sycl/src/prefill/prefill.cpp:5819-5835`）。

FP16 grouped routed-expert path が実行され、かつ `STRATA_TRACE` が設定されていると、stderr に `strata trace: Battlemage grouped routed expert projections` を一度出します（同 `4931-4937`）。この変数による性能測定値は調査対象ソースから確認できません。

## 根拠

- `engine/sycl/src/bmg_prefill_options.hpp:10-24` — 値の三状態判定、cache、window 用の別設定。
- `engine/sycl/src/prefill/bmg_expert_rows.hpp:41-51` — routed row scatter の条件。
- `engine/sycl/src/prefill/prefill.cpp:4256-4266,4656-4689,4806-4849,4931-5020` — row gather fallback、expert prefetch/grouping と TLA/F16 fallback。
- `engine/sycl/src/prefill/prefill.cpp:5819-5835,5841-5848,5945-5956` — expert window の条件・fallback・ログ。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6995-7032` — Battlemage native dequant 選択と通常 dequant fallback。
- `engine/sycl/CMakeLists.txt:338-373` — TLA expert kernel build 条件。
