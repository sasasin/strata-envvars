# `STRATA_SLOT_READ_WIDE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

サーバーの batch slot が会話の次ターンをその slot の window で読む `STRATA_SLOT_READ` に対する、追加の幅指定です。`STRATA_SLOT_READ` と本変数の両方が有効なとき、pipelined group の基本行数が 8 未満なら group window の容量を 8 行（`kVerifyNarrowT`）まで広げます。実際の読み取りで追加行を使うのは、読み取り中の slot がその group の唯一の稼働 slot で、残りの prompt 行が window 全体を満たす場合です。通常の生成 token の候補や sampler を変更する設定ではなく、既知の prompt token を処理する window の行数を変えます。`engine/src/program/generate.cpp:7831-7851` `engine/include/strata/kernels/window_limits.hpp:20-25` `engine/src/program/generate.cpp:18097-18135`

## 値と判定

`batch_groups::slot_read_wide_on` が `STRATA_SLOT_READ` と `STRATA_SLOT_READ_WIDE` の値を `switch_on` に渡します。各値は、未設定または空文字なら off、先頭文字が `0` なら off、それ以外なら on です。文字列全体・数値・大文字小文字・前後の空白は検査しません。したがって `1`, `true`, `false`, `2`, ` 0` は on、`0`, `0anything`, 空文字は off です。負数の `-1` も先頭が `0` でないため on です。`engine/include/strata/program/batch_groups.hpp:41-45`

| `STRATA_SLOT_READ` | `STRATA_SLOT_READ_WIDE` | 判定 |
|---|---|---|
| unset / empty / `0...` | 任意 | off |
| 有効値 | unset / empty / `0...` | off |
| 有効値 | 有効値 | on |

ここで「有効値」は先頭文字が空でも `0` でもない文字列です。二つの環境変数の論理積であり、本変数だけを設定しても有効になりません。CLI 引数から本変数を指定・上書きする処理はありません。リクエストの `slot_read=1` は個々の読み取りを要求する別の条件で、本変数の値を上書きしません。`engine/src/program/generate.cpp:7838-7842` `engine/src/program/generate.cpp:18765-18821`

## 有効になる条件

本変数と `STRATA_SLOT_READ` が on でも、以下を満たさない経路では wide read は実行されません。

- `--serve` で batch MTP slot を使うこと。batch MTP は `--batch-mtp` または `STRATA_BATCH_MTP` と MTP draft model / `--spec >= 2` を必要とし、Metal build では無効化されます。`engine/src/program/generate.cpp:7770-7802`
- layer split 上で 2 つ以上の pipelined batch groups が残ること。`--batch-groups`、`--adapt-async`、`STRATA_BATCH_MTP_SERIAL`、NVIDIA の `STRATA_BATCH_GROUPS_NV_SERIAL` / `STRATA_DEFAULTS=026` などによって serial group になると対象外です。`engine/include/strata/program/batch_groups.hpp:81-110` `engine/src/program/generate.cpp:7732-7749`
- `STRATA_PIPED_MTP` が有効で、`STRATA_BATCH_SELF_COMMIT` が off であり、pipelined MTP が最終的に有効なこと。group 数・残った slot 数が不足する場合や、MTP proposal を含む group が 8 行を超える場合は `STRATA_PIPED_MTP` が off になります。layer split で helper expert cache を使う場合も batch MTP の gate で off になります。`engine/src/program/generate.cpp:7786-7807` `engine/src/program/generate.cpp:8049-8074`
- `pmtp_group_cap` が slot 当たりの行数より大きいこと。group の基本行数が既に 8 行以上なら、この設定による増分はありません。容量は verifier の `batch_max_t` に収まる必要があります。`engine/src/program/generate.cpp:7843-7864` `engine/src/program/generate.cpp:17423-17456`
- 実際の会話読み取りでは、サーバー要求に `slot_read=1` があり、会話を引き継ぐ idle slot が見つかること。さらに GENI でない、画像なし、logprobs なし、pinned prefix なし、partial slot でない、slot 側が parked conversation と同じかそれより長い prefix を持つ、turn の新規 token 数が `STRATA_SLOT_READ_MAX` 以下（既定 1024）、checkpoint の stage 数が一致する、という条件があります。どれかを満たさない要求は通常の admission / prompt path に進みます。`engine/src/program/generate.cpp:17451-17456` `engine/src/program/generate.cpp:19272-19302`
- その要求を載せる group の稼働 slot が一つだけで、現在の turn の prompt token が group window の全行を埋めるだけ残っていること。短い残りや turn checkpoint / context / penalty window による上限が先に当たる場合、追加行は使われません。`engine/src/program/generate.cpp:17587-17597` `engine/src/program/generate.cpp:18097-18120`

## 実行時の詳細

