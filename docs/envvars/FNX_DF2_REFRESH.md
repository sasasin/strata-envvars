# `FNX_DF2_REFRESH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

DFlash2 を使う sFNX の複数 lane バッチデコードで、現在の window に割り当てる draft が 0 個の lane について、DFlash2 の次の drafter round まで何 window 見送るかを指定する。見送る window の tap rows は `df2_defer` に渡され、lane の host ring に保留される。指定値は予測器が各 lane に割り当てる draft 数や DFlash2 の候補数を変えず、draft がない lane の DFlash2 呼び出し頻度だけに作用する（`engine/src/split/src/batch.cpp:489-510`, `engine/src/split/src/engine.hpp:126-129`）。

この処理は `BatchDecoder::draft_next` が `mode_ == BatchDrafts::mtp` かつ `e_.df2_on()` のときだけ `draft_df2` に進む経路にある。sFNX サーバーでは `--batch` が 1 より大きく、`FNX_BATCH_DRAFTS` が off でないときにバッチデコーダーが作られる。さらに DFlash2 が選択・attach 済みである必要がある（`engine/src/split/src/batch.cpp:262-266,330-332`, `engine/src/split/tools/sfnx.cpp:65-68,107-115,448-458`, `engine/src/split/src/engine.hpp:115-120`）。

## 値と判定

`env_int("FNX_DF2_REFRESH", 8)` は環境変数の文字列全体を base 10 の符号付き整数として `strtoll` で解析する。先頭の `+` / `-` は許されるが、数字が 1 文字以上必要で、後続文字・空白・範囲外整数は許されない。未設定なら `8`。明示的な空文字は設定済みとして解析され、整数ではないため例外になる。値に `0` の特別な意味はなく、ゼロ以外も正負を問わず整数なら parse を通る。結果は追加検査なしに `int` へ cast されるため、`int` の表現範囲外の `long long` 値については移植可能な値や動作を断定できない。clamp や fallback はない（`engine/src/split/src/env.hpp:15-22,33-40`, `engine/src/split/src/batch.cpp:492`）。

| 条件 | unset | parse を通る例 | parse で拒否される例 |
|---|---:|---|---|
| `draft_df2` に初めて入る呼び出し | `8` | `0`, `1`, `+8`, `-2` | 空文字, `0anything`, ` 8`, `8 `, `1.0`, `true`, `9223372036854775808` |

parse 後の値 `refresh` は `++L.idle < refresh` の比較に使われる。したがって `refresh <= 1` なら idle lane の見送り条件は成立せず、drafter は毎 window 実行される。正の値 `N > 1` なら `N-1` 回見送った後、`N` 回目に実行する。負値や 0 も不正値扱い・既定値への置換にはならず、同じ比較により見送りなしとなる（`engine/src/split/src/batch.cpp:501-510`）。

## 有効になる条件

- sFNX がサーバーモードで起動している（`engine/src/split/tools/sfnx.cpp:73-82,107-108`）。
- `--batch` が 2 以上で、かつ `FNX_BATCH_DRAFTS` が off でないため、`BatchDecoder` が作られている（`engine/src/split/tools/sfnx.cpp:448-458`）。
- 実行時に `--draft dflash2` または `FNX_DRAFT=dflash2` で DFlash2 が選ばれて attach されている。MTP draft layer が attach された場合、`e_.df2_on()` は false でこの変数の読み取り箇所に進まない（`engine/src/split/tools/sfnx.cpp:67,86-87,107-114,1125-1133`, `engine/src/split/src/engine.hpp:119-120`, `engine/src/split/src/batch.cpp:265-266`）。
- build macro `FNX_DF2` が有効なビルドであること。無効なビルドでは `df2_attach` が `this engine was built without DFlash2` を投げるため、DFlash2 を使う実行経路に進めない（`engine/src/split/src/engine.cu:1222-1224,1231-1248`）。
- window 後も生成中の lane があり、その lane の計画 draft 数 `plan[g]` が 0 であること。`plan[g] > 0` の lane はこの閾値判定を通らない（`engine/src/split/src/batch.cpp:496-503`）。
- さらに `FNX_DF2_DEFER` が 0 でないこと。既定値は 1 で、0 の場合は `refresh` と無関係に毎回 `df2_draft` に進む。`FNX_DF2_DEFER` も `env_int` による整数判定である（`engine/src/split/src/batch.cpp:493,501-510`, `engine/src/split/src/env.hpp:33-40`）。

