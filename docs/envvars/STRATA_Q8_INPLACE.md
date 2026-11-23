# `STRATA_Q8_INPLACE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA native dense のロード時に、条件を満たす dense `Q8_0` 行列を通常の GGUF ブロック形式から `qs`（int8）面と `d`（fp16 scale）面にホスト上で並べ替え、同じデバイス割り当て領域へ転送します。別の packed コピーを作らないため、追加 VRAM はありません。対象から `blk.1.ple_key.weight` は除外されます。ロードした行列は登録表にも同じポインタで登録され、decode MMVQ と prefill の Q8_0 dequantization が packed 面を参照します（`engine/src/core/native_dense.cpp:467-482,628-656`、`engine/src/kernels/cuda/dequant_bf16.cu:395-415`）。

この変数が有効な CUDA 経路では、decode は通常の正確な MMVQ kernel ではなく `q8sm60::kernel` を試します。この kernel は積和の順序が異なり、ソースコメントは結果が通常 kernel と bitwise 一致せず float の丸め差があるとしています（`engine/src/kernels/cuda/native_mmvq.cu:2767-2797,3699-3704`、`engine/src/kernels/cuda/q8_sm60.cuh:11-18`）。prefill 側では Q8_0 dequantization の入力レイアウトが変わり、登録された行列に対して packed-plane dequant kernel が選ばれます（`engine/src/kernels/cuda/dequant_bf16.cu:395-415`）。

## 値と判定

`q8_inplace_on()` は `std::getenv` の結果を関数内 `static const bool` に保存し、値全体が ASCII の `1` 一文字の場合に限り有効とします。未設定、空文字、`0`、`true`、`01`、`1anything`、前後に空白のある値はいずれも無効です。数値変換や大文字小文字を使った比較はありません（`engine/src/kernels/cuda/native_mmvq.cu:2638-2649`）。

この判定に CLI 引数や設定ファイルからの fallback / override はありません。Strata がプロセス環境から直接読みます（同上）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA コンパイル（`__HIPCC__` 未定義） | off | `1` | 空文字、`0`、`true`、`01`、`1x` |
| HIP コンパイル（`__HIPCC__` 定義） | off | なし。このビルドでは関数が常に `false` を返す | すべて。環境値を読み取らない |

行列ごとの適格性には、別変数 `STRATA_Q8_INPLACE_MIN_OUT` も関係します。これは `std::atoi` で読み、変換結果が 1 以上ならその値を出力行数の下限に使い、それ以外（未設定、空文字、非数値、0、負数など）は 640 に戻します。`atoi` のため、先頭の空白や符号を許し、数値の後ろは検査しません（例: `640tail` は 640、`1tail` は 1）。出力行数 `n_out` は下限以上である必要があります（`engine/src/kernels/cuda/native_mmvq.cu:2651-2657,3005-3012`）。

## 有効になる条件

- `engine/src/core/native_dense.cpp` の CUDA native dense ロード経路で、対象 tensor が 2 次元の対応行列として処理され、type が `8`（Q8_0）であること。`blk.1.ple_key.weight` は対象外です（`engine/src/core/native_dense.cpp:459-471`）。
- `STRATA_Q8_INPLACE` が上記の完全一致条件を満たし、`n_in >= 128`、`n_in % 32 == 0`、`n_out >= STRATA_Q8_INPLACE_MIN_OUT` の実効下限、かつ `q8sm60::MAX_COLS` 分の共有メモリが対象デバイスの上限以下であること（`engine/src/kernels/cuda/native_mmvq.cu:3005-3012`）。
- HIP では無効です。native MMVQ の該当関数は `__HIPCC__` 時に `false` を返します（`engine/src/kernels/cuda/native_mmvq.cu:2638-2649,2997-3012`）。Metal の実装スタブも enabled / eligible の両方で `false` を返します（`engine/metal/src/engine/stubs_0145.cpp:155-156`）。SYCL 側の候補名全参照検索では、読み取り箇所は見つかりませんでした。
- `STRATA_Q8_INPLACE_MIN_OUT` は適格性だけを変えます。適格でない場合でも、`STRATA_Q8_PACKED=1` または `STRATA_Q8_SM60=1` による別の packed-copy 経路が成立すれば、そのコピーが使われることがあります。適格な in-place 行列では `do_inplace` が優先され、別コピーの生成をスキップします（`engine/src/core/native_dense.cpp:469-503`、`engine/src/kernels/cuda/native_mmvq.cu:2983-3012`）。
- `STRATA_Q8_SM60=1` が設定されている場合も in-place 判定自体は別に行われます。in-place 登録済み行列の decode はいずれも `q8sm60::launch` を通ります（`engine/src/kernels/cuda/native_mmvq.cu:2767-2793`）。
- サーバーモードや特定 CLI オプションによる分岐はこの実装箇所にはありません。適用は `NativeDense::load()` が呼ばれ、条件を満たす Q8_0 tensor を処理するかで決まります（`engine/src/core/native_dense.cpp:345-356,459-471`）。

