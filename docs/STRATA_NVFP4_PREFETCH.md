# `STRATA_NVFP4_PREFETCH`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

NVFP4 expert の CPU 行カーネルで使うソフトウェア prefetch の先読み距離をバイト単位で指定します。AVX-512 と AVX2 の実装がそれぞれ同名の変数を読み、現在処理中の NVFP4 ブロック位置から指定距離先を `_mm_prefetch(..., _MM_HINT_T0)` で prefetch します。正の距離を指定すると、行データの読み込みループで各ブロックについて prefetch 命令が発行されます。

## 値と判定

| 値 | カーネル内の値 | 動作 |
|---|---:|---|
| 未設定 | `2048` | 2048 バイト先を prefetch |
| 設定あり | `std::atoi` の戻り値 | 戻り値が正なら、そのバイト数先を prefetch |
| 空文字、数値に変換できない文字列（例: `foo`）、`0` | `0` | prefetch しない |
| 負の数 | 負値 | prefetch しない |

文字列全体の厳密な数値検証や範囲 clamp はありません。`atoi` の変換規則に従うため、先頭の空白と符号は認識され、数字の後ろにある文字列は変換結果に影響しません（例: `"1536tail"` は `1536`）。数字に変換できない文字列は `0` になり、prefetch は無効です。設定値が正でも、距離が実際の行サイズ内に収まるかをこのコードは検査しません。

## 有効になる条件

- CPU NVFP4 expert の gate/up または down 行処理が呼ばれること。
- AVX-512 カーネルが選ばれる場合は AVX-512 対応 CPU であり、`STRATA_NO_NVFP4_512` が未設定で、対象次元が NVFP4 ブロック単位（64値）で割り切れ、最大 64 ブロック（4096値）以下であること。
- AVX2 カーネルが選ばれる場合は AVX2 対応 CPU であり、`STRATA_NO_NVFP4_256` が未設定で、対象次元が同じサイズ条件を満たすこと。AVX-512 経路が選ばれない場合のほか、AVX-512 対応 CPU でも `STRATA_NO_NVFP4_512` を設定して AVX2 経路に入る場合が該当します。
- どちらの最適化経路も条件を満たさない場合、行積は ggml-cpu の dot 経路へ進み、この変数を使う NVFP4 行カーネルは実行されません。

この変数自体は AVX-512/AVX2 の選択を変えず、選択されたカーネルの prefetch 距離だけを変えます。CPU 側の expert 行処理で読み取られる設定です。CUDA/HIP/SYCL の GPU カーネルや Metal 実装に同名設定の処理は見つかりませんでした。

## 実行時の詳細

AVX-512 と AVX2 の各ソースにある `prefetch_distance()` は `static const int` を初回呼び出し時に初期化します。そのため環境変数は、それぞれのカーネル系統がプロセス内で最初に行処理をした時点で読み取られ、その後に環境を書き換えてもその系統では再評価されません。AVX-512 と AVX2 は別々の翻訳単位で別々の static 値を持つため、両方の経路が同一プロセスで使われた場合、それぞれの初回呼び出し時点の値が保存されます。

行ループは NVFP4 ブロック `ib` ごとに、値が正の場合だけ `(x + ib)` のアドレスから `prefetch_ahead` バイト先を prefetch します。距離が 0 以下の場合、ループ自体は通常どおり処理され、prefetch 命令だけが省かれます。Strata のコードに、この変数によるログ出力やエラー出力はありません。

## 根拠

- 値の読み取り、既定値、遅延初期化: `src/kernels/cpu/nvfp4_avx512.cpp:47-56`、`src/kernels/cpu/nvfp4_avx2.cpp:47-55`。
- 距離が正の場合のみ発行される prefetch: `src/kernels/cpu/nvfp4_avx512.cpp:100-110`、`src/kernels/cpu/nvfp4_avx2.cpp:99-103`。
- AVX-512 / AVX2 の選択、NVFP4 型・CPU 対応・次元条件、ggml fallback: `src/kernels/cpu/native_expert.cpp:204-218,258-276`。
- pool から gate/up と down の native 行処理を呼ぶ箇所: `src/kernels/cpu/pool.cpp:705-719`。
- 両ファイルの CPU kernel library への登録と ISA compile flags: `CMakeLists.txt:1317-1342`。
- `docs/DETAILS.md` は NVFP4 に触れていますが、この環境変数の既定値・値の判定・効果を説明する記述は確認できませんでした。
