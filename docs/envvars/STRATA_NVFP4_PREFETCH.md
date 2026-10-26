# `STRATA_NVFP4_PREFETCH`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU の NVFP4 expert 行カーネルで、重みデータに対するソフトウェア prefetch の先読み距離をバイト単位で指定します。AVX-512 と AVX2 の専用カーネルが対象です。通常の Strata 実行では、適切な CPU で NVFP4 専用行カーネルが選択されたときだけ計算中のメモリアクセスに影響します。

## 値と判定

値は `std::atoi` で整数に変換されます。文字列全体の妥当性検査や範囲制限はありません。

| 環境変数 | 距離 | カーネル内の動作 |
|---|---:|---|
| 未設定 | 2048 バイト | 各 NVFP4 block の処理で、現在の block アドレスから 2048 バイト先を `_mm_prefetch(..., _MM_HINT_T0)` に渡す |
| `0`、空文字、数値として先頭を読めない文字列 | 0 | prefetch 呼び出しを行わない |
| 正の整数 `n` | `n` バイト | 各 block でそのアドレス距離を prefetch する |
| 負の整数 | 負値 | `prefetch_ahead > 0` の条件が成立せず、prefetch しない |

変換は `atoi` のため、先頭の空白と符号を受け付け、数値に続く文字列は無視します（例: `"512tail"` は 512）。したがって、空文字や `"abc"` は 0、`"-4"` は負値になります。上限・下限の clamp はありません。

## 有効になる条件

- 実行経路が CPU のネイティブ expert 計算であること。GPU の NVFP4 カーネルには、この環境変数を読む箇所はありません。
- Gate/up または down の対象型が NVFP4 であること。
- CPU とビルドが対応する専用カーネルを使えること。AVX-512 対応 CPU では `STRATA_NO_NVFP4_512` が未設定なら AVX-512 カーネルが優先されます。そうでなければ、AVX2 対応 CPU で `STRATA_NO_NVFP4_256` が未設定なら AVX2 カーネルが使われます。
- 対象の `n` が NVFP4 block サイズの倍数で、最大 block 数以内であること。条件外では ggml-cpu の `vec_dot` に fallback します。

対象環境変数 `STRATA_NVFP4_PREFETCH` 自体は CPU 機能やモデル状態を検査しません。専用カーネルへ到達しない場合、この変数は評価されず、効果もありません。

## 実行時の詳細

AVX2/AVX-512 の各 `row_dot` は最初の実行時に関数内 `static` の `prefetch_distance()` を評価し、その翻訳単位内に値を保存します。以後、同じカーネルでプロセス環境を変更しても再評価されません。AVX2 と AVX-512 の実装はそれぞれ独立した関数内 static を持ちます。

各 NVFP4 weight block の計算ループで、距離が正なら現在の block (`x + ib`) のアドレスに距離を加えた位置へ `_MM_HINT_T0` の prefetch を発行します。Gate/up 行と down 行はいずれも同じ `row_dot` を経由します。距離 0 以下では prefetch を呼びません。Strata ソースが指定距離で prefetch 要求を出すことまでを説明しており、その要求が CPU 上でどのように処理されるかは対象外です。

同名の読み取りは `src/kernels/cpu/nvfp4_avx512_parity.cpp` にもあります。この実行ファイルは CMake で parity/ベンチマーク用として定義され、環境変数の値をベンチマーク出力に表示します。ここではカーネル呼び出し時に上記の専用カーネルが値を読むため、表示は未設定なら `2048`、設定済みなら元の文字列です。これは通常アプリの別の設定処理ではありません。

## 根拠

- 値の読み取り、`atoi`、既定値 2048: `src/kernels/cpu/nvfp4_avx2.cpp:47-55`, `src/kernels/cpu/nvfp4_avx512.cpp:47-56`。
- block ごとの正値判定と prefetch: `src/kernels/cpu/nvfp4_avx2.cpp:93-103`, `src/kernels/cpu/nvfp4_avx512.cpp:100-110`。
- Gate/up と down の行処理が `row_dot` を呼ぶ箇所: `src/kernels/cpu/nvfp4_avx2.cpp:125-145`, `src/kernels/cpu/nvfp4_avx512.cpp:127-147`。
- CPU/type/fit 条件と専用カーネルから fallback する経路: `src/kernels/cpu/native_expert.cpp:398-423,455-475`。
- 専用ソースのビルドと ISA オプション: `CMakeLists.txt:1719-1747`。
- parity/ベンチマーク実行ファイルとその値表示: `CMakeLists.txt:2139-2143`, `src/kernels/cpu/nvfp4_avx512_parity.cpp:244-247`。
- `docs/DETAILS.md` にはこの変数の説明は見つからず、値や性能効果を裏付ける資料記載は確認できませんでした。
