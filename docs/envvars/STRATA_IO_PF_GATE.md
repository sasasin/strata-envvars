# `STRATA_IO_PF_GATE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux の `FileExpertSource` で I/O prefetch が動作するとき、decode 中の read-ahead と、decode 用 blob 読み込みの `pread` を page-cache 容量と read-ahead の有用度に応じて通す gate を有効にします。gate が閉じても decode のファイル読み込みを無効にはせず、閉じた `copy_from_files` 経路では `pread` を省いてマップ済みデータをコピーします。予測 read-ahead は `warm()` から gate 状態を見て投入を止めます。`FileExpertSource::set_io_prefetch()` と `gate_capacity()` が設定・制御箇所です（`engine/src/core/expert_source.cpp:1261-1312, 2329-2359, 3487-3501`; `engine/src/core/expert_source.cpp:1904-1921`）。

## 値と判定

I/O prefetch の初期化に入ると gate は既定で ON になり、環境変数が存在し、かつ空文字でなければ `std::atoi` の結果が 0 かどうかで上書きします。文字列全体や真偽語を検証せず、数値として読める先頭部分を `atoi` で変換します。したがって `1`、`2`、`-1`、`1tail` は ON、`0`、`0tail`、`true`、`false`、先頭が数値でない文字列は通常 `atoi` が 0 を返すため OFF です。空白の後の数値も `atoi` が読む範囲なら判定されます。空文字は上書きせず既定 ON のままです。この名前を読む直接参照は `set_io_prefetch()` のみで、名前を動的に渡す共通 helper や CLI 引数による上書き経路はありません。範囲外の数値文字列については変換結果を保証するコード上の検査がありません（`engine/src/core/expert_source.cpp:1299-1303`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux で I/O prefetch 初期化が成功 | ON | `atoi(value) != 0`（例: `1`, `2`, `-1`, `1tail`） | `atoi(value) == 0`（例: `0`, `0tail`, `true`, `false`, `garbage`） |
| 空文字、または初期化されない経路 | 空文字は既定を維持。初期化されない経路ではこの変数を読まない | — | — |

## 有効になる条件

- `generate` のファイル tier が I/O prefetch を選ぶ必要があります。`STRATA_IO_PREFETCH` が未設定または空文字なら Linux の既定判定に従い、明示値が `atoi` で非ゼロなら有効化を試みます。明示値が `0` なら gate の値にかかわらず I/O prefetch に入りません（`engine/src/program/generate.cpp:8688-8704`）。
- Linux 以外では `set_io_prefetch()` の Linux 実装がなく、gate は動作しません。同関数は Linux でのみ fd を開いて worker を起動し、Linux 以外は引数を未使用にします（`engine/src/core/expert_source.cpp:1261-1312`）。
- Linux でも mapped file tier が必要です。`set_io_prefetch(true, ...)` は `base_ == nullptr`、パスなし、または unbuffered 読み取り (`direct_` が空でない) なら戻り、gate を OFF にしたままです（`engine/src/core/expert_source.cpp:1261-1267`）。呼び出し元はこの場合、明示的に prefetch を要求していて既定経路でないとき `STRATA_IO_PREFETCH=1 is not available here ...` と stderr に出します（`engine/src/program/generate.cpp:8701-8724`）。
- `STRATA_IO_PREFETCH` が未設定・空文字の場合の Linux 既定は GGUF を read-in-place する file tier、または page cache に experts.bin 全体の少なくとも 55% 分の余裕がある experts.bin tier です。後者の閾値判定は `linux_io_defaults()` にあります。明示 `STRATA_IO_PREFETCH=1` は既定判定を上書きして試行します（`engine/include/strata/core/expert_source.hpp:1084-1093`; `engine/src/program/generate.cpp:8693-8703`）。
- すべての expert が GPU cache に載っている場合、既定で開始した prefetch は `STRATA_FILE_TIER_IDLE` の既定有効ポリシーにより一時停止され、gate も OFF になります。GPU cache に空きが出て prefetch を再開すると `set_io_prefetch()` が再度環境変数を読みます。明示 `STRATA_IO_PREFETCH` で開始した prefetch はこの既定停止対象ではありません（`engine/src/program/generate.cpp:10251-10285, 10341-10377`）。
- gate が ON でも、予測 read-ahead は `STRATA_IO_PF_AHEAD=0` で止められます。また page-cache 比率または read-ahead 有用度が条件を満たさない間は gate が閉じます。しきい値は `STRATA_IO_PF_GATE_LO` / `STRATA_IO_PF_GATE_HI` / `STRATA_IO_PF_GATE_USEFUL` で変更できます（`engine/src/core/expert_source.cpp:1284, 1301-1303, 2330-2359`; `engine/src/core/expert_source.cpp:3487-3490`）。

