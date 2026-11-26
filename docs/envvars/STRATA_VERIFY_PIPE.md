# `STRATA_VERIFY_PIPE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL の stepped verifier が CPU expert pool を処理する間に、次の split segment（plan copy と VRAM expert 群）を helper thread と並行して投入するかを選ぶ。既定は並行投入で、`STRATA_VERIFY_PIPE=0` は helper thread を使わず pool 処理を同期実行する A/B 用の設定である。変わるのは serve と split segment の実行順序・重なり方で、コード上この分岐は pool の計画値を使って後続 GPU segment を投入する。token 選択や出力値を変える処理はこの分岐にはない。実装は `engine/sycl/src/core/verify.cpp` の `Verifier::run` 内にある。ファイルは SYCL の CMake ソースに含まれる（`engine/sycl/CMakeLists.txt:35-43`）。

## 値と判定

`std::getenv` の結果を文字列全体として parse せず、未設定かどうかと先頭1文字だけを見る。環境変数が未設定、空文字、または先頭が `0` 以外なら `pipe=true`。先頭文字が `0` なら `pipe=false` である。したがって `0`、`00`、`0anything` は無効化し、`1`、`true`、`false`、` 0`、`anything` は有効のままになる。大文字小文字、空白除去、数値としての妥当性検査はしない。判定箇所は `engine/sycl/src/core/verify.cpp:2525-2528`。

| 条件 | unset | パイプライン有効 | パイプライン無効 |
|---|---|---|---|
| `serve` が初めて読み取るとき | 有効 | 空文字、`1`、`true`、`false`、` 0`、`anything` など（先頭が `0` 以外） | `0`、`00`、`0anything` など（先頭が `0`） |

## 有効になる条件

- Strata の SYCL verifier を使う経路であること。候補名の実読み取りは `engine/sycl/src/core/verify.cpp` の1か所で、CUDA/HIP 側にこの名前の読み取りはない（同ファイル `:2527`）。
- `STRATA_VERIFY_STEPPED` が `env_on` 判定で有効であること。`env_on` は空でない値の先頭が `0` 以外なら有効とする（`engine/sycl/src/core/verify.cpp:151-154,194`）。
- `Verifier::run` が stepped-run 経路に入ること。これは all-resident ではなく（`ar_on()` は `all_resident_ && !ar_off_`）、`STRATA_VERIFY_EAGER` が未設定で、対象 window の segment がある場合である（`engine/sycl/include/strata/core/verify.hpp:364-370`、`engine/sycl/src/core/verify.cpp:2479`）。
- CPU pool を serve する点から次の segment が split point であること。`STRATA_VERIFY_SPLIT` が未設定、または先頭文字が `0` 以外なら split hook が作られる。`STRATA_VERIFY_SPLIT=0` など先頭が `0` の場合は split segment がなく、この変数による切替は起きない（`engine/sycl/src/core/verify.cpp:2075-2077,2525-2528`）。
- `--remote-expert-opt` を使わないこと。stepped-run はこの設定との併用時、serve に入る前に `verify: STRATA_VERIFY_STEPPED does not serve --remote-expert-opt` をエラーとして返す（`engine/sycl/src/core/verify.cpp:2493-2495`）。
- GPU の全 expert が VRAM 常駐している場合は stepped-run ではなく `stepped_ar` 側になるため、この変数の `serve` 分岐を通らない（`engine/sycl/src/core/verify.cpp:2479-2481`、`engine/sycl/include/strata/core/verify.hpp:364-370`）。

## 実行時の詳細

`pipe` は `serve` 内の関数ローカル `static const` であり、最初に `serve` がこの判定に到達した時点で値を読み、その後の呼び出しではキャッシュ値を使う。プロセス実行中に環境値を変更しても再評価されない（`engine/sycl/src/core/verify.cpp:2501-2502,2525-2528`）。

`pipe=true` かつ次 segment が split point の場合、Strata は CPU pool を `std::thread` で動かし、plan flag A が立つか pool が終了するまで待ってから split segment の graph を投入し、helper thread を join する。pool が plan を出さずに終了した場合は空 plan を設定する。その他（`pipe=false` または split point でない場合）は pool をその場で同期実行し、plan flag A が立っていなければ同じく空 plan を設定する（`engine/sycl/src/core/verify.cpp:2514-2557`）。この変数の読み取り自体はログを出さない。

## ログと測定値

通常の有効・無効状態を示すログはない。helper thread の生成などで例外が起きると verifier の error に `verify: pipelined serve: <例外文>` が入り、pool が例外を投げると `verify: pool: <例外文>` が入る（`engine/sycl/src/core/verify.cpp:2528-2552`）。呼び出し元の `strata generate` は verifier が失敗すると `strata generate: <error>` を stderr に出して終了コード 1 を返す（`engine/sycl/src/program/generate.cpp:14114-14117`）。この変数について比較測定値は確認できない。

## 根拠

- `engine/sycl/src/core/verify.cpp:151-154,192-194` — 共通の `env_on` 判定と stepped flag。
- `engine/sycl/src/core/verify.cpp:2075-2077,2479-2481` — segment capture と stepped-run/all-resident の条件。
- `engine/sycl/src/core/verify.cpp:2493-2495,2501-2557,2575-2586` — remote expert-opt の拒否、pipe 判定、非同期/同期経路と失敗処理。
- `engine/sycl/include/strata/core/verify.hpp:364-370,400-410` — all-resident 判定と segment 種別。
- `engine/sycl/CMakeLists.txt:35-43` — `verify.cpp` の SYCL ビルド構成。
- `engine/sycl/src/program/generate.cpp:14114-14117` — generate 側でのエラー表示と終了。
