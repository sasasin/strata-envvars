# `STRATA_SPEC_ADAPT_WARM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の適応 expert tier について、投機実行の開始後何回の verify round まで、通常より短い間隔で GPU resident expert を入れ替えるかを指定する。値は `STRATA_SPEC_ADAPT_EVERY` が指定する短い間隔と組で使われる。対象期間中の間隔は `STRATA_SPEC_ADAPT_EVERY`、期間後は `--adapt-every`（省略時 4）の間隔になる。変数自身は適応 tier の有効化や入れ替え数を指定しない。`engine/src/program/generate.cpp:1045-1051,5104-5109,22048-22059`。

Strata は HIP と Metal 以外の engine build で CUDA の全可視 GPU が同じ compute capability である場合にカード別の起動時既定値を適用し、その中のこの値の既定値設定は sm_86 かつ明示的な `STRATA_SPEC_ADAPT_SM86` opt-in がある場合だけ行う。ユーザーが値を明示すれば、共通の `--serve` 処理側の条件を満たす他の GPU/backend でも読み取られる。`engine/src/program/generate.cpp:4421-4449`、`engine/src/core/nv_defaults.cpp:328-347`、`engine/src/program/generate.cpp:5104-5109`。

## 値と判定

環境値の読み取りは `--adapt-every` を CLI で指定せず、`--spec >= 2` かつ `adapt_every > 0` のときに限られる。`STRATA_SPEC_ADAPT_EVERY` は `atoi`、本変数は `atoll` で変換し、両方とも変換後の条件だけを確認する。文字列全体の数値検証、空白の拒否、後続文字の検査はない。`engine/src/program/generate.cpp:4058,5104-5109`。

| 条件 | 未設定 | 有効になる値の例 | 無効になる値の例 |
| --- | --- | --- | --- |
| `--adapt-every` 未指定、`--spec >= 2`、`adapt_every > 0` | `atoll` の入力を 0 とみなし無効。sm_86 の opt-in 条件を満たす起動では、前段が未設定値を `200` に補う | 変換値が正数（例: `200`, `+200`, ` 200`, `200tail`） | 空文字、`0`, `-1`, `none`, `tail200` は変換値が正数にならず無効 |
| CLI `--adapt-every` を指定、または `--spec < 2` / `adapt_every <= 0` | 環境値を読み取らない | なし | 環境値は指定してもこの設定には使われない |

本変数で有効になるには `atoll` の結果が `> 0` である必要がある。加えて `STRATA_SPEC_ADAPT_EVERY` の `atoi` 結果 `n` が `> 0` かつ現在の `o.adapt_every` より小さい必要がある。条件に合わない場合、warm-up 設定は行われず通常の間隔を使う。値のオーバーフローを検出する処理や上限 clamp はない。`engine/src/program/generate.cpp:5104-5109`。

sm_86 の既定値処理では `STRATA_SPEC_ADAPT_WARM` と `STRATA_SPEC_ADAPT_EVERY` を個別に確認し、`getenv(...) != nullptr` なら値の内容に関係なくユーザー設定を保持する。したがって空文字も上書きされず、その場合 `atoll("")` は 0 となり warm-up は有効にならない。未設定の値はそれぞれ `200` と `2` に設定される。`engine/src/core/nv_defaults.cpp:339-346`。

## 有効になる条件

