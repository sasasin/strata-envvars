# `STRATA_ATTN_LANECELL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

QSA attention の chunk kernel で、attention score を作るスレッド配置を切り替える。CUDA/HIP では `attn_chunk_kernel<..., true>`、SYCL では `attn_chunk_kernel<..., true>` を選び、各 thread が cell と複数 query head の score を計算し、従来の warp shuffle reduction を使わず butterfly 加算する。値の積和と後続の softmax / value 集約を含む attention 経路の選択であり、QSA の候補 cell 選択自体を変える設定ではない（`engine/src/kernels/cuda/qsa_decode_attn.cu:214-247, 1057-1063`、`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:194-239, 1121-1125`）。

主な対象は batch attention と slot attention。CUDA/HIP の `qsa_decode_attn_step` はこの変数を読まず通常 kernel を launch するため、そこを通る単独 step の attention は切り替わらない（`engine/src/kernels/cuda/qsa_decode_attn.cu:1309-1349`）。SYCL には対応する `qsa_decode_attn_step` があり、同じく環境変数を参照しない（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1307-1355`）。

## 値と判定

| 実装・経路 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP batch・slots・batch-rows からの per-row 呼び出し | unset は無効。空文字も無効 | 先頭 byte が文字 `1` の文字列（`1`, `10`, `1anything`） | `0`, `true`, ` 1`, 空文字。先頭 byte だけを比較するため `01` は無効 |
| SYCL `qsa_decode_attn_batch` | unset・空文字は自動判定へ | 非空文字列を `atoi` した値が 1 以上（`1`, `2`, `01`, `1tail`, ` 1`） | `0`, `true` は `atoi` 結果 0 で無効。負の数は自動判定へ戻る |
| SYCL `qsa_decode_attn_batch_rows` | unset・空文字は parse 結果 `-1`。それ自体では per-row にならない | `atoi` の結果がちょうど `1` なら per-row に迂回し、各行で batch kernel の判定を使う | 他の値は下記 rows 経路条件による。`2` はこの関数単独では lane-cell rows kernel を有効にしない |

CUDA/HIP の判定は `v && v[0] == '1'` で、数値変換・文字列全体の検証・大文字小文字変換はない（`engine/src/kernels/cuda/qsa_decode_attn.cu:992-996, 1245-1248`）。SYCL は `v != nullptr && v[0] != '\0' ? std::atoi(v) : -1` とし、batch は `lane_cell_env >= 0 ? lane_cell_env != 0 : auto` で分岐する。したがって `-1` や `-2` も auto になる一方、`-0` は `atoi` が 0 を返して明示 OFF になる（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1034-1041`）。rows 経路では `lane_cell_env == 1` のみを per-row 条件に使う（同 `:1265-1276`）。

## 有効になる条件

- CUDA/HIP の `qsa_decode_attn_batch` は、geometry / buffer の検査を通過し、`n_q > 0` のとき chunk launch 前に判定する。lane-cell が選ばれると KV pool mode 0/1/2/3 に応じた `LANE_CELL=true` kernel を launch する（`engine/src/kernels/cuda/qsa_decode_attn.cu:1132-1146, 1026-1063`）。
- CUDA/HIP の `qsa_decode_attn_slots` も同じ判定を使う。pre75 kernel が有効でも lane-cell が on なら pre75 経路に入らない（同 `:1150-1178, 1188-1218`）。
- CUDA/HIP の `qsa_decode_attn_batch_rows` は lane-cell が on なら row ごとに `qsa_decode_attn_batch` を呼び、rows 専用の通常 kernel を避ける。HIP gfx906 では設定値にかかわらず常に per-row にするが、各行の batch 呼び出しでは lane-cell 判定が別途適用される（同 `:1245-1270`）。
- SYCL の `qsa_decode_attn_batch` は unset / 空文字 / 負値の auto 判定で、`n_q >= 16` かつ `strata::intel_gpu_gen(device) == Battlemage` の場合に有効。それ以外の世代または小さい batch では auto は OFF。非負の明示値はこの auto 条件を上書きする（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1027-1041`）。
- SYCL `qsa_decode_attn_batch_rows` は `STRATA_ATTN_RS` の値が 2 以外、または lane-cell の parse 結果がちょうど 1 のとき、row ごとに `qsa_decode_attn_batch` へ迂回する。迂回しない場合に呼ばれる `attn_rows_chunks` は通常の `LANE_CELL=false` kernel であり、`atoi` 結果が 2 などの値だけでは lane-cell rows kernel にならない（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1265-1290`）。
- AMD gfx1151 discrete および gfx12 の起動時アーキテクチャ既定値は、ユーザーがこの変数を設定していない場合に `1` を設定する。gfx1151 は `STRATA_GFX11_DEFAULTS` が先頭 `0`、gfx12 は `STRATA_GFX12_DEFAULTS` が先頭 `0` の場合に既定表を止める。両方とも `STRATA_DEFAULTS=026` でもこの既定値を使わない。空文字を含め、対象変数が存在すれば既定値は上書きしない（`engine/src/core/arch_defaults.cpp:28-55, 64-66, 302-323`、`engine/include/strata/core/gfx11_extra.hpp:8-12, 27-30, 39-60`、`engine/include/strata/core/defaults_026.hpp:26-29`）。
- CUDA/HIP の環境判定は `static` local に初回評価結果を保持する。SYCL の batch と batch-rows もそれぞれ `static` local に parse 結果を保持し、batch は device と `n_q` を呼び出しごとに auto 判定する。プロセス実行中に環境を書き換えても、既に初期化済みの判定値は再読込されない（CUDA/HIP 同 `:993-995, 1247-1248`、SYCL 同 `:1035-1041, 1266-1269`）。

