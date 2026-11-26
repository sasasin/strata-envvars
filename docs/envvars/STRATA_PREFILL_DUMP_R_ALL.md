# `STRATA_PREFILL_DUMP_R_ALL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

chunk-major prefill が各 chunk の最終 multi-stream residual `R` を GPU から host にコピーし、BF16 の生データとして指定パスへ出力する診断・データ収集用フックです。CUDA/HIP 実装と実験的 SYCL 実装にあります。全 token 位置を出力し、通常の生成結果や residual の計算自体は変更しません。データには位置番号や shape header が含まれず、呼び出しを区切る情報もありません。`engine/src/prefill/prefill.cpp:7858-7882`、`engine/sycl/src/prefill/prefill.cpp:5587-5609`。

## 値と判定

| 条件（backend） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP chunk-major (`engine/src`) | ダンプしない | `path.bin`、`0`、`true`、`0anything`（いずれも文字列全体をパスとして使う） | 有効値の形式検査はない。空文字 `""` も設定済みとして分岐するが、空パスを `fopen` できずファイル出力されない |
| SYCL chunk-major (`engine/sycl/src`) | ダンプしない | `path.bin`、`0`、`true`、`0anything`（文字列全体をパスとして使う） | 有効値の形式検査はない。空文字 `""` も設定済みとして分岐するが、空パスを `fopen` できずファイル出力されない |

どちらも `std::getenv` の null 判定だけで、文字列比較、数値変換、空白除去、大文字小文字変換はありません。値が存在すればパスとして使います。開けないパスでは `fopen` が失敗し、ファイル出力は行われませんが、この分岐は診断ログやエラーを出しません。CUDA/HIP は `fopen` 成功後の `fwrite` / `fclose` 結果も確認しません。同じ実行経路で chunk ごとに環境を読み直すため cache はなく、実行中に環境を変更すれば後続 chunk の判定に反映され得ます。`engine/src/prefill/prefill.cpp:7858-7882`、`engine/sycl/src/prefill/prefill.cpp:5587-5609`。

## 有効になる条件

- CUDA/HIP: `Prefill::run` が layer-major prefill を選ばず `run_impl` に進み、chunk の最終 residual を処理する必要があります。layer-major を試す経路では、この変数が設定されていると `lm_prepare` が `"a routing or row debug dump"` を理由に拒否し、通常の chunk-major 経路に戻ります。ただし `lm_prepare` の先行条件（短い prompt など）が先に拒否した場合は、この理由判定には到達しません。`engine/src/prefill/prefill.cpp:8205-8209, 8235-8238, 9657-9705`。
- SYCL: `run_impl` の最終 stage が各 chunk を完了する経路で出力します。`engine/sycl/src/prefill/prefill.cpp:5572-5610`。
- SYCL には別に、この変数の設定有無を `run_expert_window` の fast-path 条件から除外する判定があります。現行 checkout ではこの関数の呼び出し箇所を確認できなかったため、この guard が実行時に fast path を変えるとは断定しません。`engine/sycl/src/prefill/prefill.cpp:5838-5848`。
- 出力パスを渡す CLI 引数や、他の環境変数による path の上書きはありません。少なくとも直接参照箇所では、モデル geometry から得る `D`（`hc * n_embd`）の全 residual 列が対象です。ファイルには全 chunk・全 request 分が区切りなく連結されます。`engine/src/prefill/prefill.cpp:7858-7882`、`engine/sycl/src/prefill/prefill.cpp:5587-5609`。

## 実行時の詳細

chunk-major の最終 stage は device residual `R` を host にコピーする前に CUDA stream または SYCL queue を同期し、最大 512 行ずつ処理します。各行の `D` 個の float を BF16 に丸め、`fopen(path, "ab")` で追記します。1 token あたり `D * 2` byte で、行順は chunk 内の位置順です。ファイルは初回も切り詰めず、既存ファイルがあれば末尾へ追記します。位置番号、shape、request 境界は保存されません。`engine/src/prefill/prefill.cpp:7858-7882`、`engine/sycl/src/prefill/prefill.cpp:5587-5609`。

CUDA/HIP 版は NaN を quiet NaN にしてから BF16 化します。SYCL 版は float の bit pattern に round-to-nearest-even の加算をして上位 16 bit を保存し、NaN 専用処理はありません。どちらも出力値は BF16 相当ですが、NaN の扱いには実装差があります。`engine/src/prefill/prefill.cpp:7868-7879`、`engine/sycl/src/prefill/prefill.cpp:5597-5606`。

この名前は、CUDA/HIP の layer-major prefill が持たない row dump hook としても設定有無を確認します。layer-major prefill の選択自体は別設定やモデル・prompt 条件にも依存し、通常経路では `strata prefill: layer-major off for this prompt: a routing or row debug dump` が理由ごとに一度出ます（デフォルト選択の短い prompt などは抑制されます）。16 回連続で長い prompt が layer-major を使えない場合は継続ログも出ます。`engine/src/prefill/prefill.cpp:8205-8209, 9694-9702`。

## ログと測定値

ダンプ成功を知らせる専用ログはありません。出力先を開けない場合も明示的なログや Strata エラーにはならず、このフックによる終了もしません。GPU 同期・コピー呼び出しの戻り値もダンプ部分ではエラー判定に使われていません（後続処理で別途失敗する可能性はあります）。SYCL の同期・コピーが例外を投げた場合は `run_impl` を囲む `sycl::exception` handler が `what()` と source 行を stderr に出し、`exit(1)` します。`engine/src/prefill/prefill.cpp:7861-7882`、`engine/sycl/src/prefill/prefill.cpp:5589-5609, 5792-5796`。

## 根拠

- `engine/src/prefill/prefill.cpp:7858-7882` — CUDA/HIP chunk-major dump の読み取り、同期、出力形式。
- `engine/src/prefill/prefill.cpp:8205-8209` — layer-major prepare における debug dump の拒否。
- `engine/src/prefill/prefill.cpp:9657-9705` — layer-major の試行、理由ログ、chunk-major `run_impl` への fallback。
- `engine/sycl/src/prefill/prefill.cpp:5587-5609` — SYCL chunk-major dump。
- `engine/sycl/src/prefill/prefill.cpp:5838-5848` — SYCL expert window fast-path 条件からの除外。
- `engine/sycl/src/prefill/prefill.cpp:5792-5796` — SYCL exception の stderr 出力と終了。
- `engine/CMakeLists.txt:23-32`、`engine/cmake/strata_gpu_engine.cmake:482-488`、`engine/sycl/CMakeLists.txt:303-308` — CUDA/HIP 共通 prefill と独立した SYCL prefill の build 定義。