## 実行時の詳細

環境変数の読み取りは `FileExpertSource::set_io_prefetch()` が prefetch を開始するたびに行われ、decode ごとではありません。関数呼び出し時点の値を `gate_on_` に保持します。実行中に環境を変更しても既存の gate には反映されず、後で file-tier idle policy が prefetch を停止・再開した場合は再開時の呼び出しで再評価されます（`engine/src/core/expert_source.cpp:1261-1312`; `engine/src/program/generate.cpp:10341-10377`）。

gate が ON のとき、decode の window ごとに観測値を更新し、容量判定は初回と以後 16 window ごとに cache room と prefetch の有用度を確認します。cache room は Linux cgroup v2 の制限と file page 分を考慮した余裕、または `/proc/meminfo` の `MemAvailable` を expert 総量で割った比率です。既定では開いている gate は room 比率が 0.55 未満で閉じ、容量不足で閉じた gate は 0.65 を超えると再開します。有用度不足で閉じた場合は room 比率 0.55 以上で 256 window ごとに probe します。16 window あたりの観測が少なくとも 64 MiB に達しない場合は状態を維持します。read-ahead が 128 MiB 未満、または使われた割合が既定 0.10 を下回る場合も閉じ、容量が保たれていれば 256 window 後に probe します（`engine/src/core/expert_source.cpp:2256-2270, 2272-2327, 2329-2359`; `engine/src/core/expert_source.cpp:3804-3820`）。

decode scope にある読み込みでは、閉じた gate が `copy_from_files()` の `pread` を抑止し、既存 mapping からの `memcpy` に進ませます。`warm()` の予測 read-ahead も gate が開いている場合だけ I/O worker に投入されます。prompt 経路は decode scope 外であり、この gate 判定の対象ではありません。gate が閉じても通常の要求データ読み込みを省略するものではありません（`engine/src/core/expert_source.cpp:1904-1921, 3487-3501`; `engine/include/strata/core/expert_source.hpp:1066-1080`）。

## ログと測定値

既定で I/O prefetch が成功した起動時は、stderr の `strata generate: file tier (Linux defaults, ...): ... the decode's read-ahead only while the page cache has room for it and it pays (STRATA_IO_PF_GATE=1); off: ... STRATA_IO_PF_GATE=0` が gate の既定 ON を示します。明示的に prefetch を有効化した場合も `file tier io prefetch ON ...` の行に `; the decode's read-ahead gated (STRATA_IO_PF_GATE=0: always)` が付きます（`engine/src/program/generate.cpp:8705-8718`）。

serve は `/proc` I/O sample が有効なリクエスト終了時、prefetch と gate が ON なら `; decode gate: cache room ... read-ahead used ... page cache held ... open|closed, closed in ... windows so far, ... flips` を stderr に出します。これは累積 gate 状態と request 差分の I/O 統計を示すログです（`engine/src/program/generate.cpp:23835-23863`）。性能値はこの環境変数の動作を説明するためには記載しません。

## 根拠

- `engine/src/core/expert_source.cpp:1261-1312` — Linux prefetch 初期化、既定値、変数の読み取り。
- `engine/src/core/expert_source.cpp:1904-1921, 2250-2359, 3487-3501, 3804-3820` — decode scope、読み取り経路、gate の評価と効果。
- `engine/include/strata/core/expert_source.hpp:1066-1097` — decode gate の説明、Linux 既定条件としきい値の初期値。
- `engine/src/program/generate.cpp:8688-8724, 10251-10285, 10341-10377, 23835-23863` — prefetch 選択・診断ログ・cache 状態に応じた停止と再開。
