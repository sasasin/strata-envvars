# `STRATA_TEST_BELL_SLEEP_US`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

パイプライン同時読み込み中に stage の doorbell を処理する専用スレッドが、busy な stage がないときに使う待機方法を、テスト用に条件変数待ちから指定マイクロ秒の sleep に切り替える。正の値では launch 通知を待つ条件変数経路を通らず、指定時間ごとにループを再確認する。通常の unset / 0 では条件変数で待つ。対象コードは `engine/src/program/generate.cpp` の concurrent prompt read 経路にある（21113-21116, 21138-21175行）。

## 値と判定

関数スコープ内 `static const int` の初期化ラムダで `std::getenv` を呼び、設定されていれば `std::atoi` で整数化し `std::max(0, ...)` で負値を 0 にする。文字列全体の妥当性検査はなく、`atoi` が読む数値 prefix が使われる。未設定と空文字は 0、数値 prefix がない値も 0。先頭空白や符号は `atoi` の規則で処理される。大文字小文字の比較はない。例えば `25` と `25tail` は 25、`0`、`-2`、`true`、空文字、`tail` は 0。正の `int` に変換できる範囲の値だけが sleep 分岐に入る。範囲外の数値文字列の変換結果は本コードで検査・規定されていない。（21157-21164行）

| 条件 | unset | sleep に使う値 | sleep しない例 |
|---|---:|---|---|
| concurrent doorbell thread が動作 | 0 | `atoi` の結果が正ならその値（µs） | 空文字、`0`、負数、数値 prefix のない文字列 |

## 有効になる条件

- 同時 prompt read が有効であること。`STRATA_PIPED_CONCURRENT` が設定され、`atoi` の結果が 0 以外であることが必要。unset / `0` / `false` など `atoi` が 0 にする値では通常経路となる（21024-21046行）。
- `piped` が真であること。これは `--batch` が正、`--batch-groups` が 1 より大きく、pipeline stage 数 `n_pipe` も 1 より大きい場合（17531行）。加えて画像入力がなく、読み込み token 数が `STRATA_PIPED_CONCURRENT_MIN` 以上であること。`MIN` は unset / 0 なら 0 として全読み込みが対象になる（21047-21054行）。
- concurrent read の構成判定で抑止されないこと。`STRATA_PREFILL_HELP`、`STRATA_SPLIT_MTP_BATCH`、`STRATA_FS_SLOTS`、`--pcie-mode dma`、expert helper cache（`--expert-cache-device1..3`、それらを使う `--remote-expert-opt`）、blob を stage する GGUF / unbuffered / `STRATA_IO_PREFETCH` source、または GGUF source / arena 以外の expert source があると concurrent read は無効になり、最初に該当した理由を `strata batch: STRATA_PIPED_CONCURRENT is off beside ...` と出力する（`engine/include/strata/program/batch_read.hpp:31-53`, `engine/src/program/generate.cpp:21031-21045`）。
- 上記分岐で doorbell thread が作られ、その thread が busy stage を処理し終えて idle 分岐に到達したときだけ変数の sleep 処理が関係する。busy 中は `batch_serve` を実行して即座に次の周回へ進む（21138-21164行）。
- `req_imgs` が空でない読み込みはこの concurrent read 分岐に入らない（21054行）。
- Strata の `docs/BATCHING.md` はこの concurrent read 機能を CUDA / HIP build 向けと記載し、SYCL では利用できないとしている（`docs/BATCHING.md:279-281`）。

## 実行時の詳細

環境変数は doorbell thread のループ内にある block-scope static の初期化ラムダで初回評価され、そのプロセス内では以後の読み込みで再評価されない。評価時点は最初に busy でない周回が `test_sleep_us` 宣言へ到達したときであり、それ以前にプロセス環境を変更できるコードはこの箇所にはない。正の値なら `sleep_for(microseconds(test_sleep_us))` 後に周回を続ける。0 以下なら `bell_waiting` を立て、`bell_cv.wait_for` で最大 2 ms、終了または stage busy を待つ。pump 側は launch 時に待機中なら条件変数を通知する（21165-21174行、`generate.cpp:18307-18313`）。doorbell thread は読み込み経路の終了時に停止フラグを下ろして wake し、join される（21117-21126行）。

この設定は `STRATA_PIPED_CONCURRENT` の有効化や読み込み可否を変更せず、idle 時の待ち方だけを変える。別の CLI 数値との優先順位はなく、doorbell thread が存在しない経路には作用しない。Strata のコードにこの変数専用の警告・ログ・エラー出力はない。呼び出し側には batch window 失敗時に `a pipelined batch window failed` を返す経路があるが、この環境変数の値を原因と結びつける処理はない（21243-21250行）。

## ログと測定値

この変数を出力する専用ログはない。Strata の `docs/BATCHING.md` は、2x RTX 5090、Swift 1.5 IQ3_S、split 25、`--batch 6 --batch-groups 2`、resident experts、k8v4、262K、`--kv-resident 32768`、engine-default decode share の測定で、`STRATA_TEST_BELL_SLEEP_US=50` にすると prompt 読み込み中の stream rate が 85–92 tok/s から 64–67 tok/s になったと記載する（`docs/BATCHING.md:279-303`）。これは同資料に記録された測定であり、ソースコードから再測定した値ではない。

## 根拠

- `engine/src/program/generate.cpp:17531`, `21024-21054` — batch / group / stage 条件、同時読み込みの opt-in、token 閾値、画像入力の条件。
- `engine/src/program/generate.cpp:21113-21175` — doorbell thread、環境値の変換と sleep / 条件変数待ち。
- `engine/src/program/generate.cpp:18307-18313` — launch 時の doorbell 待機通知。
- `engine/src/program/generate.cpp:21243-21250` — concurrent read の失敗伝播。
- `engine/include/strata/program/batch_read.hpp:31-53` — concurrent read を抑止する設定と理由。
- `docs/BATCHING.md:279-303` — Strata 資料の測定条件と報告値。
