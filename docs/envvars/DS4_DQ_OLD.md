# `DS4_DQ_OLD`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `main...origin/main` で未コミット変更なし。

## 役割

DeepSeek V4.1 のチャンク化 prompt で使う低ビット dense 行 dequantizer を選びます。`DS4_DQ_OLD` が有効なら旧 `dq_rows_kernel`、無効なら新しい coalesced transpose の `dq_rows_kernel2` を選びます。選択値は `iq::dequant_rows()` が呼ばれるたびに評価されます。

## 値と判定

実装は未設定と空文字を同じ `-1`（環境変数による指定なし）として扱い、それ以外は `std::atoi()` の結果が 0 か非0かだけを見ます。文字列全体の検証や範囲検査はありません。

| 値 | `atoi` の結果 | 選択 |
|---|---:|---|
| 未設定、空文字 | 判定なし (`-1`) | 下記の backend / `DS4_DEFAULTS` 既定値による |
| `0`、`00`、`0abc`、`abc` | 0 | 新 kernel |
| `1`、`2`、`-1`、`1abc` | 非0 | 旧 kernel |

`atoi` の通常の変換規則が適用されるため、先頭空白や符号を含む数値 prefix も変換されます。変換不能な文字列は 0 となり、新 kernel を選びます。値が `1` のときだけ有効になる boolean parser ではありません。

## 有効になる条件

- **明示値**: 空文字でない値は `atoi` の結果に従って選択され、`DS4_DEFAULTS=026` より優先されます。
- **未設定または空文字**: `DS4_DEFAULTS` が `026`、`0.2.6`、`v0.2.6` のいずれかなら旧 kernel が既定です。これらは完全一致で判定されます。
- **CUDA**: 上記の `DS4_DEFAULTS` 既定がなければ新 kernel が既定です。CUDA には `gfx11` 判定がないためです。
- **HIP**: `DS4_DEFAULTS` 既定がなければ、現在の GPU の `gcnArchName` が `gfx11` で始まる場合に旧 kernel、それ以外は新 kernel です。デバイス情報の取得に失敗した場合や device index が 0–63 の範囲外の場合は新 kernel になります。
- **呼び出し対象**: この選択はチャンク化 prompt の GEMM で `gg::rows()` が低ビット GGUF dense matrix を行 dequantize するときに使われます。`iq::dequant_rows()` の対応型は IQ2_XXS / XS / S、IQ3_XXS / S、IQ4_XS、IQ1_S / M、Q4_K / Q5_K / Q6_K / Q2_K / Q3_K です。CLI 引数による上書きはコード上ありません。

## 実行時の詳細

`ds4::defaults_026()` は `DS4_DEFAULTS` を初回評価時に `static const` へ保存します。対して `DS4_DQ_OLD` は `dq_use_old_kernel()` の呼び出しごとに読み直されます。したがって、環境の変更は `DS4_DQ_OLD` については次回の行 dequantize 呼び出しから反映され得ますが、`DS4_DEFAULTS` の変更は初回評価後には反映されません。HIP の `gfx11` 判定結果は GPU ごとの static cache に保存されます。

`dequant_rows()` は `raw == nullptr`、`k % 256 != 0`、または `n <= 0` なら kernel を起動せず `false` を返します。有効な入力では環境判定後、型 switch を通じて選択した kernel を起動し、最後に `cudaGetLastError() == cudaSuccess` を返します。上位の `ds4::gguf::rows()` は dequantize が `false` の場合 stderr に `ds4 gguf rows: a low-bit type not covered` を出してエラーカウンターを増やします。環境変数の値や kernel 選択を知らせるログは見つかりませんでした。

## 根拠

- `src/dsv41/ds4_iq.cu:1398-1423` — kernel の役割、`DS4_DQ_OLD` の読み取りと `atoi` 判定、`DS4_DEFAULTS` との順序、HIP の architecture 判定と cache。
- `src/dsv41/ds4_iq.cu:1425-1452` — 入力境界、選択した kernel の起動、対応型、CUDA/HIP エラー結果。
- `src/dsv41/ds4_experts_rule.hpp:22-28,215-220` — `DS4_DEFAULTS` の完全一致 token と static cache、旧 kernel の default rule。
- `src/dsv41/ds4_gguf.cu:1328-1348` — GGUF 行 dequantizer の呼び出し元と失敗時の `fail()`。`src/dsv41/ds4_gguf.cu:32-44` は stderr 出力とエラーカウンターを定義。
- `src/dsv41/ds4_model.cu:3435-3451` — チャンク化 prompt の GEMM が GGUF 行を `gg::rows()` で再構成する箇所。
- `src/dsv41/ds4_iq.cu:1291-1293,1398-1401` — kernel 2 種の実装説明とコメントに記載された設計意図。性能値はソースコメント上の測定記録であり、この調査では再測定していません。