## 実行時の詳細

環境値はプロセス起動時ではなく、`q8_inplace_on()` の初回呼び出し時に評価され、その後は `static` キャッシュが使われます。初回呼び出し後に環境を書き換えても反映されません。行列の出力次元しきい値も別の関数内 `static` に初回評価結果が保存されます（`engine/src/kernels/cuda/native_mmvq.cu:2638-2657`）。

`NativeDense::load()` は Q8_0 行列の各ロードについて適格性を判定し、該当すれば host staging buffer を split-plane 形式に詰めて同じサイズの GPU 割り当てへコピーします。通常の Q8_0 行列のアップロードに失敗すると `err` に `native dense upload <tensor>: <CUDA error>` を設定して `false` を返します。登録後は GGUF 配置ポインタをキー、同じ領域の `qs` / `d` 面を値として管理します（`engine/src/core/native_dense.cpp:467-487,628-656,667-670`、`engine/src/kernels/cuda/native_mmvq.cu:3089-3109`）。

decode 時、登録行列は `q8sm60::launch` を使い、9 列以上は最大 8 列ずつに分けて起動します。in-place 登録行列で launch が拒否された場合は `strata q8 inplace: q8sm60 declined in-place tensor (%d x %d, ncols=%d)` を stderr に出して `abort()` します（`engine/src/kernels/cuda/native_mmvq.cu:2767-2797`、`engine/src/kernels/cuda/q8_sm60.cuh:202-215`）。

prefill の Q8_0 dequantization は registry lookup が成功し、行範囲が登録行列内なら packed-plane kernel を起動します。範囲条件に合わない場合や登録がない場合は、通常の GGUF-layout dequantization に続きます（`engine/src/kernels/cuda/dequant_bf16.cu:395-424`）。

## ログと測定値

有効値が初めて評価されたとき、適格行列の有無にかかわらず stderr に次の行を出します（`engine/src/kernels/cuda/native_mmvq.cu:2642-2646`）。

```text
strata q8 inplace: eligible dense Q8_0 matrices packed in-place (+0 MiB VRAM)
```

ロード中に 1 件以上を in-place 化した場合は、件数と合計バイト量を MiB 換算して次を stderr に出します（`engine/src/core/native_dense.cpp:654-656`）。

```text
native dense: STRATA_Q8_INPLACE=1 packed %zu Q8_0 matrices in-place (%.1f MiB, +0.0 MiB VRAM)
```

ソースコメントにある float 丸め差の説明は性能測定値ではありません。この調査では build・GPU 実行・測定を行っていません。

## 資料との照合

`docs/SETTINGS.md:282` は `STRATA_Q8_INPLACE` の対象を「NVIDIA and AMD」としていますが、調査対象コードは `__HIPCC__` ビルドで有効・適格性関数を常に false にします。また Metal スタブも常に false です。従ってこの表記は現行実装と一致しません。`docs/NVIDIA_V100.md:67` の NVIDIA 向け説明は、CUDA 実装が in-place 化する説明と整合します。ここではコードで確認できた挙動を記載しました。

## 根拠

- `engine/src/kernels/cuda/native_mmvq.cu:2638-2657` — 変数の読み取り、文字列判定、static cache、しきい値環境変数。
- `engine/src/kernels/cuda/native_mmvq.cu:2983-3012` — Q8_0 の有効化・適格性、形状と共有メモリ条件、HIP 無効化。
- `engine/src/core/native_dense.cpp:467-487,628-656` — 行列選別、in-place 転送、登録、エラーと成功ログ。
- `engine/src/kernels/cuda/native_mmvq.cu:2767-2797,3089-3109,3699-3704` — registry 利用、decode kernel と拒否時の終了経路。
- `engine/src/kernels/cuda/q8_sm60.cuh:11-18,202-215` — decode の積和順序と起動条件。
- `engine/src/kernels/cuda/dequant_bf16.cu:395-424` — prefill dequantization での packed lookup と fallback。
- `engine/metal/src/engine/stubs_0145.cpp:155-156` — Metal の無効スタブ。
- `docs/SETTINGS.md:282`、`docs/NVIDIA_V100.md:67` — 資料との照合。
