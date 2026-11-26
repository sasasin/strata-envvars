# `STRATA_DRAFT_KEEP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`--draft auto` で DFlash2 がロードされている serve loop において、現在のリクエストで使っていない drafter の状態を、window の commit ごとに追いつかせる処理を止める診断用スイッチです。`STRATA_DRAFT_KEEP` 自体はドラフト方式の選択や token の採否を直接分岐しません。未設定または `atoi` の結果が 0 以外なら idle drafter の upkeep を行い、設定されていて結果が 0 なら省きます（`engine/src/program/generate.cpp:16416-16419, 18982-19005, 23087-23103`）。

## 値と判定

serve loop の `static const bool` として `getenv(...) != nullptr && atoi(getenv(...)) == 0` を一度評価します。値全体の妥当性検査や範囲制限はありません。設定の有無を先に調べるため、unset は upkeep を有効にします。設定値は C の `atoi` で整数変換され、変換結果が 0 なら upkeep を無効にします（`engine/src/program/generate.cpp:16417`）。

| 条件 | unset | upkeep を有効にする値（例） | upkeep を無効にする値（例） |
|---|---|---|---|
| `STRATA_HAVE_DFLASH2` がある build の `--draft auto` serve loop | 有効 | `1`, `-1`, `1xyz`（変換結果が非 0） | 空文字, `0`, `00`, `0anything`, `true`, `false`, `abc`（変換結果が 0） |
| macro がない build、または DFlash2 が使われない経路 | upkeep 分岐自体が実行されない | なし | なし |

`atoi` は先頭の空白と符号を許し、数字列を変換して後続の非数字を読み飛ばします。したがって ` 0x` は 0、` 1x` は 1 です。数値文字列の完全一致・大文字小文字・真偽値語の検査はしません。`atoi` で `int` に収まらない値の結果は規定できないため、巨大な値の挙動は保証されません（`engine/src/program/generate.cpp:16417`）。

## 有効になる条件

- `STRATA_HAVE_DFLASH2` が定義された build である必要があります。CUDA/HIP 共通 engine ではこの macro を定義し、macro がない場合 `use_df2` は常に `false` です（`engine/cmake/strata_gpu_engine.cmake:6-13`, `engine/src/program/generate.cpp:8151-8159`）。
- serve loop で DFlash2 が実際に有効で、さらに `o.draft_auto` が真である必要があります。DFlash2 が起動時に設定できず MTP に fallback した場合は `use_df2` が false に戻るため、この upkeep は行われません（`engine/src/program/generate.cpp:13584-13615`）。
- `--draft auto` では CUDA/HIP 共通 engine の初期化が multi-GPU layer split と batch slots を許可しない旨を出し、その条件では DFlash2 を有効にしません。通常の `--draft dflash2`、MTP のみ、DFlash2 を使わない build でも変数による upkeep はありません（`engine/src/program/generate.cpp:8266-8276`）。
- リクエスト単位で `--draft auto` の選択が行われ、選択 drafterが DFlash2 ならアイドル MTP を `prefill` し、MTP ならアイドル DFlash2 に verifier tap を渡して `context_async` します。選択自体は request の `draft` または `--draft-rule` によって決まり、この環境変数は選択を上書きしません（`engine/src/program/generate.cpp:18982-19005, 23089-23103`）。
- upkeep は merged window では実行されません（`engine/src/program/generate.cpp:23091-23093`）。

## 実行時の詳細

設定値は serve loop の初期化で初めて該当行に到達したときに読み、`static const` に保持します。以降のリクエストでは再読込しないため、プロセス実行中に環境を変更しても反映されません。CLI 引数や他の環境変数からこの bool を上書きする処理はありません（`engine/src/program/generate.cpp:16397-16419`）。

upkeep が有効なら、各非 merged window の commit 後に、使われていない側の drafter の状態を更新します。DFlash2 側は非同期 `context_async` で tap rows と位置を記録して context を進め、MTP 側は `prefill` します。次の window が verifier の tap / residual rows を書き換える前に `keep_sync()` が保留中の DFlash2 stream と MTP stream を待ちます。またリクエスト終了時にも保留を待ちます（`engine/src/program/generate.cpp:21756-21765, 22803-22808, 23087-23103, 23223-23227`; `engine/src/core/dflash2.cpp:1145-1167`）。`STRATA_DRAFT_KEEP` を設定して変換値が 0 の場合、この upkeep 呼び出しとその wait は登録されません。次にアイドルだった drafter を選ぶリクエストでの再同期・再初期化の結果は、このスイッチの分岐だけからは保証できません。

## ログと測定値

この変数専用のログや警告はありません。upkeep を実行して `context_async` または MTP `prefill` が失敗すると、その場で stdout に `ERR <err>` を出して request 処理から `return 1` します。upkeep を待つ `keep_sync()` の失敗も同じ形式で `ERR <err>` を出します。DFlash2 の `context_async` は行数が範囲外なら `dflash2: context_async rows out of range` を返し、stream 同期失敗時は CUDA error を含む文字列を返します（`engine/src/program/generate.cpp:23095-23100, 22808, 23226`; `engine/src/core/dflash2.cpp:1145-1167`）。

`STRATA_DRAFT_LOG` が設定され、DFlash2 が有効なら stderr に request ごとの `strata draft: ... keep_ms=...` 行を出します。これは別変数によるログで、`STRATA_DRAFT_KEEP` の値や理由は表示しません。upkeep を止めた場合、当該 upkeep に計上される `keep_ms` は 0 のままです（`engine/src/program/generate.cpp:16416-16417, 23236-23239`）。この変数に関する測定値は確認できません。

## 根拠

- 候補名の実読み取りと値の判定: `engine/src/program/generate.cpp:16417`
- build macro と DFlash2 初期化・fallback: `engine/cmake/strata_gpu_engine.cmake:6-13`, `engine/src/program/generate.cpp:8151-8159, 13584-13615`
- auto の drafter 選択: `engine/src/program/generate.cpp:18982-19005`
- commit 後の idle drafter upkeep と待機: `engine/src/program/generate.cpp:21756-21765, 22803-22808, 23087-23103, 23223-23227`
- DFlash2 の非同期 context 登録と待機: `engine/src/core/dflash2.cpp:1145-1167`
- upkeep の失敗表示と別変数による request log: `engine/src/program/generate.cpp:16416-16417, 23095-23100, 23226, 23236-23239`
