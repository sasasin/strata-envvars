# `STRATA_QFUSE_HC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Hyper-connection (HC) の read が、直後の利用側が使う Q8_1 (`q8_mixed`) 画像も同じ read で書く経路を選びます。通常は `mixed_` を HC read が作り、その後の `native_quantize_q8_1` が Q8_1 画像を作ります。MTP ではこの後段量子化を省ける場合に、attention の K/V 射影や MLP shared expert が read の出力した画像を使います（`engine/src/core/mtp.cpp:1228-1249,1356-1382,2387-2404,2506-2522`）。Verifier の通常 window では HC read に Q8_1 出力先と group counter を渡し、consumer が使えるようにします（`engine/src/core/verify.cpp:1796-1820`）。

この変数は GDN recurrence の量子化を切り替えるものではありません。MTP 側の明示設定は `STRATA_QFUSE` と別に判定されます（`engine/src/core/mtp.cpp:1137-1145`）。ただし verifier では `STRATA_QFUSE` も同じ `qcnt_` 確保を有効にし、確保後は HC read に Q8_1 出力先を渡します。そのため verifier に限り、`STRATA_QFUSE=1` でも HC read 側の画像書き込みが起き得ます（`engine/src/core/verify.cpp:320,1431-1437,1810-1814`）。

## 値と判定

両読み取り箇所とも `std::getenv` の後に `std::atoi(v) != 0` で整数変換します。文字列全体の妥当性検査はなく、先頭の数値部分が 0 以外なら有効です。したがって `1`, `-1`, `1tail`, ` 1` は有効、`0`, `0tail`, `true`, `false`, 空文字、数値で始まらない文字列は無効です。未設定だけは `atoi` せず、build/backend ごとの既定判定に進みます（`engine/src/core/verify.cpp:222-238`; `engine/src/core/mtp.cpp:1137-1157`）。

| 呼び出し経路 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| verifier (`STRATA_USE_HIP` build) | 現在の GPU が gfx12 なら ON、それ以外は OFF | `atoi` が 0 以外（例 `1`, `-1`, `1tail`） | `atoi` が 0（例 `0`, `true`, 空文字） |
| verifier (非 HIP build) | OFF | なし。この関数は常に OFF | すべて。環境値を読み取らない |
| MTP (`STRATA_USE_HIP` build) | 現在の GPU が gfx12 なら ON、それ以外は OFF | `atoi` が 0 以外 | `atoi` が 0 |
| MTP (非 HIP build) | OFF | なし。この関数は常に OFF | すべて。値が設定されていても関数は OFF |

Gfx 判定は `cudaGetDeviceProperties` の `gcnArchName` を `gfx12` 判定関数へ渡します。整数の範囲検査や clamp はありません。`atoi` の変換で整数として読めない接頭部は 0 になり、空文字も 0 です（`engine/src/core/verify.cpp:224-235`; `engine/src/core/mtp.cpp:1141-1154`）。

## 有効になる条件

- verifier 側の `g_qfuse_hc()` は HIP build でのみ環境値を読みます。非 HIP build は常に false です（`engine/src/core/verify.cpp:222-238`）。
- MTP 側は MTP 内の HC read 箇所で `mtp_qfuse_hc_on()` が評価される場合に使います。HIP build では値を強制でき、未設定時の既定は gfx12 です。非 HIP build は環境値によらず false です（`engine/src/core/mtp.cpp:1137-1157,1228-1243,1356-1372,2387-2401,2506-2522`）。
- MTP では `STRATA_QFUSE` の値はこの判定に影響しません。Verifier では `STRATA_QFUSE=1` が `qcnt_` の確保を独立に有効にするため、HC 出力画像を使えることがあります（`engine/src/core/mtp.cpp:1137-1145`; `engine/src/core/verify.cpp:320,1431-1437,1810-1814`）。
- Verifier は `STRATA_HC_PERSIST=1` の永続 HC read 経路では fused read の前に戻るため、その経路では `q8_mixed` は設定されません（`engine/src/core/verify.cpp:1810-1818`）。
- fused read が全 token に Q8_1 出力先を持たない場合、または必要な counter / 条件が揃わない場合は `q8_mixed` を null に戻し、後続の通常量子化へ進みます。fast build では counter 不要経路の条件も変わります（`engine/src/kernels/cuda/fused_gr.cu:4272-4283`）。
- HIP の MTP counter-free 経路は `STRATA_QFUSE_HC_LOCAL` の値も参照します。これはこの文書の対象変数とは別設定で、`STRATA_QFUSE_HC_LOCAL=0` などのときは counter がない `q8_mixed` 経路が Q8_1 を書かず false を返す実装があります（`engine/src/kernels/gr_parity.cpp:527-529`; `engine/src/kernels/cuda/fused_gr.cu:4272-4283`）。

