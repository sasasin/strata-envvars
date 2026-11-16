# `STRATA_SYCL_QSA_CHUNK_DOWN`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL 実装の QSA attention で Battlemage 向けの chunk-down 経路を許可する設定です。未設定なら許可し、値が設定されて先頭文字が `1` でない場合は、この対応判定を無効にします。対応判定を通ると、通常の chunk attention ではなく `launch_qsa_chunk_down` の経路を選びます。MTP の two-stage 判定も同じ対応判定を参照します。読み取りと判定は `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp` の `qsa_chunk_down_supported` にあります（同ファイル:961-970, 1001-1016, 1307-1324, 2592-2607）。

この候補名のコード参照は上記の `std::getenv` 1 箇所です。`docs/SETTINGS.md` は Intel Arc 向けの on / off 設定として一覧化していますが、実装上はさらに Battlemage、形状、KV 格納形式などの条件があります（`docs/SETTINGS.md`:372）。

## 値と判定

`qsa_chunk_down_supported` 内の関数ローカル `static const bool` を初回呼び出し時に初期化し、`std::getenv` の戻り値が null（未設定）なら有効、設定済みなら `v[0] == '1'` だけで判定します。文字列全体の parse、空白除去、大文字小文字変換、数値変換はありません（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp`:961-965）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL の `qsa_chunk_down_supported` | 有効 | `1`, `10`, `1anything` | 空文字, `0`, `0anything`, `true`, ` 1` |

したがって `1` は先頭 1 文字だけで有効となり、後続文字は無視されます。明示的な空文字は設定済みで先頭文字が `\0` のため無効です。値の読み取り結果は初回判定後に static cache され、この関数の実行中に環境を変更しても再評価されません。CLI 引数や設定ファイルによる上書きはこの判定箇所にはありません（同ファイル:961-970）。

## 有効になる条件

- SYCL バックエンドのこの実装経路を使うこと。CUDA/HIP の実装参照は候補名の全参照検索では見つかりません。
- デバイスの世代判定が `IntelGpuGen::Battlemage` であること。Intel Arc 全般で有効になるわけではありません（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp`:968-969）。
- `s.n_head == 24`、`s.n_head_kv == 2`、`s.page_size == 4` であること。
- `cap` と query 数が次のいずれかであること: `cap == 2051` かつ `n_q` が 1〜6 または 32、あるいは `cap == 32768` かつ `n_q` が 1〜6（同ファイル:966-969）。
- 通常の `qsa_decode_attn_batch` では、上記に加えて KV mode が 1 で `pools.v_q` が存在すること。step 経路は KV mode 1 が必要です（同ファイル:1009-1015, 1314-1324）。
- `qsa_decode_attn_batch_try_two_stage` も同じ対応判定を使いますが、実際の two-stage 経路にはさらに `cap == 32768`, `n_q == 1`, 対応する QSA 形状と Q8 K/V pool・scale、in-order queue、十分かつ非重複の secondary scratch が必要です。`STRATA_SYCL_QSA_VALUE8_K8_VEC` が無効でも two-stage は使わず通常の batch 関数へ戻ります（同ファイル:2592-2625）。
- prefill の呼び出し元では `STRATA_ATTN_PERCELL` が未設定または先頭文字が `0` 以外だと per-cell prompt kernel を使い、`qsa_decode_attn_batch` を呼びません。明示的に `STRATA_ATTN_PERCELL=0` とした場合に batch 側へ進みます（`sycl/src/prefill/prefill.cpp`:3644-3655）。

条件を満たさないと `qsa_chunk_down_supported` は false となり、batch/step は通常の chunk attention 処理を続けます。two-stage 判定では false を返し、その呼び出し元が通常の batch 関数を呼びます（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp`:1013-1025, 1322-1332, `sycl/src/core/mtp.cpp`:1057-1060）。

## 実行時の詳細

`qsa_decode_attn_batch` は対応判定と KV mode 1・`pools.v_q` の条件を満たすと、`launch_qsa_chunk_down(1, ...)` を呼んで通常の batch kernel 群をスキップします。`qsa_decode_attn_step` も対応判定と KV mode 1 を満たすと同じ launcher に進みます（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp`:1001-1016, 1307-1324）。

launcher 内では K/V Q8 pool が揃わない場合は batch 関数へ戻ります。通常の対応呼び出しでは Q8 pool が必要です。次に `STRATA_SYCL_QSA_VALUE8_K8_VEC` が未設定または先頭文字 `1` なら、`cap` / query 数が `cap == 2051` で query 数 1〜4 または 32、または `cap == 32768` で query 数 1 の場合、`launch_normal_qsa_vector` を使います。それ以外は `chunk_down_kernel<1>` と `attn_merge_kernel` を順に投入します（同ファイル:2560-2590）。

MTP は先に `qsa_decode_attn_batch_try_two_stage` を試し、成功した場合は `launch_normal_qsa_vector` に secondary scratch を渡します。ここで対象変数が未設定または先頭文字 `1` の条件を満たさない場合は two-stage を拒否し、呼び出し元が `qsa_decode_attn_batch` に fallback します。その fallback でも他の形状・pool 条件が成立すれば chunk-down 経路を使えます（`sycl/src/core/mtp.cpp`:1055-1060, `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp`:2592-2625, 1009-1016）。

## ログと測定値

対象変数の読み取り・有効化・無効化に伴うログ出力や警告はありません。無効または条件不一致のときも、この判定自体はエラー終了せず既存の attention 経路へ進みます。対象変数に結び付いた性能測定値は `docs/DETAILS.md` に見つかりませんでした。通常処理の不正な geometry や buffer による終了経路は別途あり、batch は `qsa_decode_attn_batch: unsupported geometry or missing buffers` を stderr に出して `exit(1)`、step は `qsa_decode_attn: unsupported geometry or missing buffers` を出して `exit(1)` します。これらは環境変数の値による警告ではありません（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp`:1003-1008, 1307-1312）。

## 根拠

- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:961-970` — 環境変数の読み取り、値判定、対応形状とデバイス条件。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1001-1017, 1307-1325` — batch / step の分岐と通常経路。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2560-2590` — chunk-down launcher、vector 経路、merge。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2592-2625` — MTP two-stage の条件。
- `sycl/src/core/mtp.cpp:1055-1060` — two-stage 失敗後の batch fallback。
- `sycl/src/prefill/prefill.cpp:3644-3655` — per-cell prompt 経路と batch 呼び出しの切替。
- `docs/SETTINGS.md:372` — 候補一覧の説明。