- 自動で既定値が入るのは HIP と Metal 以外の build で GPU 数が取得でき、可視 GPU がすべて同じ compute capability で、かつその capability が sm_86 の場合。混在 compute capability の複数 GPU では `apply_spec_adapt_default` が呼ばれず、HIP / Metal build にもこの既定値処理はない。`engine/src/program/generate.cpp:4421-4450`。
- 自動既定値にはさらに `STRATA_SPEC_ADAPT_SM86` の先頭文字が `'1'` であることが必要。未設定、空文字、`0`、`true` は opt-in にならず、`1tail` は opt-in になる。`STRATA_SM86_PERF` の先頭文字が `'0'` の場合は既定値の設定を止める。`engine/src/core/nv_defaults.cpp:15-18,335-347`。
- 環境値の読み取りには `--adapt-every` が未指定、`--spec >= 2`、`adapt_every > 0` が必要。`--adapt-every` を指定すると、本変数と `STRATA_SPEC_ADAPT_EVERY` の読み取りをまとめてスキップする。`engine/src/program/generate.cpp:4058,5104-5109`。
- これは適応 tier の起動条件を満たす場合だけ入れ替え周期に影響する。serve 側では usage 集計が有効で、`o.adapt_every > 0`、保留中の処理がなく、交換待ちでないときに適応処理を開始する。適応 tier 自体は `adapt_every` と `adapt_swaps` が正である場合に有効化される。`engine/src/program/generate.cpp:11785,22048-22059`。

## 実行時の詳細

CUDA のカード別既定値設定は、同一 capability の GPU を確認した後、`nv_defaults.cpp` の `apply_spec_adapt_default` を呼ぶ。ここで環境変数を読むのは起動時で、未設定値はプロセス環境に補われる（Windows は `_putenv_s`、それ以外は `setenv(..., 0)`）。後段の `generate.cpp` は CLI option の検証後に本変数と `STRATA_SPEC_ADAPT_EVERY` を一度読み、変換値を `o.adapt_warm_rounds` と `o.adapt_warm_every` に保持する。リクエストごとの再読み取りや動作中の環境変更反映はない。`engine/src/program/generate.cpp:4428-4449,5104-5109`、`engine/src/core/nv_defaults.cpp:328-347`。

`adapt_iv(rounds)` は `rounds < adapt_warm_rounds` の間だけ `adapt_warm_every` を返し、その後 `adapt_every` に戻る。`--serve` の blocking tier は、round がこの周期に達し、usage が存在し、pending が空で交換待ちでない場合に適応処理を開始する。呼び出し側では最後の window や別の適応 job 実行中にはこの関数を呼ばない。従って本変数は入れ替え頻度の初期区間を決めるもので、expert 選択基準や入れ替え数そのものは変えない。`engine/src/program/generate.cpp:1049-1051,22048-22059,22463-22466`。

warm-up の期間単位は verify round であり、秒数や生成 token 数ではない。`STRATA_SPEC_ADAPT_EVERY` が正で `o.adapt_every` より小さい場合のみ短い周期として採用される。後段で coverage に応じて通常の `adapt_every` が変わるコードもあるため、ここで設定した warm-up 周期がその後の通常周期と比較し直されることはない。`engine/src/program/generate.cpp:5104-5109,14943-14964`。

## ログと測定値

本変数の値や warm-up 周期を直接表示するログは確認できない。serve の終了時に usage 集計がある場合は、適応 tier の入れ替え総数と `o.adapt_every` を「every N rounds」として出力するが、これは通常周期の値であり warm-up の周期や期間を示さない。`engine/src/program/generate.cpp:25314-25316`。

この変数による失敗専用経路や timeout は見つからない。blocking tier の `adapt` が失敗した場合は呼び出し元が `die("an adaptive refill failed")` に進むが、本変数の値を個別に示すエラーではない。`engine/src/program/generate.cpp:22463-22466`。

`docs/DETAILS.md` にこの変数や warm-up 周期についての説明は見つからなかった。性能値は記載しない。

## 根拠

- `engine/src/core/nv_defaults.cpp:15-18,328-347` — sm_86 opt-in、カード別既定値、および値が設定済みかの判定。
- `engine/src/program/generate.cpp:1045-1051,4058,4428-4449,5104-5109` — CLI 優先、読み取り条件、変換方法と適用範囲。
- `engine/src/program/generate.cpp:22048-22059,22463-22466,25314-25316` — serve の周期判定、呼び出しと観測可能な出力。
