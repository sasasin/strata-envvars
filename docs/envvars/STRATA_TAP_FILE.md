# `STRATA_TAP_FILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`Verifier` の検証 window で指定レイヤーの出力を記録する、開発・調査用のファイル出力フックです。値は真偽値ではなく出力先パスとして使われます。CUDA/HIP 側の `engine/src/core/verify.cpp` が `Verifier::init` で有効化し、各 window の行ごとに位置・入力 token・tap の FP32 値を書きます。通常の生成結果を選ぶ設定ではありません（`engine/src/core/verify.cpp:1063-1065, 918-934`）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `engine/src/core/verify.cpp` の非 Metal 経路 | 出力しない | 空でない文字列をそのままファイルパスとして開く | 空文字は unset と同じ。パス以外の値検証はない |
| `STRATA_GPU_METAL` 経路 | 出力しない | 該当なし | 値に関係なく環境変数を読む前に Metal window の初期化から戻る |
| SYCL (`engine/sycl/src/core/verify.cpp`) | 出力しない | 該当なし | この名前を読む処理がない |

文字列の数値変換や大小文字判定はありません。非空値は `fopen(path, "wb")` に渡され、既存ファイルがあれば書き込み用に開き直します。相対パスの基準を Strata が変更する処理もありません。開けなければ `verify: cannot write STRATA_TAP_FILE <path>` をエラーとして返します（`engine/src/core/verify.cpp:1064-1065, 1121-1124`）。

## 有効になる条件

- `Verifier::init` が実行される検証経路であること。通常生成では speculative loop の verifier を初期化する箇所があり、serve でも verifier を初期化します。環境変数単独で検証 window を開始するものではありません（`engine/src/program/generate.cpp:24459-24505, 13489-13501`）。
- `STRATA_GPU_METAL` のビルドではないこと。Metal 分岐は `window_init` と任意の `set_taps` 処理後に戻るため、`STRATA_TAP_FILE` の読み取り・ファイル出力には到達しません（`engine/src/core/verify.cpp:978-993, 1063-1065`）。
- layer split では drafter がすでに `set_taps` で tap を要求していると、先頭 stage は `strata: STRATA_TAP_FILE ignored: the drafter owns this layer split's taps` を出し、ファイル出力を無効にします。drafter の要求がない場合は先頭 stage が全 stage の tap を gather してファイルに出します（`engine/src/core/verify.cpp:1066-1093, 1131-1140`）。
- batch window の graph capture 中は tap の記録とファイル書き込みを行いません。tap capture 自体も `tap_batch_` が有効でない限り batch では抑止され、ファイル書き込み箇所は `!batch_rec_` を条件にしています（`engine/src/core/verify.cpp:2969, 3144, 4147-4148, 4243`）。
- レイヤー選択は `STRATA_TAP_LAYERS` に従います。未設定または空文字なら `5,15,25,35,45`。各 comma 区切り要素を `atoi` で変換し、`0 <= layer < n_layers - 1` の値だけを採用します。整数全体の妥当性検査はなく、`atoi` が読む先頭の整数部分を使います。通常の単一 verifier 経路では並べ替え・重複除去をしません。layer split の research dump 経路では sort と重複除去をします。layer split で選択結果が空なら `STRATA_TAP_FILE` を無視し、先頭 stage は `strata: STRATA_TAP_FILE ignored: STRATA_TAP_LAYERS names no layer in 0..%d` を出します。単一 verifier 経路では選択結果が空だと tap buffer の確保エラーで初期化に失敗します（`engine/src/core/verify.cpp:1073-1088, 1099-1119`）。

## 実行時の詳細

パスは verifier 初期化時に `std::getenv` で読み、空文字を無効化した後、非空なら tap buffer と scratch buffer を確保してファイルを `wb` で開きます。環境変数を static cache する処理はなく、各 verifier の初期化時に評価します。したがって初期化後の環境変更は、その verifier には反映されません（`engine/src/core/verify.cpp:1063-1065, 1111-1129`）。

ファイル先頭には4個の int32（magic `STAP`、version `1`、`n_embd`、tap 数）と layer ID 一覧を書きます。続いて各非 batch window の各 row について、int32 の position、int32 の入力 token、tap layer 順の `n_taps × n_embd` 個の float を追記し、window ごとに `fflush` します。position は `pos0 + row` を int32 に変換します。書き込みの戻り値は検査していません（`engine/src/core/verify.cpp:918-934, 1121-1128`）。

通常経路では `record_window` が tap device buffer を mapped host buffer にコピーし、window 完了後 `tap_write` がファイルへ出力します。layer split では全 stage の window 完了後、tap を host に gather してから出力します。gather に失敗すると stderr にエラーを出してその window の出力を飛ばします（`engine/src/core/verify.cpp:3144, 4145-4148, 4185-4190, 4242-4243, 923-934`）。

serve の `--pipeline-windows` は各 parity 用に別の verifier を初期化します。どちらも同じ非空 `STRATA_TAP_FILE` を読むため、それぞれが同じパスを `wb` で開きます。append や複数 verifier 間の調停は実装されていないので、この組み合わせではファイルが再切り詰めされ、並行した window 出力が同一ファイルに書かれる可能性があります（`engine/src/program/generate.cpp:13263-13270, 13447-13452, 13481-13483, 13496-13501; engine/src/core/verify.cpp:1121-1127`）。

## ログと測定値

- 有効時: `strata: STRATA_TAP_FILE <path>: <n> taps of <n_embd> floats per row`。layer split では末尾に `(layer split: gathered from every stage)` が付きます（`engine/src/core/verify.cpp:1127, 1140`）。
- 出力先を開けない場合、`Verifier::init` は失敗し、generate 側は `strata generate: verify: cannot write STRATA_TAP_FILE <path>`、serve 側は `strata serve: verify: cannot write STRATA_TAP_FILE <path>` の形で stderr に出します（`engine/src/core/verify.cpp:1121-1124, engine/src/program/generate.cpp:13496-13501, 24503-24505`）。
- buffer 確保失敗時は `verify: the DFlash2 tap buffers could not be allocated` を返します。layer split の host gather 失敗時は `strata: STRATA_TAP_FILE (split): <reason>` を stderr に出します（`engine/src/core/verify.cpp:1115-1119, 923-926`）。
- Strata の資料に、この変数の測定値はありません。

## 根拠

- `engine/src/core/verify.cpp:956-993, 1063-1140` — verifier 初期化、値の判定、条件分岐、buffer とファイル作成、ログ。
- `engine/src/core/verify.cpp:918-934, 3144, 4145-4148, 4185-4190, 4242-4243` — row 形式、window ごとのコピー・書き込み、layer split と batch の扱い。
- `engine/src/program/generate.cpp:13489-13501, 24459-24505` — serve と generate の verifier 初期化・エラー伝播。
- `engine/sycl/src/core/verify.cpp:985-998` — この SYCL verifier 初期化箇所に `STRATA_TAP_FILE` の読み取りがないこと。
