# `STRATA_QFUSE_HC`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の verifier で、hyper-connection（HC）read が作る `mixed` の Q8_1 表現を同じ read の GPU 処理内で生成する機能を有効化します。通常は後続の GDN 経路で `native_quantize_q8_1()` が別途行う量子化を省けるよう、その場で `xq_` に画像を書きます。GDN recurrence 自身が出す量子化を制御する `STRATA_QFUSE` とは別の設定です（`src/core/verify.cpp:136-156,1065-1074,1174-1180`）。

## 値と判定

HIP ビルドでは `g_qfuse_hc()` が初回評価時の結果を `static const bool` に保存します。文字列全体の検証はせず、設定値は `std::atoi()` で整数に変換し、0 以外なら有効です。

| 値 | HIP での判定 |
|---|---|
| 未設定 | 現在の GPU の `gcnArchName` が `gfx_arch_is_gfx12()` に該当すれば有効。それ以外、または device/property 取得失敗時は無効 |
| `0`、空文字、数値変換結果が 0 の文字列（例: `false`） | 無効。明示値があるため gfx12 の既定判定も使わない |
| 数値変換結果が 0 以外（例: `1`, `-1`, `2`, `1junk`） | 有効。末尾文字列は検査されない |

`atoi` のため、先頭空白や符号を含む文字列も数値変換の結果で判定されます。値の大小による段階設定や clamp はありません。CUDA ビルドでは関数が常に `false` を返し、環境変数を読みません。SYCL 側の verifier にもこの名前の読み取りはありません（`sycl/src/core/verify.cpp`）。根拠: `src/core/verify.cpp:140-155`。

## 有効になる条件

- HIP でビルドされた verifier 経路であること。CUDA では有効化されません。
- verifier window の初期化で `g_qfuse_hc()` が有効と判定され、Q8 counter buffer の確保とゼロ初期化に成功すること。確保または初期化に失敗すると `qcnt_` は null に戻り、Q8 画像の出力経路は使われません（`src/core/verify.cpp:789-795`）。
- HC read に必要な出力先が全 token 分そろうこと。`fused_gr_read_multi()` は token 0 の counter と各 token の `q8_mixed` がある場合に限って Q8 出力を有効にし、不足時は全 token の `q8_mixed` を null にします（`src/kernels/cuda/fused_gr.cu:1848-1853`）。
- `STRATA_QFUSE_HC_LOCAL` は別の設定です。未設定または `atoi` が 0 以外なら `qfuse_hc_local()` が true となり、ビルド条件 `!STRATA_GR_FAST_BUILD` のもとで Q8 出力先がある場合に 32-column の `gr_up_q32_kernel` を選びます。明示的な `STRATA_QFUSE_HC_LOCAL=0` ではこの分岐を通らず、通常の `gr_up_multi_kernel` 経路になります（`src/kernels/cuda/fused_gr.cu:1025-1028,1092-1118`）。

## 実行時の詳細

`g_qfuse_hc()` の判定は verifier window の初期化時に `qcnt_` の確保条件として使われます。環境をプロセス起動後に変更しても、判定済みの static 値は再評価されません。GPU 判定もデバイスごとではなく、最初に呼び出されたときの現在デバイスについて一度だけ行われます（`src/core/verify.cpp:141-155,789-795`）。

`qcnt_` があると HC read の引数に counter と `q8_mixed` 出力先を渡します。first half（`half == 0`）は `xq_` を出力先にします。HC read が正常に Q8 画像を書いた場合、`fused_gr_read_multi()` は true を返し、その verifier window では GDN 入力の直前にある通常の `native_quantize_q8_1(xm, xq_, ...)` をスキップします（`src/core/verify.cpp:1053-1074,1116`; `src/kernels/cuda/fused_gr.cu:1848-1863`）。

デバイス確保の失敗時にこの機能専用の警告ログはなく、実装は通常の後続量子化に戻ります。Q8 kernel の起動エラーは `fused_gr_read_multi q8: <CUDA error text>` を stderr に出してプロセスを終了します（`src/core/verify.cpp:789-795`; `src/kernels/cuda/fused_gr.cu:1855-1863`）。

## 文書・測定値

`docs/DETAILS.md` に `STRATA_QFUSE_HC` の既定値や測定結果の説明は見つかりませんでした。gfx12 既定という条件、および 32-column kernel の実装説明はソースコメントにありますが、ここでは独立に性能や出力同一性を確認していません。

## 根拠

- `src/core/verify.cpp:140-155` — HIP/CUDA の判定、既定値、数値変換、static cache。
- `src/core/verify.cpp:789-795` — window 初期化時の counter 確保と失敗時 fallback。
- `src/core/verify.cpp:1053-1074,1116` — HC read への Q8 出力先の設定と別量子化の省略。
- `src/kernels/cuda/fused_gr.cu:378-381,1025-1028,1092-1118,1848-1863` — Q8 出力付き kernel の選択、補助設定、出力条件とエラー処理。
- `sycl/src/core/verify.cpp` — `STRATA_QFUSE_HC` の読み取りなし。
