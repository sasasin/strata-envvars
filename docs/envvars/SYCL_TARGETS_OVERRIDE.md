# `SYCL_TARGETS_OVERRIDE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

この変数は、`engine/src/inkling2/sycl/build_inkling_sycl.sh` を `fat` モードで実行したとき、既定の SYCL target 一覧の代わりに `-fsycl-targets=<値>` を `icpx` に渡すためのビルド時上書きです。Strata の実行時設定ではなく、ビルドされたプログラムの実行時に読み直される値でもありません。参照はこのスクリプトの 1 箇所だけで、アプリ本体・サーバー・CLI の実行時読み取りはありません（同ファイル:61-86）。

## 値と判定

スクリプトは `${SYCL_TARGETS_OVERRIDE:-}` を `[ -n ... ]` で判定します。未設定と空文字は同じ扱いで override なしです。空でない値は文字列として解釈・検証・分割せず、引用された 1 個の引数 `-fsycl-targets=<値>` にそのまま連結します。したがって `0`、`false`、空白だけの値も「設定あり」と判定され、内容の妥当性は Strata 側では判定されません（同ファイル:65-66）。

| `TARGET_MODE` | 未設定 / 空文字 | 非空の `SYCL_TARGETS_OVERRIDE` |
|---|---|---|
| `fat`（第2位置引数の既定値） | `ocloc ids bmg_g31` が成功すれば `spir64,intel_gpu_acm_g10,intel_gpu_bmg_g21,intel_gpu_bmg_g31`、それ以外は `spir64,intel_gpu_acm_g10,intel_gpu_bmg_g21` を使う | 値を `-fsycl-targets=` に連結して使う。例: `spir64,intel_gpu_acm_g10` はその文字列を付けて渡す。`0` や `false` も同様に渡す |
| `bmg` / `acm` / `jit` | この変数を参照せず、それぞれ `intel_gpu_bmg_g31,spir64` / `intel_gpu_acm_g10,spir64` / `spir64` を使う | この変数を参照せず、各モードの固定値を使う |

モードは第2位置引数で指定され、空または省略時は `fat` です。`fat` の自動選択では `ocloc` の存在と `ocloc ids bmg_g31` の終了状態だけを見ます。ターゲット値の大文字小文字、空白、書式、境界値を検査するコードはありません（同ファイル:9-10,63-80）。

## 有効になる条件

- `engine/src/inkling2/sycl/build_inkling_sycl.sh` を起動し、`TARGET_MODE` が `fat` の場合に限って参照されます。`bmg` / `acm` / `jit` では値は無視されます（同ファイル:63-80）。
- 同スクリプトからのビルド経路に限られます。Inkling SYCL の CMake 経路は環境変数ではなく CMake cache string `STRATA_SYCL_TARGETS` をコンパイル・リンク引数に使います（`engine/src/inkling2/sycl/CMakeLists.txt:17-25`）。
- リポジトリ全体の参照検索では、この変数を読む別箇所や同スクリプトを呼び出す別ファイルは見つかりませんでした。通常のアプリ実行、サーバーモード、モデル状態、その他の CLI 引数による実行時の効果は確認できません。

## 実行時の詳細

スクリプト起動時に shell parameter expansion で値を読み、ビルドフラグ配列を組み立てます。設定値を別の変数へ cache したり、ビルド後の子プロセスやリクエストへ転送したりはしません。組み立てた `SYCL_FLAGS` は最後の `icpx` 呼び出しに渡され、先行する C ソース・C++ ソースの個別コンパイルには渡されません（同ファイル:34-59,61-66,96-107）。

この値が不正でもスクリプト自身は内容検証や専用警告を行いません。最終 `icpx` 呼び出しが失敗した場合は `set -e` によりスクリプトがその場で終了し、後続の `ls` と生成物の `--version` 呼び出しには進みません。`TARGET_MODE` が未知の場合は `Unknown TARGET_MODE=<値>` を stderr に出して終了コード 1 で終了します（同ファイル:5,82-85,96-110）。

## ログと測定値

スクリプトは開始時に `[build_inkling_sycl] ICPX=<値> TARGET_MODE=<値> OUT_DIR=<値>` を出しますが、選択された target 一覧や `SYCL_TARGETS_OVERRIDE` の内容を示す Strata 独自ログはありません（同ファイル:17,61-86）。`ocloc ids bmg_g31` の標準出力・標準エラーは抑制されます（同ファイル:67）。ソース資料にこの変数による測定値はありません。

## 根拠

- `engine/src/inkling2/sycl/build_inkling_sycl.sh:9-17` — 出力先、モード既定値、起動ログ。
- `engine/src/inkling2/sycl/build_inkling_sycl.sh:61-86` — モード別の target 選択、override の判定と自動 fallback、未知モードの終了。
- `engine/src/inkling2/sycl/build_inkling_sycl.sh:96-110` — フラグを使うコンパイラ呼び出しと成功時の後続処理。
- `engine/src/inkling2/sycl/CMakeLists.txt:17-25` — CMake 経路が `STRATA_SYCL_TARGETS` を使うこと。
