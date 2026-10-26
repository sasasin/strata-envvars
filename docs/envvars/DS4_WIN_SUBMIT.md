# `DS4_WIN_SUBMIT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

DeepSeek-V4.1（DS4）エンジンの Windows 経路で、CUDA/HIP stream に積んだ処理をホストから `cudaStreamQuery()` で問い合わせ、待機せずに submit するかを切り替えます。実装コメントでは WDDM が host wait/query まで queued work の submit を遅らせるケースに対する処置とされています。対象は専用 `strata-dsv41` エンジンで、通常の `strata` ターゲットには含まれません。

## 値と判定

Windows では `std::getenv()` の結果を `std::atoi()` に渡し、変換結果が 0 以外なら有効です。文字列全体の厳密な数値検査はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 無効（`atoi` が 0 を返す） |
| `0`, `00`, `+0`, `-0` | 無効 |
| `1`, `-1`, `2` | 有効 |
| 数字の後ろに文字がある値（例: `1abc`） | 数字部分の変換値で判定。例では有効 |
| 数字に変換できない値（例: `true`, `abc`, 空白のみ） | 無効（変換結果 0） |

先頭空白と符号は `atoi` の規則に従います。範囲外の数値文字列の挙動は C ライブラリの `atoi` の仕様上ここでは規定しません。非 Windows では環境変数を読み取らず、この関数は何もしません。

## 有効になる条件

`src/dsv41/ds4_kernels.cu` を含む `strata-dsv41` がビルドされて実行されることが必要です。CMake では `STRATA_BUILD_DSV41` は既定 OFF です。関数本体は `_WIN32` のときだけ環境変数を判定するため、Linux/macOS 上の DS4 経路では値にかかわらず無効です。Windows の CUDA/HIP 経路が対象です。

## 実行時の詳細

判定は `win_submit()` 内の `static const bool` で初回呼び出し時に一度だけ行われます。その後プロセス内で環境を変更しても再評価しません。有効時は `cudaStreamQuery(s)` を呼び、その戻り値を捨てて続けて `cudaGetLastError()` も呼びます。関数内にログ出力や戻り値による失敗処理はありません。無効時にはどちらも呼びません。

`win_submit()` は、device-to-host-mapped hand-off の `xfer_put()` が kernel を launch した後、受信側への acknowledgement を設定する `set_flag()` の後、および DS4 flow の DMA を積んだ区間の終端で呼ばれます。flow の終端処理は DMA 件数が増えた場合に実行されます。実装コメントは、最初の hand-off で相手側が未 submit の flag を spin wait して停止した問題と、次の put 前に acknowledgement を待つ経路を挙げています。

## 根拠

- `src/dsv41/ds4_kernels.cu:2170-2187,2199-2204` — hand-off kernel launch、環境変数判定、query 呼び出しと flag 設定後の submit。
- `src/dsv41/ds4_kernels.cuh:276-294` — host-mapped hand-off の説明と Windows 用 `win_submit` 宣言。
- `src/dsv41/ds4_model.cu:3240-3245,3498-3505` — DS4 flow の `kick` と DMA を積んだときの終端 submit。
- `CMakeLists.txt:797-811` — 独立した `strata-dsv41` ターゲットとビルド option（既定 OFF）。
- `docs/DETAILS.md` — `DS4_WIN_SUBMIT` の個別説明は見つかりませんでした。
