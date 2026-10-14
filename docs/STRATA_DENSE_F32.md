# `STRATA_DENSE_F32`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。作業開始時の Strata は `main`、作業ツリーは clean。外部ライブラリ自身の環境変数動作は対象外。

## 役割

実験用 CUDA ビルドの FP16 入力 GEMM のうち、限定された大きな dense projection を FP32 へ変換した入力で `cublasSgemm` に計算させます。対象外の形状では従来の FP16 入力 `cublasGemmEx` に進みます。Strata が環境変数を読むのはこの切り替え判定であり、cuBLAS 内部の動作は説明対象にしません。

## 値と判定

`std::atoi(v) != 0` で判定し、文字列全体の妥当性は検査しません。未設定・空文字・数値変換結果が 0 の値は無効です。先頭の空白や符号を含む整数を `atoi` が変換でき、数値の後ろに文字があっても数値部分で判定します（例: `01`、`1anything`、`-1` は有効、`0anything`、`false`、`anything`、空文字は無効）。大文字小文字の比較はありません。

| 条件 | 結果 |
|---|---|
| 変数 unset | 無効 |
| 空文字、`0`、数値で始まらない文字列 | 無効（`atoi` の結果が 0） |
| `atoi` の結果が 0 以外 | 候補として有効。さらに下記の GPU・形状条件を満たす必要がある |

環境値の判定結果は関数内 `static const bool` に一度保存されます。初回の適格な呼び出しで評価された後は、同じプロセス内で環境を変更しても再評価されません。ソース内の `gemm_set_dense_f32()` は parity 用の上書き口で、通常の `strata` 実行経路から呼び出されていません。

## 有効になる条件

すべて満たす必要があります。

- CUDA でビルドされ、`STRATA_EXPERIMENTAL_SM60` がコンパイル時に定義されている。通常の ready-made engine ではこの実験コードは含まれません。CMake の実験オプションは CUDA 12.x を要する Pascal / Volta 向けビルドとして説明されています。
- 実行中の現在デバイスの compute capability が `60` 以上 `70` 未満（6.x）。したがって Volta の 7.0 は CMake の実験ビルド対象でも、この環境変数による FP32 GEMM 経路の対象外です。デバイス属性取得に失敗した場合は 0 として扱われ、経路は無効です。
- `Gemm::f16()` に渡される `beta` が `0.0f`。
- `(N,K)` とトークン数 `T` が次のいずれか。

| `N` | `K` | 最小 `T` |
|---:|---:|---:|
| 10240 または 12288 | 2560 | 256 |
| 6144 | 2560 | 512 |
| 2560 | 6144 または 4096 | 4096 |

同じ `K` を持つ行スライスなどでも、表にない `(N,K)` は対象になりません。`beta` が 0 以外、`T` がしきい値未満、または GPU・ビルド条件が不足する場合はこの経路を使いません。HIP 側にはこの環境変数の判定・切り替えはありません。

## 実行時の詳細

`Gemm::native()` は重みを FP16 scratch に dequantize した後、`Gemm::f16()` を呼びます。`Gemm::f16()` は対象条件を満たすと重みと入力を FP32 コピーへ変換し、`cublasSgemm` を実行して通常の FP16 `cublasGemmEx` 経路を飛ばします。重みは全体、入力は最大 64 MiB 相当の FP32 スライスに分けます。切り替え時に stderr へ一度だけ `prefill gemm: the dense projections' FP16 GEMMs run as cublasSgemm on FP32 copies (STRATA_DENSE_F32=1; gemm_f32_parity checks the bits against this cuBLAS)` を出します。

変換用 GPU バッファが不足して拡張に失敗した場合は CUDA の直近エラーをクリアして、この FP32 経路を諦め、後続の FP16 `cublasGemmEx` に進みます。GPU メモリ不足によるこの分岐では、上記の切り替えログは出ません。

## 文書・測定値との照合

`docs/OLDER_GPUS.md` は、P40 と cuBLAS 12.4.5.8 での測定として、対象 GEMM の `cublasSgemm` 化、`gemm_f32_parity` による 5,201 チャンクサイズの bitwise 一致、7K prompt の測定結果を記載しています。同文書は一致が cuBLAS ビルドに依存すると説明し、利用する toolkit のライブラリで parity を実行してから有効化するよう案内しています。これは資料に記載された P40 / cuBLAS 12.4.5.8 の結果であり、他の GPU・cuBLAS ビルドでの一致や性能を保証するものではありません。調査では GPU 実行や性能測定を行っていません。

## 根拠

- `src/prefill/gemm.cu:543-577` — コンパイル条件、環境変数の `atoi` 判定、compute capability 条件。
- `src/prefill/gemm.cu:578-588` — 対象形状と最小チャンク長。
- `src/prefill/gemm.cu:728-782` — `Gemm::f16()` の条件、変換・分割・`cublasSgemm` 呼び出し、失敗時の fallback とログ。
- `src/prefill/gemm.cu:901-953` — `Gemm::native()` が重みを FP16 に dequantize して `f16()` を呼ぶ経路。
- `src/prefill/gemm.cu:500-517` — compute capability の取得とデバイスごとの cache。
- `CMakeLists.txt:148-198,607-624` — 実験ビルドの条件と `strata_prefill` への実装組み込み。
- `include/strata/prefill/gemm.hpp:92-96` — setter の既定値と parity 用途。
- `docs/OLDER_GPUS.md:122-126,128-134` — 文書化された測定条件、結果と適用上の注意。
