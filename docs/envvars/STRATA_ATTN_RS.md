# `STRATA_ATTN_RS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Intel Arc 向け SYCL エンジンの QSA attention batch kernel で、attention score/probability の scratch 内レイアウトと score の reduce 方法を選ぶ。未設定時の `2` は probability を `[cell][head]` の順に置き、value phase が 1 cell 分の head probability を vector load できる経路を使う。`1` は同じ layout に加え score の 12 head reduction を reduce-scatter にする。`0` とその他の数値は以前の `[head][cell]` layout と通常の warp reduction に戻る。コードコメントと `docs/INTEL.md` はいずれも bit-exact variant と説明しているが、この環境変数が変えるのは該当 kernel の計算配置・reduction 経路であり、attention の選択セルや出力後段を変える分岐ではない（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:121-163,242-305,368-381,1117-1136`）。

この読み取りは SYCL エンジンの `qsa_decode_attn_batch` と `qsa_decode_attn_batch_rows` に限られる。エンジンの通常の単一 query decode 関数 `qsa_decode_attn_step` にはこの環境変数の読み取りがない（同 `:1001-1003,1120,1256-1268,1307-1335`）。

## 値と判定

両箇所とも `std::getenv` の結果を `std::atoi` に渡し、未設定だけを `2` にする。空文字も設定済みとして `atoi("") == 0` となる。`atoi` は文字列全体の妥当性を検証しないため、先頭の空白と符号の後にある数値接頭辞を変換し、数値の後ろの文字は無視する。数値接頭辞がない文字列は `0` になる。parse 後に `== 1` / `== 2` で選択し、範囲 clamp や警告はない（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1120,1265-1268`）。

| `atoi` の結果 | 選択される経路 |
|---|---|
| unset → `2` | RS=2: cell-major layout、通常の score reduction |
| `1`（例: `1`, `1tail`, `+1`） | RS=1: cell-major layout、score reduce-scatter |
| `0`（例: `0`, 空文字, `true`, `false`, `0tail`, 数字で始まらない文字列） | 旧 layout・通常 reduction |
| その他（例: `-1`, `3`, `2tail`） | RS=1/2 のどちらにも一致せず、旧 layout・通常 reduction |

`atoi` の整数範囲外入力の結果はこのコードで検査・規定していない。設定値 `2` は `qsa_decode_attn_batch_rows` の複数行 kernel を選ぶ条件にも使われるため、`1`、`0`、その他の値では行ごとの `qsa_decode_attn_batch` 呼び出しに分解する（同 `:1265-1276`）。

## 有効になる条件

- `engine/CMakeLists.txt` では SYCL が独立 backend として定義され、既定は `STRATA_ENABLE_SYCL=OFF`。SYCL は CUDA/HIP と同時に有効にできない構成で、説明上 Intel Arc 向けの実験的エンジンである。したがって通常の CUDA/HIP/Metal エンジンではこの読み取り箇所を通らない（`engine/CMakeLists.txt:23-30`; `engine/sycl/CMakeLists.txt:1-3,255`）。
- prompt は `STRATA_PROMPT_ATTN_OLD` が設定されるか `qsa_prompt_attn_batch` が利用不可を返し、さらに `STRATA_ATTN_PERCELL=0` のとき `qsa_decode_attn_batch` に到達する。`STRATA_ATTN_PERCELL` が未設定または先頭文字が `0` 以外なら per-cell kernel が選ばれ、この変数は読まれない（`engine/sycl/src/prefill/prefill.cpp:3849-3853,3873-3895`）。
- verify の batch attention は `STRATA_BATCH_ATTN_ROWS` が設定され `atoi != 0`、batch recording が有効、行数が上限以下、対象 slot の KV mode が `1` 以外の場合に `qsa_decode_attn_batch_rows` を使う。それ以外の verify batch でも `qsa_decode_attn_batch` を呼ぶ経路がある（`engine/sycl/src/core/verify.cpp:1485-1494,1505-1537`）。
- MTP drafter は `qsa_decode_attn_batch_try_two_stage` が false を返すと `qsa_decode_attn_batch` に fallback する（`engine/sycl/src/core/mtp.cpp:1053-1061`）。
- `qsa_decode_attn_batch` は Q8 KV (`kv_mode == 1`)、`pools.v_q` が存在し、`qsa_chunk_down_supported` の形状・デバイス条件を満たすと、対象変数の読み取りより先に chunk-down kernel を起動して戻る。この条件には Battlemage、`n_head=24`、`n_head_kv=2`、page size 4、`cap=2051`（query 数 1〜6 または 32）または `cap=32768`（query 数 1）、および `STRATA_SYCL_QSA_CHUNK_DOWN` が未設定または先頭文字 `'1'` の条件が含まれる（同 `:1009-1016,1120`; `:961-969`）。
- `STRATA_ATTN_LANECELL` は空でない値を `atoi` し、結果が 0 以上なら lane-cell の on/off を明示する（0 は off、正数は on）。未設定・空文字・負数なら自動判定に進み、`n_q >= 16` かつ Battlemage のとき lane-cell が on になる。lane-cell が on の `qsa_decode_attn_batch` では `STRATA_ATTN_RS` の RS=1/2 分岐を使わない（同 `:1035-1041,1120-1136`）。`qsa_decode_attn_batch_rows` では `STRATA_ATTN_LANECELL` の parse 結果が正確に `1` のとき per-row 呼び出しへ分解し、その先の `qsa_decode_attn_batch` が lane-cell を選ぶ（同 `:1265-1275`）。

## 実行時の詳細

読み取り値は各関数内の `static const int` に保存される。プロセス起動時ではなく、その関数で初めて読み取り行まで実行した時に一度だけ初期化される。したがって初期化後に環境を変更しても同じ関数の値は更新されない。2 関数は別々の static cache を持つ。なお `qsa_decode_attn_batch` は `n_q <= 0` の早期 return、および前述の chunk-down shortcut では読み取り行に到達しない（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1001-1016,1120,1256-1276`）。

