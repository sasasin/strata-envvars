# `STRATA_P4_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

層分割した pipelined batch の stage window の開始・完了イベントを、指定ファイルへ記録する診断用スイッチである。Strata の `PipeProbe` が環境から値を読み、ファイルを開けた場合に `L`（launch）と `D`（done）の行を書き込む。モデル計算、生成 token、stage 選択を切り替える設定ではなく、観測用 I/O を追加する。通常の実行では未設定なら probe は無効である。`engine/include/strata/program/pipe_probe.hpp:31-46,81-102`、生成経路での probe の生成は `engine/src/program/generate.cpp:18029-18034`。

## 値と判定

コンストラクターで `std::getenv` を一度呼び、値を数値や真偽値として parse せず、ファイルパスとして扱う。未設定なら trace ファイルを開かない。設定されていて値が空文字、または文字列全体がちょうど `1` の場合は `strata-p4-trace.csv` を使う。それ以外は値全体をパスとして `fopen(path, "w")` に渡す。したがって `0`、`true`、空白を含む値、`1x` もそのままパスであり、`1` の判定は大文字小文字や先頭文字だけの比較ではない。数値境界や負値の規則はない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP の pipelined batch 経路（この読み取り箇所には backend 別の値判定なし） | trace を開かない | 空文字または `1` は既定パス、`/tmp/p4.log` はそのパス | パスとして開けない値。`0`、`true`、`1x` は「無効値」ではなく、それぞれの名前のパスを開こうとする |

パスを開けない場合、`trace_` は null のままとなり、stderr に `strata p4: cannot write the trace <path>` を出す。これは処理失敗として返されず、trace 出力だけが行われない。`STRATA_P4_TIMING` が別途有効なら timing 計測は継続する。`engine/include/strata/program/pipe_probe.hpp:33-40,46`。

## 有効になる条件

- `generate.cpp` の pipelined batch 経路が動くこと。コード上の条件は `o.batch > 0`、`o.batch_groups > 1`、`n_pipe > 1` で、`n_pipe` は layer split の `stages.size() + 1`。従って batch groups が複数でも layer split がなければこの pipelined 経路にはならない。`engine/src/program/generate.cpp:17529-17533`。
- `PipeProbe` の生成時に変数が設定されていること。値はそのコンストラクターで読み込まれ、パスもそこで一度開く。probe は pipelined batch 処理の初期化時に作られ、実行中に環境変数を再読込しない。変更を反映するには、少なくとも probe の再生成が必要である。`engine/src/program/generate.cpp:18029-18034`、`engine/include/strata/program/pipe_probe.hpp:31-40`。
- ファイルを開けること。開けないと警告後も batch は続くが、`STRATA_P4_TRACE` によるイベント記録は無効になる。ファイルは `"w"` で開くため、同じパスに既存ファイルがあれば開いた時点で切り詰められる。`engine/include/strata/program/pipe_probe.hpp:36-40`。
- OS、CUDA/HIP の違い、GPU 世代、CLI による値の優先順位をこの読み取り箇所は設けていない。対象の `generate.cpp` 経路は CUDA/HIP engine の pipelined batch であり、経路が選ばれる条件は上記の batch/layer-split 条件による。

## 実行時の詳細

`PipeProbe` は `STRATA_P4_TRACE` の値を受けて出力ファイルを開き、バッファリングを無効化する。各 stage の batch launch 成功後に `L <stage> <steady-clock の時刻（µs）> <group>`、完了時に `D <stage> <時刻（µs）> 0` を1行出力する。stage と group はコード上 0 始まりで、時刻は `steady_clock` の epoch からのマイクロ秒値である。ヘッダー行はなく、各行は `fprintf` され、無バッファ設定のため都度 flush される。終了時にファイルを閉じる。`engine/include/strata/program/pipe_probe.hpp:36-42,81-102`、イベント呼び出しは `engine/src/program/generate.cpp:18064-18068,18291-18306`。

trace が開けていると `on()` が true になり、trace 記録に必要な時刻取得と probe のイベント処理が有効になる。一方、stderr の詳細 timing summary は `STRATA_P4_TIMING` が設定されているときだけ `flush()` が出す。`STRATA_P4_TRACE` 単独では `flush()` は即時 return し、timing summary を出さない。pipelined group が実行されない場合はイベント行も発生しない。`engine/include/strata/program/pipe_probe.hpp:46-49,104-120`、呼出し・summary のタイミングは `engine/src/program/generate.cpp:18358-18382`。

## ログと測定値

出力先を開けないときの stderr 文言は `strata p4: cannot write the trace %s\n`。trace 行はファイルへ出力され、Strata は trace 専用の成功ログを出さない。`STRATA_P4_TRACE` 自体に対応する測定値はなく、数値集計の stderr summary は別変数 `STRATA_P4_TIMING` により制御される。`engine/include/strata/program/pipe_probe.hpp:33-40,81-102,104-120`。

## 根拠

- `engine/include/strata/program/pipe_probe.hpp:31-49` — 値の読み取り、既定パス、ファイル open、失敗時警告、probe 有効判定。
- `engine/include/strata/program/pipe_probe.hpp:81-102` — イベント行の形式、時刻と出力。
- `engine/include/strata/program/pipe_probe.hpp:104-120` — timing summary が `timing_` 有効時だけ出ること。
- `engine/src/program/generate.cpp:17529-17533` — pipelined batch の条件と stage 数。
- `engine/src/program/generate.cpp:18029-18034,18064-18068,18291-18306,18358-18382` — probe の生成、イベント呼び出し、集計区間と flush。
