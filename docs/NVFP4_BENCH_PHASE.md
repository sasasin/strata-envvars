# `NVFP4_BENCH_PHASE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

CUDA 用の `nvfp4_decode_bench` が、grouped native expert decode のどの段階を計測するかを切り替えます。Strata の通常の生成・server 実行コードからは参照されず、この診断ベンチ専用です。CMake では CUDA 有効時に `nvfp4_decode_bench` 実行ファイルとして定義されています（`CMakeLists.txt:1818-1823`）。

## 値と判定

ベンチは `std::getenv()` で設定有無を調べ、設定されていれば値を `std::atoi()` に渡します。文字列全体の妥当性検査やエラー表示はありません。

| 環境変数の値 | `atoi` の結果 | 実行段階 |
|---|---:|---|
| 未設定 | `0`（初期値） | gate/up、SwiGLU、量子化、down の全段階 |
| `1` に変換される値 | `1` | gate/up、SwiGLU、量子化まで。down を省略 |
| `2` に変換される値 | `2` | gate/up、SwiGLU、量子化を省略し、down のみ |
| その他 | `0` または `1` / `2` 以外 | `1` / `2` 以外は全段階 |

`atoi` のため、先頭の空白と符号を含む整数表記を受け付け、数値の後ろに文字が続いても数値部分を変換します（例: `2abc` は 2）。空文字や数値に変換できない文字列は 0 になり、全段階の実行になります。値はベンチ起動時に一度読みます。

## 有効になる条件

- `nvfp4_decode_bench` を実行している場合にだけ読み取られます。Strata の本体を起動しても、この変数による切替はありません。
- ベンチのビルドには CUDA が有効である必要があります。CMake の `STRATA_ENABLE_CUDA` 条件内にターゲット定義があります。
- `native_expert_set_mode(-1, phase)` でモードを設定するため、ベンチ側から expert layout mode は固定せず、カーネル既定の選択に任せます。`NVFP4_BENCH_PHASE` は段階だけを指定します。

## 実行時の詳細

ベンチは `NVFP4_BENCH_PHASE` を読み、`native_expert_set_mode(-1, std::atoi(ph))` を呼んでから、warm-up と反復計測で同じ `native_expert_grouped()` 呼び出しを使います。phase 2 は gate/up カーネルと SwiGLU・量子化を飛ばし、down カーネルへ進みます。phase 1 は gate/up と SwiGLU・量子化を実行した後、down の直前で戻ります。値 0 およびその他の整数は両方の段階を実行します。

出力は通常どおり計測時間、重みの帯域幅、出力バッファの hash を表示しますが、phase 1/2 は処理を途中で切り出すベンチ設定であり、完全な expert 推論結果の hash とはみなせません。環境変数専用の警告・ログはありません。

## 根拠

- `src/kernels/nvfp4_decode_bench.cpp:1-9` — 実行ファイルの目的とベンチの位置付け。
- `src/kernels/nvfp4_decode_bench.cpp:118-121` — 環境変数の読み取りと phase の設定。
- `src/kernels/cuda/iq_kernels.cu:4193-4193,4209-4216` — phase の初期値と setter。
- `src/kernels/cuda/iq_kernels.cu:4337-4354,4395-4415,4417-4449` — gate/up、SwiGLU・量子化、down の条件分岐。
- `src/kernels/nvfp4_decode_bench.cpp:131-154` — 計測と出力 hash の表示。
- `CMakeLists.txt:1818-1823` — CUDA 条件下でのベンチ実行ファイル定義。
- `docs/NVFP4.md:88-97` — `nvfp4_decode_bench` の性能測定記載。phase 別の測定値は記載されていない。
