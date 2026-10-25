# `STRATA_HIPBLASLT_TUNING`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

HIP 対応の prefill GEMM で使う hipBLASLt チューニング表のパスです。表には GPU アーキテクチャと hipBLASLt バージョンに対応する解法 ID が記録され、表を読み込めると BF16/FP16 の dense GEMM で該当 ID の解法を試します。変数自体は値を数値や真偽値として解釈しません。CUDA 専用ビルドではこの変数を読むコードは有効になりません。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | hipBLASLt state を作らず、既存の hipBLAS GEMM 経路を使う |
| 空文字 | 未設定と同様に state を作らない |
| 非空文字列 | 文字列全体をファイルパスとして開き、表を読み込む |
| 開けない・形式不正・対象外 | stderr に理由と `using hipBLASEx` を出し、state を作らず通常経路へ戻る |

数値変換、先頭文字判定、空白除去、相対パスの特別扱いはありません。パスはプロセスの作業ディレクトリを基準にした通常のファイルオープンに渡されます。表は空行と `#` で始まる行を無視します。先頭の有効行は `STRATA_HIPBLASLT_TUNING_V1 <arch> <version>` 形式で余分な項目を許さず、後続行は `f16|bf16 N K ldy T_bucket solution_id` の6項目を要求します。N/K/T_bucket は正、`ldy >= N`、solution ID は非負で、重複する shape key は拒否されます。header だけの表はロード自体は成功しますが、形状に一致する行がないため GEMM ごとにfallbackします。

## 有効になる条件

- `__HIPCC__` と `STRATA_HIPBLASLT_AVAILABLE` が定義されたビルドでのみ state 作成・呼び出しがコンパイルされます。通常の CUDA では利用されません。SYCL ソースにも同じ HIP 条件付き実装があります。
- 表の header の hipBLASLt version は実行時に取得したバージョンと一致する必要があります。architecture は完全一致のほか、gfx1200/gfx1201 同士、gfx1100/gfx1101/gfx1102 同士を同一 family として受け入れます。
- header が一致しても、呼び出し形状（dtype、N、K、ldy）に表の行が必要です。T は最も近い `T_bucket` を使い、距離が同じなら小さい bucket を選びます。解法 ID の取得・実形状でのサポート確認・workspace 量の確認にも通らなければその GEMM は hipBLASLt を使いません。
- `STRATA_WMMA_GEMM` など別の GEMM 経路が先に処理した場合や、HIP の FP16 prompt 入力経路が BF16 GEMM を変換して処理した場合、この表を使う hipBLASLt 呼び出しには到達しません。

## 実行時の詳細

環境変数は `Gemm::init()` または `Gemm::init_external()` が呼ぶ `create_hipblaslt_state()` ごとに読みます。値の判定結果をプロセス全体の static cache には保存しませんが、作成済みの GEMM state は環境変数を再読せず、表の行と shape ごとの解法判定を保持します。したがって既存の state の後で環境変数を変更しても、その state には反映されません。新しい state の初期化時には再読されます。

表の読込に成功すると stderr に `prefill gemm: hipBLASLt tuning enabled (<行数> rows, <arch>, version <version>)` と出ます。BF16/FP16 GEMM は対応する候補を確認し、対応・workspace 条件を満たせば hipBLASLt を呼びます。形状行や利用可能な解法がない場合、通常は hipBLASEx 経路へ戻ります。`STRATA_HIPBLASLT_VERBOSE` が設定されている場合は fallback 詳細も出力します。hipBLASLt の起動自体が失敗した場合、beta が 0 ならその shape を無効化してfallbackしますが、beta が 0 以外なら終了します。

setup.py は、現在のカード architecture とインストール済み hipBLASLt version の両方に合う `tools/hip/<arch>-hipblaslt-<version>.txt` がある場合、生成する実行設定の `env` にこのパスを設定します。合う表がなければ setup は警告し、実行設定に追加しません。serve は実行設定の env を親プロセス環境へ上書きしてエンジン子プロセスに渡します。

## 根拠

- 読み取り、空値判定、runtime device/version の照会、表ロードと成功ログ: `src/prefill/gemm.cu:186-220`。同等の HIP 条件付き実装: `sycl/src/prefill/gemm.dp.cpp:193-227`。
- 表の header/row validation、architecture family と version の照合、最近傍 bucket 選択: `src/prefill/hipblaslt_tuning.hpp:24-123`。
- GEMM state 作成箇所と、解法・workspace の検査、fallback、hipBLASLt 呼び出し: `src/prefill/gemm.cu:394-450,223-282,293-351,571-607,675-705`。通常経路への復帰箇所は `src/prefill/gemm.cu:667-672` および `src/prefill/gemm.cu:848-869`。
- setup の表選択と実行設定への追加: `setup.py:2613-2629,5690-5700`。実行設定 env の子プロセスへの適用: `serve/server.py:2554-2571`。
- 文書との照合: `docs/AMD_HIP.md:42-45,530-541` も、カード architecture と hipBLASLt version の一致した表のみ使用し、それ以外は通常 hipBLAS 経路を使うと説明しています。ソース実装と整合します。
