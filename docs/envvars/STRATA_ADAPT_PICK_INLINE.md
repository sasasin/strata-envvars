# `STRATA_ADAPT_PICK_INLINE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

arena を使う非同期 adaptive tier で、各 swap round の expert 選択処理 `a_pick()` を decode loop の tick 内で実行するか、job thread に送るかを決める。既定値は inline（decode loop 側）で、`0` にすると job thread 側になる。どちらも選択処理そのものは同じ `a_pick()` であり、この変数は adaptive tier の有効化、swap の選択規則、copy-in の場所を切り替えない（`engine/src/program/generate.cpp:15460-15467, 15537-15571, 15703-15729`）。

対象名の全参照は `engine/src/program/generate.cpp` のコメント 2 箇所と、実際の読み取り 1 箇所だけ。読み取りは同ファイル内のローカル helper `a_env` を介する。`terminal/data/settings-register.json:845-855` にも登録名と読み取り位置のメタデータがあるが、これは環境から値を読む実装ではない。

## 値と判定

`a_env(name, def)` は `getenv` の値が未設定または空文字なら `def` を返し、それ以外を `std::atoi` に渡す。対象の既定値は `1` で、その整数が `0` 以外なら inline が有効になる。`atoi` は文字列全体の厳密な数値検査ではなく、先頭の空白と符号を許容して数字の prefix を変換し、数字の後ろは無視する。数値に変換できない文字列は `0` になる。範囲 clamp はない（`engine/src/program/generate.cpp:15494-15502`）。

| 条件 | unset | inline になる設定値 | job thread になる設定値 |
|---|---|---|---|
| arena の非同期 adaptive tier が動作 | 既定 `1` | `1`, `-1`, `2`, `1tail`, ` 1`（`atoi` 結果が非ゼロ） | `0`, `0tail`, `false`, `true`, `  `（結果が 0。空文字は unset と同じく既定 1） |
| arena 以外、または非同期 tier が動作しない | 値を読み取る箇所自体は通るが `a_arena` が false なら `a_inline` は false | 該当なし | 選択処理自体がこの `a_inline` 分岐の対象外 |

大文字小文字の比較や厳密な文字列比較はない。たとえば `true` は真として扱われず `atoi` が 0 を返すため inline は無効、`1anything` は先頭の数字が変換されて有効になる（`engine/src/program/generate.cpp:15494-15500`）。

## 有効になる条件

- `srcp == &arena_src` であること。arena はモデルの expert を RAM arena から読む経路で、設定値が有効でも arena 以外では `a_inline` は false になる（`engine/src/program/generate.cpp:8898-8901, 15489-15502`）。
- 非同期 adaptive tier の job (`ajob`) が作られ、routing usage が空でないこと。生成箇所は `o.adapt_async || a_self`、`!drive.d.usage.empty()`、および `(src.complement_ready() && src.exchange_capacity() >= 2 * a_cap) || a_arena` の条件を満たす場合に限られる（`engine/src/program/generate.cpp:15503-15518`）。
- 手動で `--adapt-async 1` を指定する場合は `--serve` が必要で、adaptive tier（`--adapt-every` と `--adapt-swaps` がともに正）も必要。arena では layer split と `--pipeline-windows 2` は非同期 tier を無効化する。無効時は理由付きで `strata generate: --adapt-async 1 is off (%s): the blocking adaptive tier` が出るため、この変数は tier を再度有効にはしない（`engine/src/program/generate.cpp:11691-11732`）。
- `--adapt-async` を指定しない場合の自動選択 `a_self` は CUDA build、`--serve`、adaptive tier 有効、expert arena、単一 GPU、非 pipeline、非 batch、peer/remote expert tier なし、`STRATA_ADAPT_OVERLAP` 無効、`STRATA_ADAPT_FETCH` が有効でない、などの条件でのみ候補になる。`STRATA_ADAPT_ASYNC=0` も自動選択を止める。これは tier の起動条件であり、`STRATA_ADAPT_PICK_INLINE` 自体はこれらを変更しない（`engine/include/strata/core/adapt_async_default.hpp:35-60`, `engine/src/program/generate.cpp:11695-11716`）。
- 自動選択は HIP build では行われない（header の `cuda` は `!STRATA_USE_HIP` で設定）。HIP で明示的に非同期 tier を有効にした場合も、この inline 判定は同じ `a_arena` 条件下で使われる（`engine/src/program/generate.cpp:11702-11715, 11682-11690`）。

## 実行時の詳細

対象値は非同期 adaptive tier のローカル状態を初期化するときに一度 `getenv` で読み、`a_inline` に保持する。`static` cache ではないが、その serving 実行中の round ごとには再読込しない。実行中に環境を変更しても現在の `a_inline` には反映されず、新しい serving 実行で再評価される（`engine/src/program/generate.cpp:15494-15502`）。

`adapt_tick` が次の round を始める tick で、inline が有効ならそのスレッド上で `a_pick()` を呼び、選択時間を `a_pick_ms` に加算して copy-in 段階へ進む。無効なら `a_pick()` を job thread に post する。arena の round は copy-back と RAM 上の交換移動がなく、選択後は copy-in を行う構成である（`engine/src/program/generate.cpp:15460-15467, 15537-15571, 15703-15729, 15778-15821`）。

`--adapt-async` などの CLI 設定がこの値を上書きすることはない。CLI と他変数は非同期 tier 自体を起動するかを決め、対象変数は起動した arena tier 内の選択処理の実行スレッドだけを決める。`STRATA_ADAPT_ASYNC_WAIT` は copy 完了の待ち方、`STRATA_ADAPT_ASYNC_BATCH` は tick ごとの copy 数を別々に決める（`engine/src/program/generate.cpp:15500-15502, 15778-15795`）。

## ログと測定値

arena の非同期 tier が存在すると、累積統計行に ` (arena, copy-in only, batch %zu, wait %d, pick %s %.2f ms/round)` が付く。`pick` は `inline` または `on the job` と表示される。対象変数が既定値のままでもこの表示は出るが、`ajob` が作られない場合は表示されない（`engine/src/program/generate.cpp:23704-23713`）。

この変数の効果を比較する測定値は、現行ソースおよび `docs/DETAILS.md` で確認できなかったため記載しない。

## 根拠

- 全参照と実読み取り、helper の既定値・変換、arena 限定: `engine/src/program/generate.cpp:15460-15502`
- 選択処理と inline/job thread の分岐: `engine/src/program/generate.cpp:15537-15571, 15703-15729`
- async tier の生成条件とログ: `engine/src/program/generate.cpp:15503-15518, 23704-23713`
- `--adapt-async` と自動選択の適用条件: `engine/src/program/generate.cpp:11691-11732`, `engine/include/strata/core/adapt_async_default.hpp:35-60`
- 候補メタデータ（環境読み取り実装ではない）: `terminal/data/settings-register.json:845-855`
