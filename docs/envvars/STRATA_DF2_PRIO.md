# `STRATA_DF2_PRIO`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`Dflash2Drafter::make_streams()` が作る DFlash2 用の `cs_` と `cs2_` を高優先度で作成するかを選ぶ。CUDA build では未設定時に高優先度、HIP build では未設定時に通常優先度となり、この変数で既定を反転できる。対象はこの drafter の2ストリームだけで、エンジンの他のストリームの優先度は変えない。処理は `engine/src/core/dflash2.cpp:271-285`、CUDA/HIP 専用の DFlash2 実装は `engine/cmake/strata_gpu_engine.cmake:8-13` に示されている（Metal と SYCL は同ファイルのコメントどおり DFlash2 を含まない）。

## 値と判定

`std::getenv` の戻り値を `e[0]` だけで調べる。文字列全体の数値・真偽値 parse、空白除去、大文字小文字変換はない。未設定と空文字の扱いも backend ごとに異なる (`engine/src/core/dflash2.cpp:274-284`)。

| build 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_USE_HIP` 定義あり | 通常優先度 | 先頭が `1`（`1`, `10`, `1anything`） | 先頭が `0` または空文字。`true`, `-1`, ` 1` も先頭が `1` ではないため無効 |
| `STRATA_USE_HIP` 定義なし（CUDA） | 高優先度 | 未設定、空文字、先頭が `0` 以外（`1`, `true`, `-1`, ` 1` など） | 先頭が `0`（`0`, `00`, `0anything`） |

どちらも先頭文字以降は判定に影響しない。たとえば HIP の `1anything` は有効、CUDA の `0anything` は無効となる。CLI 引数や設定ファイルとの優先順位を扱うコードはない。

## 有効になる条件

- CUDA または HIP build で DFlash2 が組み込まれていること。Metal / SYCL build にはこの DFlash2 実装がない (`engine/cmake/strata_gpu_engine.cmake:8-13`)。
- 実行経路が DFlash2 drafter の初期化まで進むこと。通常の生成経路では `--draft dflash2` の選択後、`df2.load(...)` がストリームを作る (`engine/src/program/generate.cpp:8266-8275`; `engine/src/core/dflash2.cpp:267-268`)。DFlash2 を使わない通常生成では参照されない。
- DFlash2 を有効にできる他の条件も必要。たとえば同経路では native pack、`--draft-model PACK`、`--pipeline-windows 0` などを確認し、条件を満たさない場合は MTP fallback または `--draft-fallback none` による起動失敗となる (`engine/src/program/generate.cpp:8267-8272, 8310-8326`)。
- CUDA build では明示的な先頭 `0` が通常優先度を選び、HIP build では明示的な先頭 `1` が高優先度を選ぶ。どちらも優先度範囲 API が返す高優先度値（または `0`）を作成関数に渡す (`engine/src/core/dflash2.cpp:274-284`)。
- サーバーモードでも、DFlash2 が選択されて drafter が初期化される場合に同じ判定が使われる。サーバーでは verifier が tap を保持できないなどの条件で MTP fallback になることがある (`engine/src/program/generate.cpp:13584-13606`)。

## 実行時の詳細

`make_streams()` の初回実行時に関数内 `static const bool hi_prio` の初期化 lambda が環境を読み、その後の呼び出しでは保存値を使う。したがってプロセス実行中に環境を書き換えても、この値の再評価はない。`load()` の stream setup と、slot 用 `clone_alloc()` のいずれも `make_streams()` を通る (`engine/src/core/dflash2.cpp:267-268, 658-667`)。分岐した優先度で `cs_` と `cs2_` を `cudaStreamCreateWithPriority` / `hipStreamCreateWithPriority` に渡し、失敗時は `err = "dflash2: stream"` として `false` を返す (`engine/src/core/dflash2.cpp:278-287`)。

生成経路では load 失敗時に、MTP が利用可能なら DFlash2 が起動しなかった理由を stderr に出して MTP に切り替え、fallback なしなら理由を含む stderr を出して終了コード 1 で起動を終える (`engine/src/program/generate.cpp:8310-8324`)。優先度取得 API の失敗自体はここで検査されず、その戻り値による Strata のログもない。ストリーム作成失敗も `dflash2: stream` の一般的な DFlash2 起動失敗として上記経路に渡る。

## ログと測定値

`STRATA_DF2_PRIO` の値や選択された優先度を直接表示するログはない。ストリーム作成が失敗した場合はエラー文字列 `dflash2: stream` が上位へ渡る (`engine/src/core/dflash2.cpp:283-287`)。ソース内コメントは高優先度ストリームの意図を「verifier の async commit がカード上で動く間、draft round がそれの後ろに並ばないようにする」と記すが、この調査では性能差を測定していない (`engine/src/core/dflash2.cpp:272-273`)。

## 根拠

- `engine/src/core/dflash2.cpp:271-302` — backend ごとの値判定、優先度範囲取得、二つのストリーム作成、失敗文字列。
- `engine/src/core/dflash2.cpp:187-191, 267-268, 658-667` — drafter の load / clone と stream setup の呼び出し。
- `engine/cmake/strata_gpu_engine.cmake:8-13` — CUDA/HIP 条件と DFlash2 を含まない backend。
- `engine/src/program/generate.cpp:8266-8275, 8310-8326` — 通常生成での利用条件、失敗時の fallback / 終了経路。
- `engine/src/program/generate.cpp:13584-13613` — サーバーモードでの DFlash2 利用と bind / prepare 失敗時の fallback。
