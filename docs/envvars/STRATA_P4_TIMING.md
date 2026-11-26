# `STRATA_P4_TIMING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

layer split 上で `--batch-groups` を複数グループ並行処理する経路の時間を計測し、バッチが idle になったときに stage ごとの統計を stderr に出す診断用スイッチ。`PipeProbe` が各 stage の window 時間・launch 間隔・完了後の gap、pump の時間、verdict 処理、in-flight 数、stage の idle / starved tick を集計する。値を読む箇所は `engine/include/strata/program/pipe_probe.hpp:31-40`、probe の生成と計測は `engine/src/program/generate.cpp:18029-18045`。

この変数で pipeline の有効化、stage の選択、token や出力値は切り替わらない。`timing_` は計測用分岐と時計読み取り・stderr 出力に使われ、生成や scheduling の選択条件には使われていない（`engine/include/strata/program/pipe_probe.hpp:46-48, 104-120`; `engine/src/program/generate.cpp:18035-45, 18360-81`）。

## 値と判定

コンストラクターで `std::getenv("STRATA_P4_TIMING") != nullptr` を一度評価する。値の文字列は parse せず、設定されているかだけを見る。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `PipeProbe` の生成時 | `timing_` は false | 空文字、`0`、`1`、`false`、その他の任意の文字列はすべて true | なし（環境変数が存在する場合） |

大文字小文字、空白、数値としての妥当性、文字列の全体・先頭文字は判定しない。unset の場合だけ false。CLI 引数や設定ファイルによる上書き・優先順位はこの読み取り箇所にはない。別変数 `STRATA_P4_TRACE` は probe の trace 出力を制御するが、`STRATA_P4_TIMING` の真偽を変更しない（`engine/include/strata/program/pipe_probe.hpp:31-40, 46-48`）。

## 有効になる条件

- 計測対象の処理は、`o.batch > 0`、`o.batch_groups > 1`、かつ `stages` が空でない layer split の pipelined group 経路（`n_pipe = stages.size() + 1`）である。`piped` が true の場合に `pump(true)` が呼ばれる（`engine/src/program/generate.cpp:17529-17533, 18410-18413`）。
- この変数自体の読み取りには OS・GPU backend・build macro・サーバー要求ごとの追加判定はない。実際に統計が出るには上記の pipeline が動き、少なくとも一つの group-step が完了して全処理が idle になる必要がある（`engine/src/program/generate.cpp:18360-18381`）。
- `STRATA_P4_TRACE` は独立した任意条件。これだけが設定されても `timing_` は有効にならず、この変数が unset のままなら `flush()` は timing summary を出さない（`engine/include/strata/program/pipe_probe.hpp:34-40, 104-107`）。

## 実行時の詳細

`PipeProbe p4` の生成時に値を読み、以後 `timing_` に保持するため、同じ probe の寿命中に環境を書き換えても反映されない。生成箇所は group pipeline の処理内にあり、リクエスト単位の読み直しや子プロセスへの転送はこの変数について実装されていない（`engine/src/program/generate.cpp:18029-18034`; `engine/include/strata/program/pipe_probe.hpp:31-40`）。

`timing_` が true のとき、pump ごとに stage busy 数・in-flight group 数と stage の free tick を記録し、stage の poll / 完了 / launch、最終 stage の verdict 処理を計時する。全 pipeline が idle で `bt_windows > 0` のとき、通常の `strata batch (pipelined, ...)` 行の直後に `p4.flush()` が統計を stderr に出し、カウンターを reset する（`engine/src/program/generate.cpp:18035-45, 18059-64, 18360-81`; `engine/include/strata/program/pipe_probe.hpp:60-67, 80-120`）。

`batch_poll` が負値を返す失敗経路では `ERR %s` を stdout に出して pump が false を返し、呼び出し元が `1` を返す。この経路では idle 時の `p4.flush()` に到達しない（`engine/src/program/generate.cpp:18059-63, 18410-13`）。

## ログと測定値

通常完了時に stderr へ、たとえば次の形式の行を出す。実数値は実行時集計であり、この調査では build・GPU 実行・測定をしていない。

```text
strata p4: pump ... ms/tick over ... ticks; stage-busy ... of ...; group wait ... ms;
strata p4:   s... windows ...  win ... ms  cycle ... ms  gap ... ms  busy ...%  launch ... ms
strata p4:   verdict work ... ms/window; inflight groups avg ... of ...
strata p4:   s... free ticks: with a group waiting ..., starved ...
```

これらの行は `timing_` が true のときだけ出る。環境変数が unset の場合と、完了 window がなく idle summary を通らない場合は出ない（`engine/include/strata/program/pipe_probe.hpp:104-120`; `engine/src/program/generate.cpp:18360-81`）。

## 根拠

- `engine/include/strata/program/pipe_probe.hpp:31-40` — 環境変数の存在判定と、独立する trace の読み取り。
- `engine/include/strata/program/pipe_probe.hpp:46-48, 60-67, 80-120` — probe の有効判定、計測条件、stderr 出力と reset。
- `engine/src/program/generate.cpp:17529-17533, 18029-18045` — pipelined batch-groups の条件、probe の生成と pump 内集計。
- `engine/src/program/generate.cpp:18059-18064, 18360-18381, 18410-18413` — poll 失敗、idle 時の flush、pump の呼び出し。
