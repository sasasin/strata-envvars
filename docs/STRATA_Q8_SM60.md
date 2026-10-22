# `STRATA_Q8_SM60`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の native MMVQ 経路で、Q8_0 重み行列の decode GEMV に Pascal GP100 向けカーネル `q8sm60::kernel` を opt-in します。対象の重みをロード時に `qs` と fp16 scale の平面へコピーし、Q8_0 の dense projection と native output head の decode でコピーを使います。元の GGUF 配置も保持され、prompt 経路は引き続き元データを使います。通常の CUDA decode 経路は `small_mmvq` です（`src/kernels/cuda/native_mmvq.cu:1930-1947,2866-2870`; `src/core/native_dense.cpp:363-382`; `src/core/native_head.cpp:54-78`）。

## 値と判定

値は文字列全体で厳密に比較され、`"1"` だけが有効です。数値変換や前後空白の除去はありません。

| 値 | 結果 |
|---|---|
| 未設定、空文字 | 無効 |
| `1` | 有効 |
| `0`, `01`, `true`, ` 1`, `1 ` など | 無効 |

判定は `q8_sm60_on()` 内の `static const bool` に一度だけ保存されます。そのプロセスで最初にこの関数が評価された後に環境を変更しても反映されません。有効と判定された最初の呼び出しでは stderr に `strata q8 sm60: Q8_0 decode GEMVs on the Pascal kernel (STRATA_Q8_SM60=1)` を出します（`src/kernels/cuda/native_mmvq.cu:1932-1943`）。

## 有効になる条件

- CUDA ビルドであること。HIP ビルドではコンパイル時分岐により常に無効です。Metal の stub も pack 関数で `false` を返します（`src/kernels/cuda/native_mmvq.cu:1932-1947,2252-2283`; `metal/src/engine/stubs_0145.cpp:147-149`）。
- 対象行列が Q8_0 で、`n_in >= 128`、`n_in` が 32 の倍数、`n_out > 0` であること。native dense のロードでは `blk.1.ple_key.weight` を除外します（`src/kernels/cuda/native_mmvq.cu:2240-2243,2257-2258`; `src/core/native_dense.cpp:363-382`）。
- カーネル起動時は `ncols` が 1〜8、`n_in` が 32 の倍数かつ 128 以上、動的 shared memory が 48 KiB 以下であること。shape がカーネルに拒否された場合、通常の packed exact kernel の対象 shape ならそちらに fallback し、それ以外は packed registry の経路を抜けて元の GGUF 配置を使う exact kernel に進みます（`src/kernels/cuda/q8_sm60.cuh:21-22,118-148`; `src/kernels/cuda/native_mmvq.cu:2048-2072,2240-2243`）。

コード上に compute capability の実行時チェックはありません。機能の説明と測定対象は Pascal GP100 ですが、環境変数の分岐自体は CUDA デバイスを調べずに有効になります。どの GPU で性能上有利かはこの分岐からは判断できません（`src/kernels/cuda/native_mmvq.cu:1932-1943`）。

`STRATA_Q8_PACKED=1` も native dense の Q8_0 行列を pack する別の理由になります。`native_q8_0_packed_enabled()` はどちらか一方が有効なら true を返すため、両方を設定した場合は SM60 カーネルが選択可能な packed registry も作られます（`src/kernels/cuda/native_mmvq.cu:2232-2238`; `src/core/native_dense.cpp:363-382`）。

## 実行時の詳細

native dense の準備時に適格な Q8_0 行列を host 上で pack して追加の CUDA allocation に転送し、元の GGUF 配置のデータとともに registry に登録します。Qwen 3.6 専用 engine の行列 loader も同じ enabled / eligible 判定、pack、registry 登録を行います（`src/qwen35/q36_engine.cu:1011-1023`）。output head は `type_ == 8` の場合に別途 pack を試みます。head の pack は追加 VRAM が確保できない場合や同期中の pack が失敗した場合に stderr へ理由を出して失敗し、通常配置のまま継続します。成功時は対象名・行列サイズ・追加 VRAM 量を stderr に出します（`src/core/native_dense.cpp:363-382,473-492`; `src/core/native_head.cpp:68-79`; `src/kernels/cuda/native_mmvq.cu:2252-2281`）。

decode の Q8_0 MMVQ 呼び出しは registry 内に一致する packed 行列があると SM60 kernel の起動を試します。kernel は Q8_1 activation を workgroup ごとに shared memory に移し、出力行の積和を計算します。通常カーネルと加算順が異なるため、出力が bitwise 一致する保証はありません。入力 shape を kernel が受け付けない場合には前節の fallback が適用されます（`src/kernels/cuda/native_mmvq.cu:2053-2072,2866-2870`; `src/kernels/cuda/q8_sm60.cuh:21-22,38-91,118-148`）。

なお `src/kernels/cuda/q8_sm60.cuh` 内の `STRATA_Q8_SM60_BPS` は別環境変数で、SM あたりの起動 block 数を `atoi` で読み、正数でなければ既定値 4 を使います。この文書の対象変数の値判定とは独立です（`src/kernels/cuda/q8_sm60.cuh:85-95`）。

## 根拠と資料との照合

`docs/OLDER_GPUS.md:110-128` は機能を GP100 向けとして説明し、Q8_0 dense 行列と head の追加 copy、通常 kernel との加算順の違い、shape による fallback、必要な Q8_0 dense model の作成手順を記載しています。ソースでは厳密な `"1"` 判定と CUDA/HIP の差、pack の失敗ログ、kernel が拒否する shape の fallback を確認しました。

性能値を新たに検証していません。同資料は PH402 SKU 200、4 GP100 dies、Windows 11、CUDA 12.9、Flash-Next IQ3_XXS などを条件として、`STRATA_Q8_SM60=1` の decode 平均 38.9 tok/s と GPU verify-window 時間を報告しています（`docs/OLDER_GPUS.md:144-156`）。これらは資料中の測定報告であり、他の環境での性能を示すものではありません。