## 実行時の詳細

CUDA/HIP batch launch では `lane_cell_attn()` の結果を `kernel < 0`（通常の環境選択 launch）の場合にだけ使う。parity 用に kernel を明示した呼び出しはこの環境選択を使わない。ON なら KV の形式別 kernel の `LANE_CELL=true` specialization を dispatch し、OFF なら gfx906 swizzle、pre75、または標準 kernel の分岐へ進む（`engine/src/kernels/cuda/qsa_decode_attn.cu:1023-1042, 1057-1116`）。

QSA layer の通常 step は `qsa_decode_attn_step` を呼び、batch / verify 経路は `qsa_decode_attn_batch` または `qsa_decode_attn_batch_rows` を呼ぶ。したがって、CLI / server という入口だけでは有効性は決まらず、実際に呼ばれる attention API、backend、query 数、GPU 世代、KV pool mode が適用範囲を決める（`engine/src/core/layer.cpp:1284-1290`、`engine/src/core/verify.cpp:2466-2468, 2580-2589`）。SYCL batch は `qsa_chunk_down_supported(...) && kv_mode == 1 && pools.v_q` の場合、環境変数を判定する前に chunk-down 経路へ return する（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1001-1016`）。

アーキテクチャ既定値は `generate.cpp` の GPU 初期化時に `apply_arch_defaults` から設定される。未設定時だけ `setenv(..., 0)` / `_putenv_s` で設定するため、明示 `0` や空文字もユーザー設定として残る。対応既定値が投入されたときは stderr に `strata: gfx11 (RDNA3): ... exact speed switches on by default ...`、または gfx1151 / gfx12 向けの一覧行が出て、設定名一覧に `ATTN_LANECELL` が現れる。変数の読み取り自体が出す lane-cell 専用の有効 / 無効ログはない（`engine/src/program/generate.cpp:4285-4315`、`engine/src/core/arch_defaults.cpp:218-224, 318-332, 397-404`）。

## ログと測定値

この変数の不正値に対する警告やエラーはない。CUDA/HIP batch の geometry / buffer 不備は stderr の `qsa_decode_attn_batch: unsupported geometry or missing buffers`、kernel launch error は `qsa_decode_attn_batch: %s` を出して `exit(1)` する。SYCL batch の geometry / buffer 不備も同じ文言で終了する（`engine/src/kernels/cuda/qsa_decode_attn.cu:1135-1146`、`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1003-1008`）。

Strata のソースコメントには個別環境・GPU・モデル・query 数を伴う性能比較がありますが、本書では一般的な速度差として扱わない。コメント上の bit-identical という説明も実測の一般保証としては記述しない。

## 根拠

- 値の読み取りと dispatch: `engine/src/kernels/cuda/qsa_decode_attn.cu:992-996, 1023-1063, 1132-1146, 1150-1218, 1227-1270`
- CUDA/HIP step が変数を参照しない箇所: `engine/src/kernels/cuda/qsa_decode_attn.cu:1309-1349`
- SYCL の値判定、auto 条件、rows 分岐: `engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1001-1041, 1121-1135, 1265-1290, 1307-1355`
- architecture default: `engine/src/core/arch_defaults.cpp:28-55, 64-66, 218-224, 302-332, 397-404`、`engine/include/strata/core/gfx11_extra.hpp:8-12, 27-30, 39-60`、`engine/include/strata/core/defaults_026.hpp:26-29`
- 起動時設定と呼び出し元: `engine/src/program/generate.cpp:4285-4315`、`engine/src/core/layer.cpp:1284-1290`、`engine/src/core/verify.cpp:2466-2468, 2580-2589`