`qsa_decode_attn_batch` では `1` と `2` が KV mode 0〜3 ごとの `attn_chunk_kernel<M, false, V>` を起動し、`V` が選択 layout/reduction variant を表す。その他の値は `attn_chunk_kernel<M>`（既定 RS=0）へ進む。後続の chunk merge は共通である（同 `:1009-1010,1079-1136,1139-1227`）。

`qsa_decode_attn_batch_rows` は、RS 値が `2` 以外、または `STRATA_ATTN_LANECELL` の parse 結果が `1` の場合、各 query を `qsa_decode_attn_batch` に分解する。RS=2 で lane-cell 強制がない場合のみ、rows kernel をまとめて起動する（同 `:1265-1299`）。

この変数専用のログ、警告、終了処理はない。未設定・空文字・不正な文字列も、上記変換後の分岐として黙って処理される。batch 関数の不正 geometry / buffer は stderr に `qsa_decode_attn_batch: unsupported geometry or missing buffers` または `qsa_decode_attn_batch_rows: unsupported geometry or missing buffers` を出して `exit(1)` するが、これはこの環境変数の値判定によるものではない（同 `:1004-1008,1260-1264`）。

## ログと測定値

環境変数を読んだことや選択 variant を示す実行時ログはない。`docs/INTEL.md` は Arc Pro B70 の 4,095-token IQ3_S prompt について、`STRATA_ATTN_RS=2` で 1,254→1,265 tok/s（+0.9%）、`=1` で 1,254→1,236 tok/s（-1.5%）と記録する。同資料の測定条件の注記は Arc Pro B70 32 GB、PCIe 3.0 x8、Ubuntu 24.04、SYCL port などを挙げるが、表の該当行は別途「4,095-token IQ3_S prompt」の条件である。これは資料中の測定記録であり、現行 checkout 上での再測定ではない（`docs/INTEL.md:475-476,556-563`）。

## 根拠

- 全直接参照と kernel variant: `engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:121-163,242-305,368-381,1001-1016,1035-1041,1079-1136,1139-1227,1256-1299,1307-1335`
- 呼び出し元と適用条件: `engine/sycl/src/prefill/prefill.cpp:3849-3895`; `engine/sycl/src/core/verify.cpp:1485-1537`; `engine/sycl/src/core/mtp.cpp:1053-1061`
- backend/build 条件と chunk-down shortcut: `engine/CMakeLists.txt:23-30`; `engine/sycl/CMakeLists.txt:1-3,255`; `engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:961-969`
- 文書の用途・測定記録: `docs/SETTINGS.md:30`; `docs/INTEL.md:462,556-563`
