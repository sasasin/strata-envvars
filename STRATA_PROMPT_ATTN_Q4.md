# `STRATA_PROMPT_ATTN_Q4`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の Q4_0 KV prompt attention で、専用の tensor-core kernel（mode 4）を使うか、従来の QSA decode attention kernel に fallback するかを切り替えます。変数を `0` 始まりの値にすると fallback を選びます。Q4_0 KV 以外の prompt attention には作用しません。

## 値と判定

| 環境変数の状態 | `q4_off` | 結果（ほかの適用条件を満たす場合） |
|---|---:|---|
| 未設定 | false | mode 4 を試す |
| 空文字 | false | mode 4 を試す |
| 先頭文字が `0`（例: `0`, `01`, `0abc`） | true | 専用 kernel を使わず fallback |
| 先頭文字が `0` 以外（例: `1`, `true`, `false`, ` 0`） | false | mode 4 を試す |

数値変換や文字列全体の比較はせず、`getenv()` の結果が存在し、先頭文字が `'0'` かだけを検査します。大文字小文字や後続文字は判定に影響しません。値を読み取る結果は関数内の `static const bool` に保存されます。

## 有効になる条件

- `STRATA_PROMPT_ATTN_OLD` が設定されていないこと。設定されていると prefill 側が専用 kernel 呼び出し自体を飛ばし、decode kernel を使います。
- CUDA の Q4_0 KV pools を使っていること（`pools.k_q4 != nullptr`）。K8V4 hybrid KV は別分岐です。
- QSA prompt kernel の形状・入力条件（`n_q > 0`、head dimension、head 数、`cap`、selection / page table 等）を満たすこと。
- 有効な compute capability が 8.0 以上であること。コードは `cc < 80` を Turing とし、Q4 mode 4 を拒否します。`STRATA_QSA_WARP=1` または `attn` は capability 値を 7.5 に上書きするため、この場合も mode 4 は拒否されます。
- `pools.v_q4` が存在すること。
- CUDA が kernel の dynamic shared memory 属性を設定できること。設定に失敗すると launch helper は `false` を返し、呼び出し元の fallback に進みます。

条件を満たさず `qsa_prompt_attn_batch()` が `false` を返した場合、呼び出し元は `qsa_decode_attn_batch()` を `m.attn_batch` 単位で実行します。HIP の関数は HIP 専用分岐で WMMA 対応の int8 条件を処理した後、それ以外は `false` を返して関数を抜けるため、この Q4 判定には到達しません。SYCL 版は XMX kernel を試し、成功しなければ `false` を返しており、XMX 実装も Q4_0 pools を拒否します。そのため SYCL でも当該変数は選択に使われません。

## 実行時の詳細

prefill の QSA 層では、`STRATA_PROMPT_ATTN_OLD` が未設定なら `qsa_prompt_attn_batch()` を呼びます。CUDA で Q4_0 KV かつ上記条件を満たし、`STRATA_PROMPT_ATTN_Q4` が未設定または `0` 以外で始まる値なら mode 4 を launch します。この kernel は Q4_0 の K/V block の nibble code を int8 code に展開し、block の FP16 scale とともに attention 計算へ渡します。

環境変数は CUDA の Q4_0 分岐に初めて入ったときに評価され、その後は process 内でキャッシュされます。最初の評価後に環境を書き換えても反映されません。fallback 自体にこの変数固有のログはありません。kernel launch 時の CUDA エラーは `qsa_prompt_attn_batch: <CUDA error>` を stderr に出して終了します。

## 根拠

- `src/kernels/cuda/qsa_prompt_attn.cu:1453-1522` — device capability 判定、HIP の早期 return、Q4_0 pools と `STRATA_PROMPT_ATTN_Q4` の判定、mode 4 と fallback 用 `false` の選択。
- `src/kernels/cuda/qsa_prompt_attn.cu:162-193` — mode 4 の Q4_0 K/V block 読み込み、code 展開、scale の適用。
- `src/kernels/cuda/qsa_prompt_attn.cu:715-738` — kernel launch と CUDA エラー時の stderr / 終了処理。
- `src/prefill/prefill.cpp:2865-2877` — `STRATA_PROMPT_ATTN_OLD` による呼び出し迂回、および `false` 時に `qsa_decode_attn_batch()` を呼ぶ fallback。
- `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2007-2010,2022-2032` — SYCL では XMX を試してから return し、後段の Q4 判定に進まない。
- `sycl/src/kernels/cuda/qsa_prompt_attn_xmx.dp.cpp:364-383` — XMX 実装は Q4_0 pools を拒否。
- `docs/NVIDIA_V100.md:33-35` — Q4_0 KV は decode kernel を使うという説明。
- `docs/INTEL.md:632-633` — SYCL port で Q4_0 tensor-core prompt attention を移植していないという記述。
