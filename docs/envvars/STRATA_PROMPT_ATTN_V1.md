# `STRATA_PROMPT_ATTN_V1`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の QSA prompt attention で、int8 KV を使う場合に旧版カーネルを選ぶための診断・比較用スイッチです。適用される GPU では、未設定時の cp.async 版と、設定時の v1 版で浮動小数点の加算順序が異なります。これは prompt attention の実行経路を選ぶもので、QSA が選んだセルや入力 KV を変えるスイッチではありません。

## 値と判定

`std::getenv("STRATA_PROMPT_ATTN_V1") != nullptr` だけで判定し、値の parse や文字列比較はありません。

| 環境変数 | CUDA での判定 |
|---|---|
| unset | `v1=false`。対象 GPU では `launch_i8()` を選ぶ |
| 空文字を含む任意の設定値 | `v1=true`。対象 GPU では `launch<1>()` を選ぶ。`0`、`false`、不正な数値文字列も同じ |

判定結果は `static const bool` に保存されます。プロセス内で最初に int8 KV の分岐へ到達したときに読み、その後に環境を変更しても再評価しません。

## 有効になる条件

- CUDA の `qsa_prompt_attn_batch()` が呼ばれ、形状が `head_dim == HD`、`n_head == G * n_head_kv`、`cap > 0` で、`ids`、`steps`、page table が有効であること。
- K と V が通常の int8 KV（`pools.k_q`, `pools.v_q`, 両 scale が存在）であること。Q4_0 K/V は先行する Q4 分岐、int8 K + Q4 V の hybrid は別分岐に入るため、この変数では切り替わりません。FP16 KV も対象外です。
- Ampere（sm_80）以降では、未設定なら cp.async を使う `launch_i8()`、設定済みなら `launch<1>()` を選びます。Volta（sm_70）は `launch70<1>()`、Turing（sm_75）は `launch<1>()` が元から選ばれるため、この変数の有無で経路は変わりません。さらに CUDA では `STRATA_QSA_WARP` が `1` または `attn` だと検出 compute capability を 75 として扱うため、sm_80 以降でも `launch<1>()` が選ばれ、この変数の効果はなくなります。sm_70 未満はこの関数が早期に `false` を返し、呼び出し元が旧 decode kernel に fallback します。
- HIP ビルドでは CUDA 分岐に入る前に HIP 専用判定を行い、WMMA を使えない場合は `false` を返します。このため `STRATA_PROMPT_ATTN_V1` は HIP 経路を選びません。

## 実行時の詳細

本番 prefill は `STRATA_PROMPT_ATTN_OLD` が設定されている場合、`qsa_prompt_attn_batch()` を呼ばず、query を小分けにして `qsa_decode_attn_batch()` を使います。この場合 `STRATA_PROMPT_ATTN_V1` は実際の prefill 経路を変えません。両変数が未設定で、CUDA・int8 KV・Ampere 以降などの条件を満たすと、この変数だけで v1 と cp.async 版を比較できます。カーネル起動が成功すれば同じ `attn` 出力バッファに結果を書きます。launch 設定エラー時は `qsa_prompt_attn_batch` が stderr に CUDA エラー文字列を出して `exit(1)` します。

ソースコメントは v1 を「同じ精度で、別の summation order」と説明しています。ヘッダーは prompt tensor-core カーネルの結果が decode FP32 kernel と bitwise 一致せず、parity と prompt quality gate で差を評価すると説明しています。`docs/DETAILS.md` および確認した関連 docs に、この環境変数固有の性能測定値や独立した品質保証値は見つかりませんでした。したがって、全モデルで同一出力になることや速度差は断定できません。

SYCL の移植ファイルにも同名の参照がありますが、その関数は XMX 試行後に `return false` する制御があり、当該読み取り行より前に到達不能です（`sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2007-2010,2039-2047`）。このファイルは DPCT による移植コードであり、上記の有効な本番挙動の根拠にはしていません。

## 根拠

- `src/kernels/cuda/qsa_prompt_attn.cu:1453-1522`: 呼び出し条件、HIP の早期 return、KV format ごとの分岐、sm 世代と v1/cp.async の選択。`STRATA_QSA_WARP` の検査は 1474-1481 行。
- `src/kernels/cuda/qsa_prompt_attn.cu:425-430,464-468,679-707,709-738`: int8 cp.async 版と v1 共通カーネルの実装・起動箇所。
- `include/strata/kernels/qsa_prompt_attn.hpp:1-18,27-30`: prompt tensor-core 経路と decode 経路の差、bitwise 一致ではない旨、インターフェース。
- `src/prefill/prefill.cpp:2865-2878`（SYCL prefill: `sycl/src/prefill/prefill.cpp:3160-3192`）: `STRATA_PROMPT_ATTN_OLD` による bypass と decode fallback。
- `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2039-2047`: 移植ファイル上の同名参照。到達不能コードのため実挙動の根拠には不使用。
