# `STRATA_PF_W16_CACHE_MIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

CUDA の prefill 用 `Gemm::native()` が、GGUF の量子化 weight を FP16 に dequantize した結果を GPU メモリに保持する上限を MiB 単位で指定します。同じ weight を後続の GEMM が使うと、再 dequantize せず保持した FP16 weight を使います。既定では無効です。

環境変数名の全参照を検索すると、実際に値を読むのは `src/prefill/gemm.cu` の `Gemm::native()` のみです。ヘッダー、サーバー、実験 variant にも名前はありますが、そこはコメントまたは設定文字列です。CUDA 以外ではこのキャッシュ分岐はコンパイル対象になりません。

## 値と判定

`std::getenv()` で未設定かどうかを判定し、設定されていれば `std::atoll()` の戻り値に `1 MiB` を掛けます。文字列全体の形式検査や範囲検査はありません。

| 値 | 判定と動作 |
|---|---|
| 未設定 | この `Gemm` インスタンスでは予算 0、無効。空き VRAM に応じた自動有効化もありません。 |
| 空文字、数値に変換できない文字列 | `atoll()` が 0 を返すため無効。エラーや警告は出しません。 |
| 正の整数 | `atoll()` が読む10進数の前置部分を MiB に換算した値が累積キャッシュ予算になります。例えば `2048` と `2048MiB` はどちらも 2048 MiB、`5.9` は 5 MiB です。先行空白と符号も `atoll()` の変換規則に従います。 |
| 0 または負数 | 予算が正でないため無効。 |

明示設定時の VRAM 留保は固定 2 GiB です。設定値が予算上限であり、実際に保持できる量はカードの空き VRAM と各 weight の大きさにも制限されます。CLI 引数による同名設定や優先順位はありません。別の環境変数 `STRATA_DEQUANT_SIDE` が side scratch を有効にすると、このキャッシュ経路は使われません。

根拠: `src/prefill/gemm.cu:1411-1423,1425-1433`; `include/strata/prefill/gemm.hpp:96-105`; `src/prefill/gemm.cu:637-643,1468-1483`。

## 有効になる条件

- CUDA ビルドであること。`Gemm::native()` のキャッシュ部分は `#ifndef STRATA_USE_HIP` 内にあります。HIP ビルドではこのコードが除外されます。Metal の `Prefill::init()` は Metal engine に委譲して通常の GPU `Gemm` を初期化しません。
- `Gemm::native()` が呼ばれること。通常は native GGUF weight を使う prefill の dense projection で呼ばれます。`native_proj()` は native weight がない場合はエラーを返し、ある場合に `gm.native()` を呼びます。native PLE key も `Gemm::native()` を呼ぶ経路です。Qwen3.5/3.6 engine でも prompt の行数 `T` が 8 を超えるとこの GEMM を使います。
- `w16_budget_ > 0` かつ `side_scratch_ == nullptr` であること。
- weight が予算内に収まり、`cudaMemGetInfo()` が成功し、割り当て後にも 2 GiB より多い空き VRAMが残ること。

`N*K` が scratch に収まり切らない場合でも、キャッシュ割り当てに成功すれば全 weight を dequantize して GEMM に使います。条件を満たさない、または割り当てられない場合は通常の dequantize 経路に進みます。`STRATA_DEQUANT_SIDE` の読み取りは CUDA で先頭文字が `1` の場合に有効となり、prefill 初期化時に side scratch を設定します。この読み取り箇所自体に OS 別の分岐はありません。

根拠: `src/prefill/gemm.cu:1353-1372,1403-1453`; `src/prefill/prefill.cpp:1692-1703,1883-1890,2931-2936,3957-3961`; `src/qwen35/q36_engine.cu:1177,1563-1572`。

## 実行時の詳細

値はプロセス共通の static cache ではなく、各 `Gemm` インスタンスが最初の `native()` 呼び出し時に読み、`w16_budget_` に保持します。そのインスタンスでは以後読み直しません。別の `Gemm` インスタンスはそれぞれ初回呼び出し時に環境を読みます。キャッシュ entry は device weight pointer、量子化 type、`N`、`K` の組で照合されます。

新しい weight のサイズは `N*K*2` bytes です。累積使用量と予算の合計が上限内で、空き VRAM `fb` が weight サイズと留保量の合計より大きければ、`cudaMalloc()` 後に全 weight を dequantize して保持します。キャッシュ hit は保持済み weight で `f16()` を実行します。保持した entry は `Gemm` の破棄時に `cudaFree()` されます。

`cudaMemGetInfo()` または `cudaMalloc()` が失敗したときは、stderr に一度だけ `strata prefill: FP16 weight cache ...` を出し、その時点の既使用量を上限として以降の割り当てを止めます。既使用量が 0 ならキャッシュは無効化されます。新規 weight がユーザー指定予算に収まらない場合は、この割り当て失敗ログを出さずに通常経路へ進みます。通常経路は scratch に weight 全体が収まらなければ行ごとの slice に分け、dequantize と GEMM を行います。明示設定値が無効でも、専用の無効値警告や終了経路はありません。

キャッシュ使用時は full weight を使った `f16()` の GEMM となり、未キャッシュで scratch に収まらない場合の sliced GEMM とは計算形状が異なります。現行ソースのコメントは一部 GPU で bit-exact でない事例を記録していますが、この調査では実機で数値差を再測定していません。

根拠: `include/strata/prefill/gemm.hpp:99-105`; `src/prefill/gemm.cu:646-671,1411-1452,1454-1463`。