OS/backend 別の値判定分岐はこの読み取り箇所にはない。この値は CUDA/HIP のどちらかで有効化されるのではなく、DFlash2 対応ビルドと上記の実行条件によって適用される（`engine/src/split/src/engine.cu:1222-1248`）。

## 実行時の詳細

値は `BatchDecoder::draft_df2` に初めて入ったときに関数内 `static const int` として読み取られ、そのプロセス内で以降キャッシュされる。環境変数をプロセス起動後に変更しても、初回読み取り後は反映されない。初回読み取りより前の変更は読み取り値に反映される。`FNX_DF2_DEFER` も同じ関数内 static で初回に読み取られる（`engine/src/split/src/batch.cpp:489-493`）。

各 lane の `idle` は `BatchLane::start` で 0 に初期化される。`defer` が有効で `plan[g] == 0` のとき、`idle` を増やし、増加後の値が `refresh` 未満なら `df2_defer(q)` によりその window の rows を保留し、drafter round を行わない。比較が成立しないときは `idle` を 0 に戻し、その lane の request を集める。対象 request が 1 件もなければ戻り、1 件以上あれば `e_.df2_draft(rq)` を呼び出す。したがって通常の既定値 8 では、draft 0 の状態が続く lane は 7 window 分を保留し、8 window 目に drafter round を実行する（`engine/src/split/src/batch.hpp:25-32`, `engine/src/split/src/batch.cpp:40-58,489-510`）。

見送られた rows は `Engine::df2_defer` が lane の host ring に記録する。次の drafter round は `df2_catch_up` で ring の保留範囲を取り込み、要求された位置まで追いついてから DFlash2 を実行する（`engine/src/split/src/engine_common.cu:1675-1697,1699-1720,1722-1746`）。

## ログと測定値

有効値を使った見送り・実行について `FNX_DF2_REFRESH` 専用の成功ログはない。バッチ診断の `FNX_BATCH_TRACE` は lane ごとの `plan` 等を stderr に出すが、refresh counter や defer の有無は出力しない（`engine/src/split/src/batch.cpp:317-329,501-510`）。

値が整数でない場合、helper は `FNX_DF2_REFRESH: '<値>' is not a whole number` 形式の `std::runtime_error` を投げる（`engine/src/split/src/env.hpp:33-40`）。sFNX のサーバーループでは例外が `fail` に渡り、stdout に `ERR <例外文>`、stderr に `sfnx: failed: <例外文>` を出して終了コード 1 で終了する（`engine/src/split/tools/sfnx.cpp:1094-1102,1160-1166`）。

## 根拠

- `engine/src/split/src/env.hpp:15-22,33-40` — 整数文字列全体の解析と未設定時 fallback、無効値の例外。
- `engine/src/split/src/batch.cpp:489-510` — refresh 値の cache、idle lane の見送りと DFlash2 呼び出し。
- `engine/src/split/src/batch.cpp:262-266,330-332` — MTP mode と DFlash2 attach の分岐。
- `engine/src/split/tools/sfnx.cpp:65-68,73-115,448-458,1125-1133` — サーバー引数、DFlash2 選択、バッチデコーダー生成、engine への attach。
- `engine/src/split/src/engine.hpp:115-129`、`engine/src/split/src/engine_common.cu:1675-1746` — DFlash2 状態、保留 tap の保存・次回利用と drafter 呼び出し。
