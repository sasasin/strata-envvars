# `DS4_DQ_OLD`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。候補名の参照をリポジトリ全体で検索し、実装の読み取り箇所を確認した。外部ライブラリの環境変数動作は対象外。

## 役割

DeepSeek V4.1 engine の chunked prompt path で、低 bit dense weight を FP16 行列に展開する dequantizer を選びます。旧 row-per-lane kernel (`dq_rows_kernel`) と新 coalesced transpose kernel (`dq_rows_kernel2`) の選択です。decode 用 matvec など、dense dequantizer を通らない処理には適用されません。

この変数を読む実装は `src/dsv41/ds4_iq.cu` の一箇所です。CMake 上では DSV41 engine の専用実行ファイル `strata-dsv41` に含まれますが、`STRATA_BUILD_DSV41` は既定で OFF です（`CMakeLists.txt:931-945`）。

## 値と判定

読み取り時に、未設定または空文字は `-1`（明示指定なし）、それ以外は `atoi(value) != 0` なら `1`、ゼロなら `0` に変換します。文字列全体の検証はありません。したがって `1`, `01`, `+1`, `-1`, `1tail` は `1`、`0`, `0tail`, `true`, `false`, 数字で始まらない文字列は `0` になります。`atoi` が扱えない範囲の整数文字列の結果には依存しないでください。空白だけの文字列も `atoi` の結果が 0 となり、明示的な無効指定です。

| 実行 device / 設定 | 旧 kernel を選ぶ条件 |
|---|---|
| HIP の gfx11 (`gcnArchName` が `gfx11` で始まる) | `DS4_DQ_OLD` の変換結果が `1` のときだけ。未設定・空文字・変換結果 0 は新 kernel。`DS4_DEFAULTS=026` はこの分岐に影響しない。 |
| その他の CUDA / HIP device | 明示値があればその値（0 は新、非ゼロは旧）。未設定または空文字なら `DS4_DEFAULTS` が厳密に `026`, `0.2.6`, `v0.2.6` のいずれかのとき旧、それ以外は新。 |

明示的な `DS4_DQ_OLD` が `DS4_DEFAULTS` より優先します。CLI 引数による上書きはありません。`DS4_DEFAULTS` の token 判定と結果は初回参照時に static cache されます（`src/dsv41/ds4_experts_rule.hpp:22-27`）。

## 有効になる条件

- chunked prompt の GEMM が GGUF 形式の行列を `gg::rows()` に渡し、対象の低 bit 型を `iq::dequant_rows()` が処理するときに選択が使われます。FP16 weight 再構成など別経路ではこの環境変数の分岐を通りません（`src/dsv41/ds4_model.cu:4174-4193`; `src/dsv41/ds4_gguf.cu:1393-1422`）。
- CUDA/HIP の DSV41 kernel 経路が対象です。HIP では現在 device の `gcnArchName` を見て gfx11 を特別扱いします。device property は device 番号ごとの static atomic cache に入り、device 番号は各呼び出しで取得します（`src/dsv41/ds4_iq.cu:1439-1455`）。CUDA build では gfx11 判定は常に false です。
- 旧 kernel は全ての量子化型で使えるわけではありません。`dq_old_ok<T>()` が true の型だけ旧 kernel を起動し、それ以外は環境変数が旧を要求しても新 kernel にします。この判定は codebook table がなく、shared staging のサイズが 704 bytes 以下で 16 bytes の倍数であることに基づきます（`src/dsv41/ds4_iq.cu:1358-1365,1465-1489`）。
- Metal では `gg::rows()` が Metal host dequantizer を先に使い、対応しない GGUF dense matrix は Metal 専用のエラー経路に入ります。CUDA/HIP dequantizer の `DS4_DQ_OLD` 判定は呼ばれません（`src/dsv41/ds4_gguf.cu:1393-1411`）。

## 実行時の詳細

`iq::dequant_rows()` の呼び出しごとに `DS4_DQ_OLD` を読み直し、HIP では device 判定後、その他の CUDA/HIP device では必要に応じて `defaults_026()` を参照します。したがってこの変数自体は関数内に cache されませんが、`DS4_DEFAULTS` の判定は初回参照後に変わりません。呼び出しごとの再読み取り以外に、プロセス実行中の環境変更方法や同期についての保証はコードから確認できません（`src/dsv41/ds4_iq.cu:1457-1463`）。

旧 kernel が選ばれたときは `dq_rows_kernel<T>`、それ以外は `dq_rows_kernel2<T>` を `strata_ds4_launch()` で起動します。`dequant_rows()` は null 入力、`k % 256 != 0`、`n <= 0`、未対応型なら false を返し、正常な型の起動後も `cudaGetLastError() == cudaSuccess` で成否を返します（`src/dsv41/ds4_iq.cu:1465-1492`）。呼び出し側 `gg::rows()` は false の場合 `stderr` に `ds4 gguf rows: a low-bit type not covered` を出し、内部エラーカウンタを増やします。選択値だけを知らせるログは見つかりません（`src/dsv41/ds4_gguf.cu:34-44,1409-1411`）。

旧 kernel の対象型には `IQ2_XXS`, `IQ2_XS`, `IQ2_S`, `IQ3_XXS`, `IQ3_S`, `IQ4_XS`, `IQ1_S`, `IQ1_M`, `Q4_K`, `Q5_K`, `Q6_K`, `Q2_K`, `Q3_K` が列挙されています。ただし上記の `dq_old_ok<T>()` 制約を満たさない型は実際には新 kernel を使います。入力型は `dequant_rows()` の switch にない場合 false になります（`src/dsv41/ds4_iq.cu:1475-1490`）。

## 根拠

- 直接読み取り、gfx11 条件、旧/新 kernel の選択: `src/dsv41/ds4_iq.cu:1439-1492`。
- gfx11 の device property cache と HIP 以外で常に false となる判定: `src/dsv41/ds4_iq.cu:1439-1455`。
- 旧 kernel の対象型制約と fallback: `src/dsv41/ds4_iq.cu:1358-1365,1465-1489`。
- `DS4_DEFAULTS` の厳密な token 判定と cache: `src/dsv41/ds4_experts_rule.hpp:22-27`。
- chunked prompt GEMM から GGUF rows 展開への呼び出し: `src/dsv41/ds4_model.cu:4168-4193`; rows の Metal/CUDA-HIP 分岐: `src/dsv41/ds4_gguf.cu:1393-1422`。
- 関連資料 `docs/release-notes-0.2.7.md:32-35` は `DS4_DEFAULTS=026` で dense dequantizer を含む既定を戻すことを説明しています。`docs/DETAILS.md` にこの個別切替の測定条件付き説明は確認できなかったため、コメント中の性能値は一般化して記載していません。
