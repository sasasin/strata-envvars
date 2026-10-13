# `STRATA_NO_NORM_ROPE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

ネイティブ GPU の RMSNorm と RoPE を一つのカーネルに融合する経路を無効にします。値が無効化条件に当たる場合でも、`--native-rope` 自体や通常のネイティブ RoPE は無効になりません。融合を見送った呼び出し元は、RMSNorm と RoPE を別々に実行します。また、in-place のネイティブ RoPE カーネルでは融合可能性に合わせた 32-thread 起動を使わず、128-thread 起動を選びます。

## 値と判定

環境変数の文字列全体や数値としての値は解析せず、最初の文字だけを検査します。空文字は設定済みでも無効化条件にはなりません。

| `STRATA_NO_NORM_ROPE` | 判定 |
|---|---|
| 未設定、空文字、先頭文字が `0` | この変数による無効化なし |
| それ以外（例: `1`, `true`, `false`, 空白で始まる値） | 融合不可 |

判定結果は `native_norm_rope_usable()` 内の `static const bool` に保存されます。したがって最初の呼び出し後にプロセス内で環境を変更しても再評価されません。HIP ビルドでは、この変数が無効化しなかった場合に限り、別の `STRATA_NORM_ROPE` が未設定・空・先頭 `0` なら融合不可となります。`STRATA_NO_NORM_ROPE` が無効化側に当たれば、`STRATA_NORM_ROPE` の値にかかわらず無効です。

## 有効になる条件

この変数は融合を止める方向にだけ働きます。`STRATA_NO_NORM_ROPE=0` は融合を明示的に有効化する設定ではありません。

- CUDA コンパイル（`__HIPCC__` ではない）では、変数による無効化がなければ融合可能性フラグは既定で ON です。
- HIP コンパイルでは、無効化されていないことに加え、別変数 `STRATA_NORM_ROPE` の先頭文字が空でも `0` でもない必要があります。
- いずれのビルドでも、`head_dim` が 128 または 256、`n_rot` が 64 の場合だけ `native_norm_rope_usable()` は true になります。
- 実際の推論経路で融合を使うにはネイティブ RoPE が有効であることが必要です。通常は CLI の `--native-rope`（または、それを有効化する `--native` プリセット）が必要です。QSA の verify 経路ではネイティブ QSA も必要です。

## 実行時の詳細

CUDA 実装 `src/kernels/cuda/native_rope.cu` と SYCL 向けの対応実装 `sycl/src/kernels/cuda/native_rope.dp.cpp` は、同じ先頭文字判定と `__HIPCC__` 分岐を持ちます。API コメントは CUDA では既定有効、HIP では AMD 側の parity check が通るまで既定無効で、`STRATA_NORM_ROPE` による opt-in と説明しています。

融合が利用可能な場合、QSA verify は Q/K の RMSNorm と RoPE を `native_qsa_rms_norm_rope()` 一回で処理します。無効な場合は RMSNorm の後にネイティブ RoPE（またはネイティブ経路が無効なら通常の RoPE）を呼びます。MTP の K append と Q projection にも同じ fused kernel の分岐があり、無効時は個別処理へ進みます。特に K append は `T == 1` の場合にだけ融合分岐を使います。これらの分岐は `STRATA_NO_NORM_ROPE` の値を直接読むのではなく、キャッシュ済みの `native_norm_rope_usable()` の結果を使います。

無効化専用のログや警告は見つかりません。変わるのはカーネル選択と起動形状です。`docs/DETAILS.md` にはこの変数や融合経路の説明・測定値を確認できませんでした。性能差や出力一致をこの調査で実測したものではありません。API コメントには parity check 6 で fused kernel が分離した2処理と bit-identical とありますが、ここではコメントの記述としてのみ扱います。

## 根拠

- `src/kernels/cuda/native_rope.cu:175-186` — 環境変数、HIP opt-in、対応する head dimension と回転幅の判定。
- `sycl/src/kernels/cuda/native_rope.dp.cpp:229-240` — SYCL 向け実装の同等の判定。
- `src/kernels/cuda/native_rope.cu:208-209` — in-place RoPE の 32-thread / 128-thread 起動選択。
- `include/strata/kernels/native_rope.hpp:21-30` — fused API と CUDA/HIP の既定動作に関するコメント。
- `src/core/verify.cpp:1196-1212,1331-1362`、`sycl/src/core/verify.cpp:1078-1094` — QSA verify の融合呼び出しと分離処理への fallback。
- `src/core/mtp.cpp:740-752,806-820`、`sycl/src/core/mtp.cpp:866-878,933-955` — MTP の K append / Q projection の融合条件と fallback。
- `src/program/generate.cpp:371,1868-1873,2501-2505,3055-3057` — `--native-rope` と `--native` プリセット、実行時フラグ設定。
- `docs/DETAILS.md` — `STRATA_NO_NORM_ROPE` の説明や測定値は確認できず。
