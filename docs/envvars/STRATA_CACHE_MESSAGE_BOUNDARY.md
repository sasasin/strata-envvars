# `STRATA_CACHE_MESSAGE_BOUNDARY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の prompt cache に、最終ターンより前のメッセージ境界の checkpoint を追加する opt-in 変数。長い会話で最後の質問だけが変更されたとき、通常の checkpoint より先の履歴状態を再利用できる場合がある。既存の token / image の一致確認による再利用判定は残り、この変数は checkpoint を追加するだけである（`engine/src/program/generate.cpp:21491-21498`、`engine/sycl/src/program/generate.cpp:11627-11637`）。

同じ読み取りと分岐が CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL の `engine/sycl/src/program/generate.cpp` にある。名前への実コード参照はこの二箇所で、Python server 側の参照は候補位置を選ぶコメントである（`terminal/serve/server.py:2498,2542-2544`）。

## 値と判定

両 engine は最初にこの処理へ到達したとき、関数内 `static const bool` の初期化で `std::getenv` を一度呼び、値が存在し、かつ `std::atoi(e) != 0` なら有効にする（`engine/src/program/generate.cpp:21491-21494`、`engine/sycl/src/program/generate.cpp:11627-11630`）。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効（`getenv` が null） |
| 空文字 `""` | 無効（`atoi` は 0） |
| `0`、`0anything`、`true`、数字で始まらない文字列 | 無効（先頭の整数変換結果が 0） |
| `1`、`2`、`1anything`、`-1` | 有効（先頭の整数変換結果が非ゼロ） |

`atoi` は文字列全体の妥当性を検査せず、先頭の空白と符号の後にある10進数字列を整数化するため、大文字小文字や後続文字列は判定条件にならない。数値として変換できない先頭なら 0 になる。範囲外の値に対する `atoi` の結果は保証されず、Strata 独自のエラー処理・範囲制限もない。環境値を読んだ結果を CLI 引数で上書きする処理はない。機能側は別途 `--prompt-cache`、有効な `--turn-token` と単一 GPU 条件を要求する（同上; `engine/include/strata/program/message_boundary.hpp:9-17`）。

## 有効になる条件

- engine が `--serve` の prompt 読み取り処理を実行していること。通常実行のプロンプト読み取りにはこの分岐はない（`engine/src/program/generate.cpp:21459-21466`、`engine/sycl/src/program/generate.cpp:11593-11603`）。
- `--prompt-cache` が正であること。既定値は 6 で、0 以下では message boundary を選ばない（`engine/src/program/generate.cpp:1086-1090,1293-1295,21497-21498`、SYCL 側 `engine/sycl/src/program/generate.cpp:11635-11637`）。
- 実効 `multi_gpu` が false であること。層分割で複数 GPU を使う経路では変数が有効値でも無視される（同上）。
- `--turn-token` が負でなく、今回の prompt で `resume` より後に最終ターン境界が見つかること。リクエストの `ckpt=0` は最終 turn checkpoint を無効にし、結果としてこの境界 checkpoint も選ばれない（`engine/src/program/generate.cpp:21464-21467,21482-21498,18841-18845`、`engine/include/strata/program/message_boundary.hpp:9-12`）。
- helper は最終 turn より前へ遡り、最初に見つけた `turn_token` の位置が 8,192 以上、かつ最終 turn から 16,384 token 以内の場合だけ位置を返す。対象 turn token が prompt 内にない、または条件を満たす過去の境界がなければ checkpoint は追加されない（`engine/include/strata/program/message_boundary.hpp:9-17`、呼び出し側 `engine/src/program/generate.cpp:21495-21498`）。

コード上、この判定に OS 固有の条件はない。利用可能性は実際に起動する CUDA/HIP または SYCL engine の build に依存する。

## 実行時の詳細

環境値はプロセス起動直後ではなく、serve の prompt 処理がこの関数内 static 初期化へ初めて到達した時に一度だけ評価される。以降のリクエストでは同じ値が使われ、プロセス実行中に環境を変更しても再評価されない（`engine/src/program/generate.cpp:21491-21494`、`engine/sycl/src/program/generate.cpp:11627-11630`）。

選ばれた位置 `message_at` は prompt の読み取り区切り一覧に追加され、エンジンはそこまで読み進めた後に checkpoint を保存してから先を読み続ける（`engine/src/program/generate.cpp:21522-21527,21609-21623`、`engine/sycl/src/program/generate.cpp:11638-11652,11673-11685`）。保存状態は既存の会話 checkpoint cache に入り、`--prompt-cache N` の上限と既存の eviction の対象になる。message-boundary 用として保持される tail checkpoint は一つで、新しい tail の保存時に前の tail を削除する（`engine/src/program/generate.cpp:14710-14728`）。

設定が無効、条件が不足、または適切な境界がない場合、追加区切りは `-1` となり通常の読み取り区切りだけを使う。checkpoint の保存に失敗した場合、継続可能な失敗では stderr に `strata serve: checkpoint at ... skipped: its state could not be copied out (see above); the request goes on without it` と出して続行する。継続不能な失敗では stdout に `ERR saving a conversation checkpoint failed...` を出してリクエスト処理を `return 1` で終える（CUDA: `engine/src/program/generate.cpp:21610-21617`; SYCL: `engine/sycl/src/program/generate.cpp:11674-11681`）。

通常は有効化しただけでは専用ログを出さない。`STRATA_TRACE` が設定されている場合（空文字でも設定あり）、選択した区切りに到達すると stderr に `strata serve: message boundary checkpoint: %lld tokens, %lld tail` を出す（CUDA: `engine/src/program/generate.cpp:16069-16077,21621-21623`; SYCL: `engine/sycl/src/program/generate.cpp:11683-11685`）。

## ログと測定値

この変数の現行 commit に対する測定値は確認できないため記載しない。Strata の `docs/MESSAGE_BOUNDARY_CACHE.md:15-19` は tail の上限を 1,024 token と記述しているが、現行の CUDA/HIP と SYCL の呼び出しは helper に `max_tail=16384` を渡している（`engine/src/program/generate.cpp:21497-21498`、`engine/sycl/src/program/generate.cpp:11635-11637`）。この文書ではソースの値を採用した。その他の専用ログは `STRATA_TRACE` 設定時の到達ログと、上記の checkpoint 失敗時ログである。

## 根拠

- `engine/src/program/generate.cpp:21491-21498,21522-21527,21609-21623`
- `engine/sycl/src/program/generate.cpp:11627-11637,11638-11652,11673-11685`
- `engine/include/strata/program/message_boundary.hpp:9-17`
- `engine/src/program/generate.cpp:1086-1090,1293-1295,14710-14728,16069-16077,18841-18845`
- `terminal/serve/server.py:2498,2542-2544`
- `docs/MESSAGE_BOUNDARY_CACHE.md:15-19`（ソースとの記述差の確認のみ）
