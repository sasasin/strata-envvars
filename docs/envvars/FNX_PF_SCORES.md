# `FNX_PF_SCORES`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

この名前は Flash-Next の prompt scoring を制御する設定としては使われません。Flash-Next の `Engine` は、27B 向けの環境変数群の一つとして `FNX_PF_SCORES` の設定有無を確認し、値が設定されていれば「Flash-Next にはその設定対象がない」としてエンジン構築を拒否します。スコア値の読み取り、変換、転送はありません。

## 値と判定

| 状態 | 判定と結果 |
|---|---|
| 未設定 | この拒否チェックを通過する。 |
| 設定あり（空文字を含む） | `std::getenv(k)` が null でないため拒否する。値の内容は調べず、`0`、`1`、その他の文字列も同じ扱い。 |

`FNX_PF_SCORES` 専用の既定値、数値境界、無効値 fallback はありません。CLI 引数による上書きもありません。拒否チェックは `Engine` の各構築時に環境を確認し、結果を static cache しません。

## 有効になる条件

チェックは `src/split/src/engine.cu` の `Engine` コンストラクターにあります。したがって、Strata の通常エンジン全般に効く変数ではなく、split エンジン実装を組み込んだ実行経路に限られます。split ターゲットは `STRATA_BUILD_SPLIT` が既定 OFF で、CMake は Linux CUDA または HIP の構成を対象にしています。生成される `strata-split-N` と、同じ Engine ソースを使う `split_fnx_run` にチェックが含まれます。各ターゲットは `FNX_27B=0` でビルドされます。

他の prompt-prefill 変数や CLI 指定がこの判定を解除する経路はありません。`FNX_PF_SCORES` が存在する場合、prefill 等の Engine 設定に進む前に拒否されます。

## 実行時の詳細

コンストラクターは `FNX_PF_SCORES` を他の 27B 向け名前とともにループで `getenv(k)` に渡します。非 null なら `std::runtime_error` を投げ、例外文は `FNX_PF_SCORES is the 27B's: Flash-Next has nothing it sets` になります。エンジンの使用を続けず、スコアを読む処理や変更は行いません。

`strata-split-N` の起動時にこの例外が起きると、`sfnx` は stdout に `ERR <例外文>`、stderr に `sfnx: failed: <例外文>` を出し、終了コード 1 で終了します。値の書式によってログや終了経路は変わりません。

## 根拠

- `src/split/src/engine.cu:31-36` — `Engine` 構築時に拒否リストを走査。`FNX_PF_SCORES` の完全一致参照はこの一箇所で、`getenv` の非 null 判定だけを行い、27B の設定とする例外を投げます。
- `src/split/tools/sfnx.cpp:1050-1061` — モデルと MTP を作った後に `Engine` を構築し、例外時は `fail()` へ。
- `src/split/tools/sfnx.cpp:1027-1035` — `fail()` が stdout/stderr に理由を出し `_Exit(1)` する。
- `src/split/tools/fnx_run.cpp:978-989` — 同梱の `fnx_run` コマンドも同じ Engine を構築します（`lab_mode` は `lab_check` に渡り、その中にも Engine 構築箇所があります: `src/split/tools/fnx_run.cpp:437-448`）。
- `CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-7,92-117,153-165` — split は opt-in で、Linux CUDA/HIP のエンジンと同梱ドライバーに同じ実装を組み込み、`FNX_27B=0` を定義します。
