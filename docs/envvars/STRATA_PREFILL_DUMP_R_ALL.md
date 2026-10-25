# `STRATA_PREFILL_DUMP_R_ALL`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

プロンプト prefill の各 token 位置について、最終 multi-stream residual `R` を BF16 に丸め、指定ファイルへ追記します。コードコメントでは draft-layer distillation data 用の opt-in フックとされています。通常の生成結果や prefill の計算を切り替える設定ではなく、追加の同期・device-to-host copy・ファイル書き込みを行う調査用出力です。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | 出力処理を行わない |
| 空文字を含む任意の設定値 | 設定値をファイルパスとして `fopen(path, "ab")` に渡す。文字列比較や数値変換はしない |
| パスを開けない値 | `fopen` が失敗し、出力を黙ってスキップする |

値は `getenv` で各 chunk の出力箇所に到達した時点で読みます。`static` cache はありません。したがって、コード上は後続 chunk で環境値を再取得します。

## 有効になる条件

- CUDA 実装（`src/prefill/prefill.cpp`）または SYCL 実装（`sycl/src/prefill/prefill.cpp`）の prefill 経路を通ること。
- layer-split prefill では `next_ == nullptr` の最終 stage のみがこの書き出し箇所に到達します。中間 stage は後続 stage に hand-off して `continue` するため、この箇所では出力しません。
- Metal は `Prefill::run()` から `metal_engine::prompt_run()` に分岐して `run_impl()` を呼ばないため、この環境変数の読み取り箇所を通りません。

通常の prefill 呼び出し、プロンプト chunk 分割、server/CLI のどれかに限定する判定は、この変数の実装箇所にはありません。各 chunk の終端 stage で値が設定されていれば出力します。

## 実行時の詳細

`m.R` は `T` 行、各 `D` 個の float を持つ最終 residual バッファです（このソースでは `D = N * HC`）。環境変数が設定されていると、まず CUDA stream または SYCL queue を同期し、`m.R` を最大 512 行ずつ host にコピーします。各 float の IEEE 754 bit pattern `u` に `0x7fff + ((u >> 16) & 1)` を加えた後、上位 16 bit を保存しており、BF16 の round-to-nearest-even への丸めです。

出力は token 位置順に並ぶ raw な `uint16_t`（BF16）の連続列です。ファイルにはヘッダー、位置番号、chunk/request 境界は書きません。各 chunk で `fopen(path, "ab")` を使うため、既存ファイルの末尾へ追記し、複数 chunk・複数 request のデータも同じファイルに連結されます。固定寸法のこの実装では各行 10,240 BF16 値（20,480 byte）です。

ファイルを開けない場合の警告・エラー設定はありません。`fwrite` や residual copy の戻り値もこの箇所では検査せず、ログ出力もありません。`STRATA_PREFILL_DUMP_R` は別の出力経路で、64 token ごとに位置番号と F32 residual を別形式で書きます。

## 根拠

- `src/prefill/prefill.cpp:4180-4214`: CUDA の `STRATA_PREFILL_DUMP_R_ALL` 読み取り、同期、最大 512 行単位の copy、BF16 丸め、追記。
- `sycl/src/prefill/prefill.cpp:4463-4500`: SYCL の対応実装。形式と追記動作は CUDA と同じ。
- `src/prefill/prefill.cpp:4169-4179, 4180-4193`: 中間 layer-split stage の hand-off と最終 stage 側の出力箇所。
- `src/prefill/prefill.cpp:4338-4354`: Metal 経路は `prompt_run()` に分岐し、通常経路の `run_impl()` より前に戻る。
- `src/prefill/prefill.cpp:118`: `N = 2560`, `HC = 4`, `D = N * HC` の寸法定義。
- `docs/DETAILS.md` および他の設計資料に、この変数の説明や出力形式・測定値の記載は見つかりませんでした。
