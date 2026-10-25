# `STRATA_TQ_ISA`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU 上で Strata 独自の trellis（TQ2_T / TQK6 / TQK7）expert カーネルを使うとき、実行する命令セットの上限を指定します。上限を指定しない場合は CPU が実行できる最も広い実装（AVX-512、AVX2、scalar の順）を選びます。この変数はカーネルの有効・無効ではなく、選択する ISA を制限します。

## 値と判定

`src/kernels/cpu/tq_cpu.cpp` は値を文字列全体で、大文字小文字を区別して比較します。

| 値 | ISA 上限 | 選択結果 |
|---|---|---|
| 未設定または空文字 | 2（既定） | CPU が対応すれば AVX-512、次に AVX2、どちらも不可なら scalar |
| `scalar` | 0 | scalar |
| `avx2` | 1 | AVX2 対応 CPU なら AVX2、そうでなければ scalar |
| その他すべて（`avx512`、`AVX2`、空白付き文字列、不明な値を含む） | 2 | 既定と同じ自動選択 |

したがって実装では `avx512` を特別扱いせず、明示値として認識するのは `scalar` と `avx2` だけです。不明値に警告を出したり、scalar に fallback したりはしません。CPU が対応しない ISA は実行時機能判定で候補から外れます。

## 有効になる条件

- CPU native expert 経路で trellis 型（ggml type 144–146）の gate/up または down rows を処理するときに参照されます。ほかの形式の CPU カーネル選択には使われません。
- x86-64 では AVX2 / AVX-512 実装を CPU 機能判定の後に選べます。AVX-512 対応判定は `cpu_avx512_ok()`、AVX2 対応判定は `cpu_avx2_ok()` に委ねられます。
- x86-64 以外では AVX 実装はビルドされず、scalar のみです。
- `STRATA_NO_TQ_KERNELS` が非ゼロとして判定され、かつ利用中の ggml に対象型の `vec_dot` がある場合、trellis rows は ggml-cpu 側へ進むため、この ISA 選択は使われません。対象型の `vec_dot` がない場合は Strata 独自カーネルが維持されます。

## 実行時の詳細

`env_isa_cap()` は `std::getenv()` を呼び、値が未設定または空なら上限 2 を返します。非空値は `scalar` との完全一致で 0、`avx2` との完全一致で 1、それ以外は 2 になります。数値変換は行いません。

`tq_isa()` は選んだ ISA を関数内の `static const` に保存します。最初にこの関数が呼ばれた後でプロセス環境を変更しても、選択は再評価されません。選択は各 row kernel の呼び出しに渡され、AVX-512 / AVX2 / scalar の実装へ dispatch されます。環境変数自体を読み取ったことを示すログはこの実装にはありません。

## 根拠

- `src/kernels/cpu/tq_cpu.cpp:42-49`: 環境変数の読み取り、既定値、完全一致判定。
- `src/kernels/cpu/tq_cpu.cpp:96-115`: CPU 対応判定、自動選択、選択結果の static cache。
- `src/kernels/cpu/tq_cpu.cpp:170-178,183-195`: ISA ごとの row dispatch。
- `src/kernels/cpu/native_expert.cpp:31-37,62-76,224-228,297-299`: trellis 型と独自カーネル経路、ggml fallback、および gate/up・down 側からの呼び出し。
- `include/strata/kernels/cpu/tq_cpu.hpp:21-24`: カーネルの位置づけと変数の設計意図。動作の値判定は実装を根拠とした。
- `docs/GYRO.md:305-309`: CPU trellis kernels の概要と比較用途の説明。記載の性能説明は特定環境の説明であり、本調査では一般化していない。
