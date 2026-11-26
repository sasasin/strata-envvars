# `STRATA_MTP_SIDE_STREAM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

HIP build で MTP drafter を読み込むとき、`side_` という非ブロッキング stream を作るかどうかを指定する。未設定時は GPU 名が `gfx103` で始まる場合だけ作成し、この変数に非空値を設定するとその既定判定を上書きする。CUDA build では `side_` とイベントを無条件に作成する別分岐に入り、この変数は読まれない。Metal の MTP load は Metal engine を呼び出して先に戻るため、この変数を読み取らない（`engine/src/core/mtp.cpp:345-355,646-671`）。

## 値と判定

HIP の `MtpDrafter::load` は `std::getenv` の結果が null でなく、かつ先頭文字が NUL でない場合に `std::atoi(v) != 0` を既定判定へ代入する。空文字は未設定と同じ扱いで、gfx103 系の自動判定を保つ。非空値は整数として全体検証されず、`atoi` が読む先頭の数値部分が 0 かどうかで判定される（`engine/src/core/mtp.cpp:661-667`）。

| 条件 | unset / 空文字 | stream を作る値の例 | stream を作らない値の例 |
| --- | --- | --- | --- |
| HIP build、デバイス名が `gfx103` で始まる | 作成 | `1`, `2`, `-1`, `1junk` | `0`, `-0`, `true`, `junk`, ` 0` |
| HIP build、デバイス名が `gfx103` で始まらない、またはデバイス情報取得に失敗 | 作成しない | `1`, `2`, `-1`, `1junk` | `0`, `-0`, `true`, `junk`, ` 0` |
| CUDA build | 変数を読まず、stream とイベントを作成 | 該当なし | 該当なし |
| Metal MTP load | 変数を読まず Metal engine に委譲 | 該当なし | 該当なし |

先頭の空白や符号は `atoi` の変換規則に従い、数値の後ろは判定に使われない。したがって ` 1tail` は非ゼロ、` 0tail` はゼロとして扱われる。`true` / `false` の文字列比較はなく、どちらも変換結果は 0 になる。数値の後ろを含む全体検査、範囲チェック、clamp、無効文字列の警告や fallback 処理はない。`atoi` の整数範囲外入力について、この実装に安全な境界処理はない（同 `:666`）。

## 有効になる条件

- HIP build で、MTP drafter の `MtpDrafter::load` が呼ばれること。通常の `generate` 経路では `--mtp` が設定され、`--spec T` が 2 以上であることが前提で、`--spec` が 2 未満なら `--mtp` は警告付きで無効化される（`engine/src/program/generate.cpp:8243-8264`）。
- 対象の load が HIP 分岐へ到達すること。gfx103 系かどうかは現在の device を問い合わせ、`gcnArchName` の先頭 6 文字を `gfx103` と比較する。device 選択またはプロパティ取得に失敗した場合、既定値は false になる。非空の変数値はこの判定を上書きする（`engine/src/core/mtp.cpp:661-667`）。
- build が CUDA の場合、この変数による制御はない。CUDA 分岐は `side_` に加えて shared-expert 用 event も作成する（同 `:647-653`）。
- HIP では shared expert の枝分かれが compile-time に無効 (`branch_on == false`) なので、MTP の通常・batch 計算はこの `side_` に shared-expert 処理を送らない（同 `:1391-1407,2537-2553`）。この変数が制御するのは stream の作成有無であり、別の環境変数や CLI 引数による side stream 利用への切り替えはない。

## 実行時の詳細

変数は `MtpDrafter::load` の stream 初期化箇所で、その load ごとに読み取られる。`static` cache はなく、MTP drafter が複数作成される batch 経路では各 drafter の load で評価される（`engine/src/core/mtp.cpp:345-346,661-667`; `engine/src/program/generate.cpp:8351-8367`）。したがって、同一プロセス内で環境を変更できる場合、後続の load は新しい値を読む。既に作成した drafter の stream 状態は変わらない。

HIP では自動判定が true か、明示値の `atoi` 結果が非ゼロの場合に `cudaStreamCreateWithFlags(&side_, cudaStreamNonBlocking)` を呼ぶ。失敗すると `err` に `mtp: streams` を設定し、load は false を返す。false 判定ならこの stream 作成呼び出しを省略する。作成された stream は `MtpDrafter` の破棄時に `cudaStreamDestroy` される（`engine/src/core/mtp.cpp:667-670,219-242`）。

HIP 計算箇所では `branch_on` が false で、通常経路の shared expert は `cs` を使い、batch 経路も `use_branch` が false になる。そのため HIP 側でこの stream に計算や event を enqueue する箇所は確認できない（同 `:1391-1418,2537-2565`）。CUDA build は変数を読み取らず、通常経路・batch 経路とも shared-expert branch で `side_` を使う場合がある（同 `:647-653,1400-1418,2545-2565`）。

## ログと測定値

この変数の値や gfx103 判定について、Strata は専用ログを出さない。HIP の stream 作成失敗時は `MtpDrafter::load` が `mtp: streams` を返し、通常の `generate` 経路は `strata generate: <error>...` を stderr に出して終了コード 1 で戻る。batch slot 経路では `strata generate: batch MTP slot <番号>: <error>...` を stderr に出して終了コード 1 で戻る（`engine/src/core/mtp.cpp:667-670`; `engine/src/program/generate.cpp:8264,8363-8367`）。

ソースコメントには、RX 6800・Windows・`STRATA_HIP_PROMPT_F16=1`・約 7.9K token の prompt で、stream あり 798–808 tok/s、なし 584–596 tok/s とする観測が記されている（`engine/src/core/mtp.cpp:655-660`）。これはコメントに記録された測定であり、この調査では再測定していない。HIP のコード経路から確認できるのは stream の作成・破棄までで、Strata の MTP 計算がこの stream に投入される経路は見つからなかったため、この測定の仕組みや一般的な性能効果は断定しない。

## 根拠

- `engine/src/core/mtp.cpp:345-355` — Metal load の早期 return と共通 MTP load。
- `engine/src/core/mtp.cpp:647-671` — CUDA/HIP build 分岐、HIP の gfx103 判定、環境値変換、stream 作成と失敗。
- `engine/src/core/mtp.cpp:219-242` — `side_` の破棄。
- `engine/src/core/mtp.cpp:1391-1418,2537-2565` — 通常・batch MTP の HIP shared-expert branch 抑止と stream 使用条件。
- `engine/src/program/generate.cpp:8243-8264,8351-8367` — `--spec` 条件、通常 load と batch slot load、失敗時のログ・終了。
