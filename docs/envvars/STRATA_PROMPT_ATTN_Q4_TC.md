# `STRATA_PROMPT_ATTN_Q4_TC`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の prompt attention で、Q4_0 形式の K/V cache を処理する tensor-core kernel を Turing（compute capability 7.5）でも選べるようにする opt-in です。通常の Turing 経路ではこの kernel を使わず、呼び出し元が従来の decode attention kernel に fallback します。この変数は Q4_0 経路の選択だけを変え、Q4_0 経路自体を有効化する設定ではありません。

## 値と判定

値全体や数値としての妥当性は parse せず、環境変数の先頭文字だけを判定します。判定は `qsa_prompt_attn_batch()` 内の関数ローカル `static const bool` に保存されます。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（先頭文字が `\0`） |
| 先頭文字が `1` | 有効（例: `1`, `10`, `1anything`） |
| その他 | 無効（例: `0`, `true`, ` 1`） |

最初に Q4_0 経路で判定された後は値を再読込しないため、プロセス実行中に環境を変更しても判定は変わりません。根拠: `src/kernels/cuda/qsa_prompt_attn.cu:2298-2308`。

## 有効になる条件

- `qsa_prompt_attn_batch()` が prompt attention から呼ばれ、query 数が正で、head geometry がこの kernel の compile 時 geometry と一致し、capacity・選択 ID・step table・page table が有効である必要があります。そのうえで Q4_0 K cache（`pools.k_q4`）の分岐に入り、Q4_0 V cache（`pools.v_q4`）も必要です。
- CUDA の Turing（sm_75）では、変数が有効な場合に Q4_0 tensor-core kernel の launch を許可します。未設定または無効なら関数は `false` を返し、prompt 側が従来の `qsa_decode_attn_batch()` に切り替えます。
- Volta（sm_70）は変数にかかわらずこの経路を拒否します。sm_80 以降では Turing 専用の拒否条件がないため、この変数を設定しなくても Q4_0 tensor-core kernel の条件を満たせば launch します。
- `STRATA_PROMPT_ATTN_Q4=0` の場合も Q4_0 tensor-core kernel を拒否します。この別変数は先頭文字が `0` かを判定し、`STRATA_PROMPT_ATTN_Q4_TC=1` だけでは拒否を上書きできません。
- HIP では `qsa_prompt_attn_batch()` が通常の Q4_0 分岐より前に `false` を返すため、この変数は Q4_0 経路を有効にしません。SYCL 側の対応実装 `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp` にこの変数の読み取りはありません。

根拠: `src/kernels/cuda/qsa_prompt_attn.cu:2254-2293,2295-2310`; `src/prefill/prefill.cpp:3260-3271`; `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2027-2029`。

## 実行時の詳細

prompt の QSA attention は `qsa_prompt_attn_batch()` の成功時にその結果を使います。関数が `false` を返すと `src/prefill/prefill.cpp` は query を `m.attn_batch` ごとに分け、`qsa_decode_attn_batch()` で計算します。Q4_0 K/V は kernel 内で KV mode 4 として扱われ、Q4_0 block の値を int8 code として取り込み、FP32 で scale を適用します。`STRATA_PROMPT_ATTN_Q4_TC` 自体に専用ログ出力はありません。

`docs/NVIDIA_V100.md` は V100 の Q4_0 prompt attention について decode kernel を使うと記載しています。これは sm_70 での現行コードの拒否条件と一致します。`docs/DETAILS.md` にはこの変数固有の説明や測定結果は見つかりませんでした。ソースコメントには RTX 2080 Super の parity ケースを挙げていますが、条件や測定値は示されていないため、性能・正確性の一般的な主張には使っていません。

## 根拠

- `src/kernels/cuda/qsa_prompt_attn.cu:2254-2283` — デバイス世代の判定。Turing は compute capability 7.5、Volta は 7.0。
- `src/kernels/cuda/qsa_prompt_attn.cu:2295-2310` — Q4_0 K/V 分岐、`STRATA_PROMPT_ATTN_Q4` との併用、Turing での環境変数判定、kernel launch の可否。
- `src/kernels/cuda/qsa_prompt_attn.cu:83-88` — KV mode 4 が `--kv q4_0` に対応すること。
- `src/prefill/prefill.cpp:3260-3271` — prompt attention kernel が拒否された場合の decode attention fallback。
- `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2027-2029` — SYCL 実装には Q4_0 用の別環境変数 `STRATA_PROMPT_ATTN_Q4` はあるが、本変数の読み取りはない。
- `docs/NVIDIA_V100.md:35` — V100 では Q4_0 prompt attention に decode kernel を使うという既存説明。