環境値は `generate.cpp` の `pm_read_wide` 初期化時に読み、`const bool` として保持します。関数内 `static` ではありませんが、要求ループ内で再読込されないため、実行中に環境を変更してもその実行経路には反映されません。CLI 引数や request の `slot_read` は、本変数の判定値を変更しません。`engine/src/program/generate.cpp:7838-7842`

有効時は `pm_group_rows` が、slots とその draft 行数で計算した容量を、`kVerifyNarrowT`（この commit では 8 行）未満の場合に 8 行へ引き上げます。これが verifier window の上限計算、MTP drafter の residual buffer 行数、deferred commit、group の行容量に伝わります。したがって wide slot read の要求が来ない場合でも、条件を満たす pipelined MTP の実行では、これらの容量・VRAM 使用量を増やすことがあります。`engine/src/program/generate.cpp:7843-7864` `engine/src/program/generate.cpp:13211-13223` `engine/src/program/generate.cpp:13562-13580` `engine/src/program/generate.cpp:13595-13600` `engine/include/strata/kernels/window_limits.hpp:20-25`

リクエストが slot read の条件を満たすと、slot の turn prompt は既知 token として各行に割り当てられます。通常は slot 当たりの行数で計画し、wide が有効な場合は group 全体の容量まで計画します。ただし追加行を使う group window は、その group 内の稼働 slot が 1 個の読み取り slot であり、残りの prompt が全容量を満たすときに限られます。追加行の window をあらゆる中間サイズ分 capture するのでなく、全容量の row layout を使います。コードコメントは row layout 1 種につき各 stage 20–30 MiB の VRAM とし、slot ごとに追加する layout は一つと記しています。`engine/src/program/generate.cpp:17589-17597` `engine/src/program/generate.cpp:18097-18120`

## ログと測定値

wide 条件を満たす server 起動では、stderr の `strata generate: STRATA_SLOT_READ: ... and <行数> while it is the only slot of its group that runs (STRATA_SLOT_READ_WIDE)` 部分で実行上の容量を確認できます。このログは `slot_read` 機能が有効な場合だけ出ます。通常の server `INFO` 行の `slot_read=1` は `STRATA_SLOT_READ` 側の capability を示す値であり、wide の有効性を単独では示しません。`engine/src/program/generate.cpp:16069-16076` `engine/src/program/generate.cpp:17464-17472`

要求が実際に slot read に進む場合は stderr に `strata batch: slot ... reads its conversation's next turn in its own windows: ...`、stdout に `DONE 0 ...` と `BADM ...` を出します。wide flag が unset・空・`0` 始まりの場合やその他の条件不足では wide 専用の警告はなく、追加幅を要求しません。追加容量の確保に失敗した場合、たとえば MTP slot residual buffer は `strata serve: batch MTP slot %d residual buffer does not fit%s`、deferred commit 初期化は `strata serve: STRATA_PIPED_MTP, stage %zu: %s` を出して起動を失敗させます。`engine/src/program/generate.cpp:13567-13580` `engine/src/program/generate.cpp:13595-13600` `engine/src/program/generate.cpp:19390-19399`

`terminal/data/settings-register.json:42800-42838` の reviewed note には `STRATA_SLOT_READ=1` と本変数を使った測定として、2x RTX A4000、IQ3_XXS、60K-token の会話 2 件、交互に turn を送った 4 interleaved rounds で、後続 turn の first token が 12.13 秒から 8.20 秒（-32.4%、4/4 rounds）、read throughput が 42.0 から 62.0 tokens/s、同一 token と記録されています。同 note は 10K tokens では 4 回中 2 回のみ高速としています。これは当該測定条件の記録であり、他の GPU・モデル・会話長への一般化はできません。コード上の読取り幅・同一性の効果を独立に再測定したものではありません。`terminal/data/settings-register.json:42800-42838`

## 根拠

- `engine/include/strata/program/batch_groups.hpp:41-48` — switch 判定と `STRATA_SLOT_READ` との論理積。
- `engine/include/strata/kernels/window_limits.hpp:14-25` — build 時 window row limit と `kVerifyNarrowT=8`。
- `engine/src/program/generate.cpp:7732-7807,8049-8074` — batch group / piped MTP の前提と無効条件。
- `engine/src/program/generate.cpp:7831-7864,13211-13223,13562-13600` — wide 容量とその buffer / verifier への反映。
- `engine/src/program/generate.cpp:16069-16076,17423-17472` — slot-read capability、pipelined group 条件、起動ログ。
- `engine/src/program/generate.cpp:17574-17600,18097-18120,18765-18821,19272-19400` — request 判定、prompt row の計画・使用、観測可能な結果。
- `terminal/data/settings-register.json:42800-42838` — 条件付き測定メモ。
