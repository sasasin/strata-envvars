# `STRATA_IO_PF_AHEAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux の `FileExpertSource` の I/O prefetch が有効な間に、ルーター予測で先の層の expert を I/O worker queue に入れるかを制御する。既定は有効。`0` にすると予測分の先読み queue への投入を止めるが、現在の層で必要になった expert の demand 読み取りは止めない。読み取りと設定は `FileExpertSource::set_io_prefetch()`、予測 queue への投入は `FileExpertSource::warm()` と `warm_scored()` が行う（`engine/include/strata/core/expert_source.hpp:1222-1231`, `engine/src/core/expert_source.cpp:1228-1229,1261-1289,3467-3489`）。

## 値と判定

Linux の `set_io_prefetch(true, ...)` 内で `std::getenv()` が非 null の場合に `std::atoi(v) != 0` を代入する。未設定ならメンバー初期値 `true` が維持される。空文字は設定済みだが `atoi` の結果は 0 なので無効。数値の先頭部分を整数変換するため、`1`、`+1`、` 1tail`、`1tail`、`-1` は有効、`0`、`0tail`、`true`、`false`、空文字、数値で始まらない文字列は無効となる。全体一致や範囲検査はしない（`engine/include/strata/core/expert_source.hpp:1225`, `engine/src/core/expert_source.cpp:1284`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux で I/O prefetch の開始処理が進む場合 | `io_ahead_` の初期値 `true` | `atoi` 結果が非 0（例: `1`, `-1`, `1tail`） | `atoi` 結果が 0（例: `0`, 空文字, `true`, `0tail`） |
| 非 Linux build、または Linux でも開始条件を満たさない場合 | 当該呼び出しでは環境変数を読まない | 判定されない | 判定されない |

## 有効になる条件

- `--mmap-experts` 等で選ばれた `FileExpertSource` のファイル階層が使われ、`set_io_prefetch(true, ...)` が呼ばれる必要がある。初期化時は Linux file-tier 既定値、または `STRATA_IO_PREFETCH` の非 0 値が開始条件となる（`engine/src/program/generate.cpp:8621-8647,8688-8703`）。
- `set_io_prefetch()` は Linux でのみ I/O worker の準備を行う。`on` が false、mapping がない、path が空、unbuffered reader、またはファイルを開けない場合は先に戻るため、この環境変数の判定は行われず、I/O prefetch も開始されない（`engine/src/core/expert_source.cpp:1261-1284,1310-1312`）。
- 既定で I/O prefetch が始まるのは Linux のみ。GGUF をその場で読む file tier は `linux_io_defaults()` が true、`experts.bin` は page-cache の余裕率が 55% 以上の場合に既定有効となる。明示的な `STRATA_IO_PREFETCH` があればこの既定条件とは別に評価される（`engine/include/strata/core/expert_source.hpp:1082-1093`, `engine/src/program/generate.cpp:8693-8703`）。
- 予測読み取りには router lookahead が予測を出すことも必要。lookahead 自体は source が warm 可能などの条件で開始し、`STRATA_LOOKAHEAD` が 0 なら起動しない（`engine/src/program/generate.cpp:10288-10327`, `engine/src/core/expert_source.cpp:3789-3790`）。
- decode gate が閉じている間は予測読み取りも実行されない。`warm_scored()` は gate と `io_ahead_` の両方を確認する（`engine/src/core/expert_source.cpp:1228-1229`, `engine/include/strata/core/expert_source.hpp:1066-1080`）。
- server 実行では、全 expert が GPU cache に収まって Linux 既定で有効化した I/O prefetch を停止することがある。その既定の再開時には `set_io_prefetch(true, ...)` が再度呼ばれ、環境変数も再読込される。明示的に `STRATA_IO_PREFETCH` で有効にした場合は、この既定値専用の停止条件には該当しない（`engine/src/program/generate.cpp:10251-10285,10341-10369`）。

## 実行時の詳細

`io_ahead_` は `FileExpertSource` のメンバーで初期値が true。Linux の `set_io_prefetch(true, ...)` は、file descriptor の準備後に環境変数を読み、その後 worker threads を起動する。unset は初期値を保ち、値を評価するのは関数呼び出し時であって、関数内 static cache ではない（`engine/include/strata/core/expert_source.hpp:1222-1231`, `engine/src/core/expert_source.cpp:1261-1284,1305-1309`）。

予測された expert は `warm()` から `io_enqueue(..., true)` に進むのが `io_ahead_ == true` の場合だけ。false の場合はこの予測 queue に入らない。`warm_scored()` も false の場合は通常の `warm()` へ戻るが、同じ判定によって予測 queue には入らない。一方、現在の層で必要な expert の `prefetch()` は `io_fill_` 経路で `io_enqueue(layer, e)` を行い、`io_ahead_` を条件にしないため demand pread は継続する（`engine/src/core/expert_source.cpp:1228-1229,2449-2467,3485-3490`）。値はこの queue 制御だけを変える実装で、expert の選択結果や生成 token を変える処理はここにはない。

## ログと測定値

この変数専用の有効・無効ログやエラー文言はない。I/O prefetch が有効で OS I/O サンプルを取得できる場合、server は request ごとの `io prefetch: ... read ahead ...` 統計を stderr に出すが、これは読み取り量などの集計であり、この変数の設定値を表示するログではない（`engine/src/program/generate.cpp:23831-23857`）。設定による性能値は、対象変数単独の条件を示す Strata 資料から確認できないため記載しない。

## 根拠

- 初期値と状態: `engine/include/strata/core/expert_source.hpp:1222-1231`
- 環境値の読み取りと Linux 限定処理: `engine/src/core/expert_source.cpp:1261-1289,1310-1312`
- 予測 queue と demand queue: `engine/src/core/expert_source.cpp:1228-1229,2449-2467,3467-3489`
- Linux file-tier の有効化条件と server の停止・再開: `engine/include/strata/core/expert_source.hpp:1082-1093`, `engine/src/program/generate.cpp:8688-8703,10251-10285,10341-10369`
- request 単位の I/O 統計ログ: `engine/src/program/generate.cpp:23831-23857`
