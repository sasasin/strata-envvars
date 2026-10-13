# `STRATA_PREFILL_DUMP_R`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

プロンプト prefill の各チャンクが最後の layer stage を終えたとき、最終 residual `R` のうち絶対位置が64の倍数となる行を、指定パスへバイナリ出力します。ソースコメントでは A/B 品質確認用の debug dump とされています。通常の生成設定を切り替える変数ではなく、ファイル書き出しと GPU/queue 同期を追加する診断用フックです。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | dump 処理を行わない。 |
| 設定あり（空文字を含む） | 値をそのままファイルパスとして `fopen` に渡す。文字列の parse、真偽値判定、空白除去はない。 |
| パスを開ける | 出力する。各 `run_impl` 呼び出しの最初のチャンク（`c0 == 0`）は `wb` で新規作成または切り詰め、後続チャンクは `ab` で追記する。 |
| パスを開けない | `fopen` が失敗し、dump 部分は何も書かずに続行する。専用の警告・エラー処理はない。 |

空文字も「設定あり」として同期処理までは進みますが、通常は空のパスを開けず、書き込みは行われません。

各サンプル行は、まずネイティブ表現の `int64_t` 位置 `pos`、続いて `D` 個のネイティブ表現 `float` residual 値を順に書きます。ファイルにヘッダーや次元情報は付かず、エンディアンや浮動小数点形式の変換もありません。書き込み戻り値は確認されません。

## 有効になる条件

- CUDA 実装（`src/prefill/prefill.cpp`）または SYCL 実装（`sycl/src/prefill/prefill.cpp`）の prefill 経路で評価されます。
- 現在の `run_impl` が layer split の最終 stage であることが必要です。後続 stage (`next_ != nullptr`) がある場合は、先に hand-off して `continue` するため、この stage では dump しません。最終 stage 側で同じ処理が実行されます。
- 対象チャンクの処理後、`m.R` に残っている最終 residual を読みます。絶対位置 `p0 + t` が64の倍数となる行だけが対象です。先頭の対象オフセットは `(64 - p0 % 64) % 64` です。
- `STRATA_PREFILL_DUMP_R_ALL` は別の変数で、全位置を BF16 で書き出す別処理です。両方を設定した場合は各 dump 処理が独立して実行されます。

## 実行時の詳細

変数はチャンクごとの書き出し箇所で `std::getenv` により読み直され、static cache されません。したがってコード上はチャンクごとにパスを再取得します。各 `run_impl` の最初のチャンクでファイルを切り詰めるため、後続チャンクは同じ実行内で追記されます。次の `run_impl` 呼び出しも `c0 == 0` から始まり、同じパスなら既存ファイルを切り詰めます。

dump が有効な場合、CUDA は `cudaStreamSynchronize(m.cs)`、SYCL は `m.cs->wait()` を実行してから residual を host memory へコピーします。該当行がないチャンクでもこの同期とファイル open/close は行います。ファイル open 失敗や `fwrite` 失敗のログはありません。

## 根拠

- CUDA のチャンク loop、`c0` と絶対位置 `p0` の設定: `src/prefill/prefill.cpp:2139-2143`。
- CUDA での最終 stage 判定、同期、サンプル選択、`int64_t` と `float` の出力、ファイル mode: `src/prefill/prefill.cpp:4065-4083`。
- SYCL の同等処理: `sycl/src/prefill/prefill.cpp:4452-4478`。
- `STRATA_PREFILL_DUMP_R_ALL` との別処理: `src/prefill/prefill.cpp:4085-4106`, `sycl/src/prefill/prefill.cpp:4480-4502`。
- `docs/DETAILS.md` と関連設計資料には、この変数の利用説明や測定値を確認できませんでした。
