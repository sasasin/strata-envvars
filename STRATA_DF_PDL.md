# `STRATA_DF_PDL`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の意味は対象外。

## 役割

CUDA の verify window で、一部の連続する GPU kernel launch を programmatic dependent launch (PDL) に切り替える opt-in です。先行 kernel の完了前に後続 kernel が開始し、後続 kernel は必要な出力を読む直前の `pdl_wait()` で依存完了を待ちます。その待ちより前に重ねる処理は重みの読み込みなどで、Strata のコメントは通常 launch と計算結果が同じになる設計と説明しています。

設定しただけで全 kernel が PDL になるわけではありません。verify-window の CUDA 経路で、対応する stream capture の依存先が kernel node のみであり、後続 kernel 自身も PDL 用コードを含む場合に限って launch 属性を付けます。HIP では常に無効です。

## 値と判定

値は `std::atoi` で整数に変換されます。文字列全体の妥当性確認や範囲 clamp はありません。先頭空白と符号の後の数字列を読み、数字列の後ろは無視します。数字に変換できない文字列や空文字は 0 になります。

| 設定値 | `pdl_supported()` の opt-in 判定 | 追加の predecessor 制限 |
|---|---|---|
| 未設定 | 無効 | なし（本番の verify-window scope が設定されない） |
| `0`、`false`、空文字、数字で始まらない値 | 無効（`atoi` が 0） | なし |
| 数値変換結果が 0 以外（例: `1`, `1abc`, `-1`, `3`) | 有効候補 | 変換結果がちょうど `2` のときだけ、依存先が1 nodeの場合に限定 |
| `2` または `2abc` | 有効候補 | 依存先が1 nodeの場合に限定 |

`mode` の読み取りは `pdl_launch_ok()` 内で別の static 値として行われます。ここでは未設定時を `1` としますが、未設定時は先行する opt-in 判定が false なので通常の verify-window scope から PDL launch には進みません。明示値 `2` は join などで依存先が複数ある edge を通常 launch に戻します。明示された他の非ゼロ値は複数依存先を許す `1` 相当です。

根拠: `src/kernels/cuda/verify_kernels.cu:1391-1399,1433-1445`。

## 有効になる条件

- CUDA のビルドで CUDA Runtime が 12.3 (`CUDART_VERSION >= 12030`) 以上であること。未満では `pdl_supported()` が常に false を返し、launch 判定も false です。
- `STRATA_DF_PDL` の整数変換結果が非ゼロであること。
- 実行デバイスの compute capability major が 9 以上であること（`STRATA_EMULATE_CC` が設定されていれば `cc_major_of()` の判定にその値も使われます）。
- `gpu_stamp_kernel<true>` と個々の PDL 対象 kernel について、CUDA が返す `ptxVersion` および `binaryVersion` がともに 90 以上であること。古い PTX を実行時 JIT しているだけの kernel はこの条件を満たさず、通常 launch に戻ります。CUDA アーキテクチャのビルド指定は `CMAKE_CUDA_ARCHITECTURES` で行われますが、どの kernel が条件を満たすかは実行時の属性確認で決まります。
- verify window が単一 group であること。`src/core/verify.cpp` は `G == 1 && pdl_supported()` のときに限り thread-local の PDL scope を有効にします。
- capture 中で、次の node のすべての依存先が kernel node であること。capture 外、依存先なし、memcpy/memset/host/event node を含む場合は通常 launch になります。明示値 `2` では依存先が1つであることも必要です。

条件不足による専用の警告や状態ログは、確認した実装箇所にはありません。条件が合わない launch は `launch_pdl()` が通常の kernel launch にフォールバックします。

## 実行時の詳細

`pdl_supported()` は `STRATA_DF_PDL` の opt-in 判定を関数内の `static const bool` に一度だけ保存します。対応状況は device ごとの配列に保存され、各 device では初回判定結果を再利用します。`pdl_launch_ok()` も環境値の `mode` を static に保存し、kernel と device ごとの属性確認結果をキャッシュします。そのため、これらの判定後に同一プロセス内で環境を書き換えても再評価されません。

scope が有効な間、`launch_pdl()` は対象 kernel の属性と stream capture の依存 node を確認し、条件を満たせば `cudaLaunchAttributeProgrammaticStreamSerialization` 属性付きで `cudaLaunchKernelEx()` を呼びます。それ以外は通常の `<<<...>>>` launch です。CUDA device code の `pdl_trigger()` / `pdl_wait()` は sm_90 以上でそれぞれ `griddepcontrol.launch_dependents` / `griddepcontrol.wait` を発行し、それ未満と HIP では no-op です。CUDA の native MMVQ、BF16 MMVF、および verify stamp に wrapper の利用箇所があります。

`docs/DETAILS.md` にはこの環境変数または PDL の説明・性能測定値を確認できませんでした。したがって、この調査では効果の性能値は記載しません。

## 根拠

- `src/kernels/cuda/verify_kernels.cu:1374-1403`: scope、CUDA Runtime 条件、値の opt-in 判定、device 判定と属性判定。
- `src/kernels/cuda/verify_kernels.cu:1406-1456`: kernel 属性キャッシュ、`mode` の判定、capture graph の predecessor 条件。
- `include/strata/kernels/pdl.hpp:1-18,27-32,62-96`: PDL の目的、適用条件、device instruction、通常 launch への fallback。
- `src/core/verify.cpp:842-866`: verify window の group 数と scope を有効にする条件。
- `src/kernels/cuda/native_mmvq.cu:1268-1290,2124`、`src/kernels/cuda/native_bf16.cu:322-328`、`src/kernels/cuda/verify_kernels.cu:1345`: wrapper の利用箇所。
- `CMakeLists.txt:150-158,193`: CUDA build と `CMAKE_CUDA_ARCHITECTURES` の既定値・設定。
- `include/strata/core/emulate.hpp:14-24`: compute capability 判定への `STRATA_EMULATE_CC` の影響。