## 実行時の詳細

設定値は verifier の `g_qfuse_hc()` と MTP の `mtp_qfuse_hc_on()` それぞれで static に一度だけ保存されます。値が設定されていれば、その真偽値をプロセス中固定します。未設定の場合も GPU architecture 判定を device ごとに cache します。したがって実行中に環境変数を変更しても再評価されません（`engine/src/core/verify.cpp:222-235`; `engine/src/core/mtp.cpp:1137-1157`）。MTP の gfx12 cache は最大 64 device の配列です。

Verifier は `g_qfuse()` または `g_qfuse_hc()` が true のとき `g.n_embd / 32` 個の unsigned counter buffer を確保してゼロ初期化します。確保または初期化に失敗するとエラーを消去して buffer を解放し `qcnt_ = nullptr` とするため、以降の HC fused read は Q8_1 出力を指定せず通常経路になります（`engine/src/core/verify.cpp:1431-1437,1810-1818`）。

MTP の attention HC read は成功時に `q8_attn` を返し、true なら K/V 射影前の別 `native_quantize_q8_1` を省略します。MLP HC read は成功時の `q8_mlp` を単 token の shared expert へ渡します。batch MTP でも同様に attention の別量子化を省略し、MLP の画像を fused shared expert に渡します（`engine/src/core/mtp.cpp:1228-1249,1356-1382,2387-2404,2506-2559`）。この環境変数が router の選択、モデル設定、CLI 引数の優先順位を変える処理は確認できません。

## ログと測定値

対象変数の値を直接表示する専用ログや無効値警告は見つかりません。Verifier の HC read は dispatch note が有効なとき `hc read: weights Q8_0 copies=%ld (0 = bf16 rows), half=%ld, qfuse=%ld` を出しますが、`qfuse` は環境変数の値ではなく `qcnt_ != nullptr` を示します。これは `STRATA_QFUSE` で確保された場合も 1 になります（`engine/src/core/verify.cpp:1796-1814`）。

Verifier で counter buffer の確保に失敗した場合は上記の通り通常経路へ戻り、対象変数に対する専用の失敗ログはありません。fused read の引数不正や kernel launch error は stderr に `fused_gr_read_multi: invalid arguments for token %d`、`fused_gr_read_multi q8: %s` などを出して終了コード 1 で終了する経路がありますが、これらは値の parse 警告ではありません（`engine/src/kernels/cuda/fused_gr.cu:4264-4269,4286-4293`）。

`docs/DETAILS.md` に本変数や本変数固有の測定結果は見つかりませんでした。性能・正確性の数値は記載しません。

## 根拠

- `engine/src/core/verify.cpp:221-238` — verifier の読み取り、HIP 限定、gfx12 既定。
- `engine/src/core/verify.cpp:320,1431-1437,1796-1820` — `STRATA_QFUSE` との counter 共有、HC read の出力画像と note。
- `engine/src/core/mtp.cpp:1137-1157` — MTP の読み取り、gfx12 default、device cache。
- `engine/src/core/mtp.cpp:1228-1249,1356-1382,2387-2404,2506-2559` — MTP の attention / MLP HC read と後続処理。
- `engine/src/kernels/cuda/fused_gr.cu:4272-4293` — fused read の Q8_1 条件、fallback 判定およびエラー経路。
- `engine/src/kernels/gr_parity.cpp:527-529` — counter-free MTP 経路に関する実装コメント。
