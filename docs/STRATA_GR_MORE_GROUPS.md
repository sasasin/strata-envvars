# `STRATA_GR_MORE_GROUPS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Intel GPU 向け SYCL 実装の fused GR（hyper-connection read）の複数 token カーネルで、work-group 数を増やした分解を選びます。既定では Alchemist（Arc A-series）で有効、それ以外のデバイスでは無効です。CUDA/HIP 側でこの名前を読む実装は確認できません。

この実装は SYCL ビルドの `sycl/src/kernels/cuda/fused_gr.dp.cpp` にあります。SYCL の CMake は `src/kernels/cuda/fused_gr.cu` を解決する際、移植済みの `.dp.cpp` が存在すればそれをビルド対象にします（`sycl/CMakeLists.txt:88-104,213-224`）。fused GR 自体も、モデル形状が対応し `g_fused_gr` が有効な場合に engine の layer 処理から呼ばれます（`sycl/src/core/layer.cpp:1558-1559,1622-1628`）。

## 値と判定

値は文字列全体ではなく `std::atoi(e) != 0` で判定します。未設定時だけデバイス世代に応じた既定値を使います。

| 設定 | 判定 |
|---|---|
| unset | `strata::intel_gpu_gen(q->get_device())` が `Alchemist` なら有効。それ以外は無効 |
| 空文字、数値に変換できない文字列（例: `true`） | `atoi` が 0 を返すため無効 |
| 先頭の空白や符号の後に非ゼロ整数がある値（例: ` 1`, `+1`, `-1`, `1abc`） | `atoi` の結果が非ゼロなので有効 |
| `0`、`0abc`、数値として先頭が 0 の値 | `atoi` の結果が 0 なので無効 |

判定は `gr_more_groups()` 内の `static const bool` に保存されます。環境変数の変更は、この関数が初回評価された後には反映されません。既定値に使う `q` も初回呼び出しの queue です。そのため、複数デバイスを同一プロセスで使う場合も判定はデバイスごとではなく、初回に渡されたデバイスに基づく一つの値が共有されます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:643-649`）。

## 有効になる条件

- Strata の SYCL ビルドで、この移植版 fused GR カーネルが実行されること。CUDA/HIP ビルドの挙動をこの設定で制御する根拠はありません。
- fused GR がモデル形状に対応し、layer 実行で選択されること（`sycl/src/core/layer.cpp:1558-1559,1622-1628`）。
- 下流カーネルの分解変更は `STRATA_GR_DOWN_SLICED` が有効なときだけです。同変数は未設定なら有効、設定時は `atoi(...) != 0` です。これが無効なら down 側は別経路になりますが、up 側では `STRATA_GR_MORE_GROUPS` の分岐が引き続き使われます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:651-653,1956-1989,2039-2043`）。

## 実行時の詳細

有効時、sliced down は通常の 80-group 相当の分解に代わり、slice と row block に分けたより多い work-group で計算し、その後 reduce kernel を起動します。up は 16 列単位の通常カーネルから 8 列単位のカーネルへ切り替わり、ソースコメントでは 320 groups とされています。無効時は down に通常の sliced 経路、up に既定の multi-token 経路を使います（`sycl/src/kernels/cuda/fused_gr.dp.cpp:637-642,803-834,1956-1983,2039-2043`）。

ソースコメントは、この変更で float sum の順序と出力を維持すると述べ、`gr_bench` の checksum に変化がなかったとしています。また A770 の 1〜6 token の測定として、down が 117–180 µs から 87–149 µs、decode が 28.04–28.54 tok/s から 29.99–30.00 tok/s になったと記載しています（同ファイル:637-642）。これは実装コメントに記録された測定値であり、ここで再測定した結果ではありません。`docs/A770_SPEED_SPEC.md:662-665` の standalone GR 測定値は別の測定で、この切り替え前後の比較条件を示すものではありません。

## 根拠

- `sycl/src/kernels/cuda/fused_gr.dp.cpp:643-649` — 環境変数の parse、Alchemist の既定値、static cache。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:637-642,803-834` — work-group 分解の説明と、追加分解用の down/up launch。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1956-1989,2039-2043` — down sliced 条件と down/up の分岐。
- `sycl/include/strata/sycl_queue.hpp:119-150` — `intel_gpu_gen` の判定対象とデバイス識別方法。
- `sycl/src/core/layer.cpp:1558-1559,1622-1628`; `sycl/CMakeLists.txt:88-104,213-224` — runtime 経路と SYCL 移植ソースのビルド解決。
