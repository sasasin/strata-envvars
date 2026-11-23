# `STRATA_BATCH_CONCURRENT_READ`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`--batch` で処理中のスロットがあるとき、適用条件を満たす prompt の読み込みを専用スレッドで行い、その間もこのスレッドで batch window を進めます。無効時や条件を満たさない場合は通常の `run(q, r)` に戻ります。読み取り箇所は `engine/src/program/generate.cpp` の `conc1` 初期化で、実際の分岐は同ファイルの `run_conc` です（`20787-20805`）。

## 値と判定

最初に `run_conc` の初期化箇所へ到達したとき、`std::getenv` の結果を `std::atoi(v) != 0` で判定し、関数内 `static` の `conc1` に保存します（`engine/src/program/generate.cpp:20792-20795`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| すべての実行条件 | `false` | `1`、`2`、`-1`、`1tail`（整数として読める先頭部分が非ゼロ） | 空文字、`0`、`0tail`、`true`、整数部分を読めない文字列 |

`atoi` のため、文字列全体の厳密な数値検証・大文字小文字の判定・範囲制限はありません。先頭の空白と符号は整数変換に従い、変換された値がゼロなら無効、非ゼロなら有効です。表現可能範囲を超えた数値の結果は、このコードで定義・検査されていません。CLI 引数による値の上書きや、無効値時の別の既定値への fallback はありません。

## 有効になる条件

環境変数の判定が有効であることに加えて、prompt 読み込み時に次をすべて満たす必要があります（`engine/src/program/generate.cpp:20796-20799`）。満たさない場合は同じ箇所から通常の `run(q, r)` に進みます。

- `--batch`（または同義の `--slots`）が正数であること。引数は `o.batch` に設定されます（`engine/src/program/generate.cpp:4036-4037`）。
- batch slot が少なくとも一つ active であること。`batch_on()` は `BSlot::active` を走査します（`engine/src/program/generate.cpp:16696`, `16750`）。
- `--no-prefill-borrow` が指定され、`o.no_prefill_borrow` が true であること（`engine/src/program/generate.cpp:4030`）。
- `piped` が false で、`stages` が空であること。layer split の stage がある経路は対象外です。`piped` は batch groups と複数 stage の条件で決まります（`engine/src/program/generate.cpp:17423-17426`）。
- その request に画像がなく（`req_imgs.empty()`）、elastic K/V が有効でない（`!kvg.on`）こと。
- その prompt part の長さが `piece_now()` によって正の piece に分割されること。piece が正でなければ `run(a0, b0)` へ進みます（`engine/src/program/generate.cpp:21237-21242`）。

実装コメントはこの機能を「one GPU」と説明しています（`engine/src/program/generate.cpp:20787`）。コード上の明示的な判定は `stages.empty()` であり、`multi_gpu` を直接検査する条件はこの分岐にはありません。OS や GPU 世代、特定の build macro による追加判定もこの箇所にはありません。

## 実行時の詳細

`conc1` は初回到達時に一度だけ評価されるため、後から環境値を変更しても同じプロセス内では反映されません（`engine/src/program/generate.cpp:20792-20795`）。他の環境変数はこの分岐の有効条件に使われていません。CLI は環境変数の値を上書きしませんが、`--batch` と `--no-prefill-borrow` は機能を使うための別条件です（`engine/src/program/generate.cpp:4030`, `4036-4037`, `20797-20799`）。

条件を満たすと `run_conc` は `in_prompt_read` と `conc_read` を立て、prefill の share を block してから reader thread を起動し、そのスレッドで `run(q, r)` を実行します。呼び出し側のスレッドは reader の完了まで `batch_on()` 中に `batch_step()` を進め、`BSTOP` 入力も処理します。reader を join した後、prompt の読み込み token 数・所要時間と、その間に進んだ window 数を stderr に出します（`engine/src/program/generate.cpp:20800-20846`）。この環境変数が変えるのは読み込みと slot window の進め方であり、CLI 引数や prompt token の内容はこの分岐では書き換えません。

batch window が失敗すると `batch_fatal` を立て、`a batch window failed` をエラーとして返します。reader 内で例外が発生した場合は `the prompt read failed: <例外内容>`（または `the prompt read failed`）を記録します。失敗は呼び出し元で `strata serve: <エラー>` を stderr、`ERR <エラー>` を stdout に出し、通常は終了コード 1 で request 処理を終えます（`engine/src/program/generate.cpp:20806-20814`, `20847-20852`, `21487-21498`）。条件不成立時や変数が無効のときに、この機能専用の理由ログはありません。

## ログと測定値

有効経路を通った場合の stderr 行は `strata batch: read %lld tokens on a thread of its own in %.0f ms; the slots ran %lld windows meanwhile` です（`engine/src/program/generate.cpp:20844-20846`）。調査対象 commit のコードと関連文書 `docs/BATCHING.md:328-357` を照合しました。同文書は pipelined groups の別の読み込み方式を説明しており、この環境変数固有の測定値は確認できないため、性能値は記載しません。

## 根拠

- `engine/src/program/generate.cpp:20787-20852` — 値の読み取り、適用条件、reader thread と batch window の並行処理、結果ログ。
- `engine/src/program/generate.cpp:16696`, `16750` — batch slot と active 判定。
- `engine/src/program/generate.cpp:4030`, `4036-4037`, `17423-17426`, `21237-21242` — 関連 CLI 引数、piped 判定、piece 呼び出し。
- `engine/src/program/generate.cpp:21487-21498` — prompt 読み込み失敗時のログと終了経路。
- `docs/BATCHING.md:328-357` — 関連する batch 読み込み文書との照合。
