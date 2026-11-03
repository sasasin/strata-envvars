# `FNX_DRAFT_PEN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査対象リポジトリの作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

sFNX の MTP draft layer が次の draft token を作る際、sampling 設定の repetition / frequency / presence penalty を draft logits にも適用するかを制御します。既定値は有効です。`0` にすると draft 側だけ penalty を適用しません。通常の検証側（main model）の出力分布は別に `Sampling` の penalty 設定で計算され、draft はその分布との speculative sampling に使われます。

この変数の読み取り箇所は `src/split/src/session.cpp` と `src/split/src/batch.cpp` の2箇所です。いずれも sFNX 用コードの `fnx::env_int` helper を使います。Strata の通常 engine に対する環境変数ではありません。

## 値と判定

`src/split/src/env.hpp:15-21,33-40` の `env_int` は設定値全体を base-10 の符号付き整数として読みます。`FNX_DRAFT_PEN` では値が `0` 以外なら有効、`0` なら無効です。

| 値 | 判定 |
|---|---|
| 未設定 | 既定値 `1`。ただし Session 経路では sampling penalty が実際に有効な場合にだけ変数を読む |
| `0` | draft logits に penalty を渡さない |
| 0 以外の整数（負値を含む） | draft logits に penalty を渡す |
| 空文字、整数でない文字列、整数の後ろに余分な文字がある値、`long long` 範囲外 | `std::runtime_error`。許容範囲への clamp はない |

符号 `+` / `-` は受け付けます。先頭文字は符号または数字でなければならず、空白を含む値や末尾空白は拒否されます。例として `+1`, `-2`, `01` は有効、` 1`, `1 `, `1x`, 空文字は無効です。helper は `strtoll` の後に文字列末尾まで消費したことと overflow がないことを検査します。

Session 経路では `penalize && env_int(...)` の短絡評価により、sampling penalty が無効なら環境値を読みません。その場合、無効な文字列でもこの箇所からはエラーになりません。一方、batch decoder は生成設定にかかわらず構築時に読みます。

## 有効になる条件

この変数が draft penalty の有無を変えるには、sFNX の MTP draft が使われる必要があります。通常の Session では `speculate` が有効で、MTP draft layer が engine に attach されていることが前提です。`Engine::draft` は draft layer 未接続時に `draft: no draft layer attached` を投げます。バッチ経路は server の `--batch` が2以上で `FNX_BATCH_DRAFTS` が `off` ではない場合に `BatchDecoder` を作りますが、`FNX_BATCH_DRAFTS=lookup` は lookup draft だけを使うため、この変数は penalty に影響しません。decoder constructor は lookup mode でも `FNX_DRAFT_PEN` を parse するので、無効値ならそこでエラーになります。

さらに実際の penalty 適用には、sampling が有効（temperature > 0）、`pen_last_n > 0`、かつ repeat / frequency / presence のいずれかが既定値と異なることが必要です。greedy decoding や penalty が設定されていない request では、この変数の値にかかわらず draft penalty は使われません。これらの条件は `penalizes()` で判定されています。

CLI の引数で `FNX_DRAFT_PEN` の値を上書きする処理は見つかりません。request の sampling 設定は penalty 適用の条件や数値を決めますが、この環境変数は draft 側にそれを適用するかを選びます。

## 実行時の詳細

単独 Session の `Session::generate` は各 generate 呼び出しで `pen_drafts` を計算し、penalty 条件が成立する場合に環境値を読み直します。draft 1個ごとに直近 `pen_last_n` token から penalty row を作り、その row を `Engine::draft` に渡します。MTP chain の後続 draft では直前の draft token も履歴へ足します。環境値の static cache はありません。

バッチ経路の `BatchDecoder` は構築時に `pen_drafts_` を一度設定し、その decoder の間は値を保持します。sFNX server では `--batch > 1` かつ batch drafting が有効なときに server 構築中に decoder が作られるため、後からプロセス環境を変更しても既存 decoder には反映されません。`fnx_run bdecode` の batch decoder も構築時に値を保持します。

有効な設定値に対して、この環境変数専用のログはありません。無効値で helper が例外を投げた場合、sFNX は `ERR <例外文>` を stdout に、`sfnx: failed: <例外文>` を stderr に出して status 1 で終了します。初期化時の失敗は `READY` を出す前に発生します。`fnx_run` は `fnx_run: <例外文>` を stderr に出して status 1 で終了します。エラー本文は `FNX_DRAFT_PEN: '<値>' is not a whole number` です。

## 根拠

- 値の全体 parse、未設定 fallback、無効値の例外: `src/split/src/env.hpp:15-21,33-40`。
- penalty 条件、Session 経路での読み取り、draft logits への penalty row の受け渡し、後続 draft への履歴追加: `src/split/src/session.cpp:100-110,397-410,439-449,556-582`。
- MTP draft 未接続時の失敗と、draft penalty を engine 側のカード別データへ渡す処理: `src/split/src/engine_common.cu:1371-1387,1393-1410,1434-1438`。
- BatchDecoder の構築時読み取りと cached member: `src/split/src/batch.cpp:64-86`, `src/split/src/batch.hpp:57-63`。
- batch server で decoder を作る条件: `src/split/tools/sfnx.cpp:435-445`。
- sFNX の例外を protocol / stderr に出して終了する処理: `src/split/tools/sfnx.cpp:1027-1035,1040-1049,1086-1090`。
- `fnx_run` の例外表示と終了 status: `src/split/tools/fnx_run.cpp:1364-1373`。
