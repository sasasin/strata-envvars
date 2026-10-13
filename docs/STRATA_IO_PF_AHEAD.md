# `STRATA_IO_PF_AHEAD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

Linux のファイル層 I/O prefetch が有効なとき、ルーター先読みが予測した次の層の expert を I/O worker のキューへ入れるかを制御します。既定では予測 expert も先読みします。`0` を指定すると予測による先読みを止めますが、現層が必要とする expert の読み込みは止めません。

この変数単独で I/O prefetch を有効にはしません。起動側で `STRATA_IO_PREFETCH` が有効になり、`FileExpertSource::set_io_prefetch()` が成功して初めて値が読み取られます。

## 値と判定

`std::atoi(v) != 0` で判定します。文字列全体の検証はせず、`atoi` が先頭から数値として変換した結果が 0 かどうかだけを見ます。

| 値 | 判定 |
|---|---|
| 未設定 | `io_ahead_` の初期値 `true` を維持し、予測先読みを許可 |
| 空文字、`0`、`0abc`、数値に変換できない文字列 | `atoi` が 0 を返すため、予測先読みを停止 |
| `1`、`-1`、`2`、`1abc` | 変換結果が非 0 のため、予測先読みを許可 |

設定値は `set_io_prefetch()` の実行時にインスタンスの `io_ahead_` へ格納されます。通常の生成経路では起動時に一度設定され、その後の環境変更は既存インスタンスに反映されません。関数を同じインスタンスで再度呼び、変数を unset にした場合は、実装が既定値へ戻さず現在の `io_ahead_` を維持します。

## 有効になる条件

- `src/program/generate.cpp` で `STRATA_IO_PREFETCH` の `atoi` 結果が非 0 であること。
- Linux ビルドであること。`set_io_prefetch()` の実装は `__linux__` の場合だけ worker を作ります。Windows などでは同関数は実質 no-op です。
- mapped file tier であること。`base_` が null、ファイルパスが空、または unbuffered read が有効で `direct_` が空でない場合は I/O prefetch を開始せず、環境変数も読み取りません。
- `STRATA_IO_PF_AHEAD=0` が効くのは、ファイル層 I/O prefetch が起動した後の予測先読みです。予測先読みを行う `RouterLookahead` は、対象ソースが warm に対応し、`STRATA_LOOKAHEAD` が有効（未設定時は有効）、ルーター重みの条件を満たす場合などに初期化されます。初期化できない経路ではこの変数による予測キュー投入もありません。

## 実行時の詳細

起動側は `STRATA_IO_PREFETCH` が有効なら `src.set_io_prefetch(true, ...)` を呼びます。Linux mapped file tier で有効化できた場合、I/O worker が作られ、ファイルアクセス経路が有効になります。`STRATA_IO_PF_AHEAD` はこの初期化中に読み込まれます。

ルーター先読みの予測 expert は `FileExpertSource::warm()` に渡されます。ここでは `io_pf_` が有効で unbuffered read でなければ、`io_ahead_` が true の場合に限って expert を worker キューへ入れます。false の場合は予測をキューへ入れません。予測候補の warm stamp と件数はこの分岐より前に更新されますが、それだけでファイル読み込みは発生しません。

現層で必要な expert の `prefetch()` 経路は別です。`experts.bin` の page-cache fill 経路では、未キャッシュの必要 expert を `io_enqueue()` へ渡し、`io_ahead_` を参照しません。staging 経路でも現層分を `fill_many()` で処理します。したがって `STRATA_IO_PF_AHEAD=0` は予測先読みだけを止め、必要な expert の読み込みや `STRATA_IO_PREFETCH` 自体を無効化しません。

`docs/DETAILS.md` は `STRATA_IO_PF_AHEAD=0` を「demand reads のみ」と記述しています。そこで示される比較測定は `STRATA_IO_PF_STAGE` の条件別結果であり、この変数だけを切り替えた性能値は記載されていません。

## 根拠

- `include/strata/core/expert_source.hpp:717-728,824-833`: Linux mapped file tier の I/O prefetch と `io_ahead_` の既定値・用途。
- `src/program/generate.cpp:4667-4679`: `STRATA_IO_PREFETCH` を条件に有効化し、利用不可時に診断を出す起動経路。
- `src/core/expert_source.cpp:636-669`: Linux 条件、mapped/unbuffered の早期 return、環境変数の `atoi` 判定、worker 起動。
- `src/core/expert_source.cpp:2116-2155`: 予測 expert を `io_ahead_` に応じて worker キューへ入れる処理。
- `src/core/expert_source.cpp:1426-1483`: 現層で必要な expert の読み込みは `io_ahead_` によらず処理する経路。
- `src/program/generate.cpp:5488-5524`: routing-aware prefetch の初期化条件と `STRATA_LOOKAHEAD` の既定有効判定。
- `docs/DETAILS.md:225-232`: I/O prefetch の説明と `STRATA_IO_PF_AHEAD=0` の記述。性能測定は同節の `STRATA_IO_PF_STAGE` 比較。
