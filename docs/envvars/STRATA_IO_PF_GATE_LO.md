# `STRATA_IO_PF_GATE_LO`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux の `FileExpertSource` が I/O prefetch とともに使う decode gate の下側しきい値を設定する。gate が開いているとき、専門家ファイル tier に対する decode の cache-room 比率がこの値を下回ると gate を閉じる。閉じると decode 中の未キャッシュ blob の `pread` と router lookahead の先読みを抑え、mapped file からの通常読み込みに戻る。gate 自体は既定で有効だが、環境変数で I/O prefetch が有効にならなければ、この値は読まれない（`engine/src/core/expert_source.cpp:1261-1267, 1299-1303`、`engine/src/program/generate.cpp:8693-8703`）。

## 値と判定

`set_io_prefetch(true, ...)` のたびに `std::getenv` で取得し、設定されていれば `std::atof` の結果を `[0.0, 1.0]` に `std::clamp` する。未設定ならメンバー初期値 `0.55` のまま。空文字は設定済みとして読み取られ、`atof("") == 0` なので `0.0` になる。`atof` は文字列全体の厳密な数値検証をしないため、数値として読める接頭部の後ろは無視され、変換できない文字列は `0.0` になる。例えば `0.7tail` は `0.7`、`0anything` は `0`、`true` / `false` はともに `0`。大文字小文字の比較はない。有限値は範囲外なら clamp される。`nan` のように `atof` が NaN を返す入力は `std::clamp` でも有限値に正規化されず、後段の比較は通常の数値比較どおりには成立しない。

| 条件 | 未設定 | 設定時に使われる値 | 例 |
|---|---:|---|---|
| `STRATA_IO_PREFETCH` が有効で Linux mapped file tier を使う場合 | `0.55` | `atof` の結果を `[0, 1]` に clamp | `0.55` → `0.55`、`-1` → `0`、`2` → `1`、空文字・`junk`・`true` → `0` |
| I/O prefetch を有効化しない場合、または Linux 以外 | 読み取りなし | 適用なし | この変数だけでは I/O prefetch は有効にならない |

下限は「gate が開いているとき」に `ratio >= gate_lo_` なら room 条件を満たす、`ratio < gate_lo_` なら満たさない、という境界である。capacity 不足で閉じた gate は、再開時には別変数 `STRATA_IO_PF_GATE_HI` の上側しきい値を使い、`ratio > gate_hi_` で開く。`STRATA_IO_PF_GATE_HI` の値も `[gate_lo_, 1.0]` に clamp されるため、下限を上げると上限の許容最小値も上がる（`engine/src/core/expert_source.cpp:1301-1303, 2342-2358`）。

## 有効になる条件

- `strata generate` の Linux file tier で `STRATA_IO_PREFETCH` が unset / 空文字のときは、ソース種別・cache room に応じて Linux 既定が選ばれた場合に読み取られる。明示値が空でなければ `atoi(value) != 0` のときだけ有効化されるため、`STRATA_IO_PREFETCH=0` は既定有効化を抑止する（`engine/src/program/generate.cpp:8693-8703`）。
- Linux 以外では `set_io_prefetch` の実装が no-op。Linux でも `on == false`、mapped base がない、パスが空、または unbuffered reader の場合は早期 return し、しきい値を読み込まない（`engine/src/core/expert_source.cpp:1261-1267, 1310-1312`）。
- `STRATA_IO_PF_GATE` が非空で設定されると、`atoi(value) != 0` が gate の有効状態を上書きする。したがって `STRATA_IO_PF_GATE=0` なら本変数を読んでも gate は使われず、非ゼロなら使われる。未設定または空文字なら、I/O prefetch とともに gate が有効になる（`engine/src/core/expert_source.cpp:1299-1302`）。
- このしきい値を直接上書きする CLI 引数はなく、`STRATA_COLD_OVERLAP` は別の cold-read / zero-copy 経路の設定で、本変数や gate の有効化を上書きしない（`engine/src/core/expert_source.cpp:1299-1303`; `engine/src/program/generate.cpp:5461-5468`）。
- decode gate の更新は、staged source で decode thread として印を付けられた処理に限られる。新しい decode window ごとに room を確認し、prompt 経路は gate 対象外（`engine/src/core/expert_source.cpp:2250-2254, 3818-3819`; `engine/src/program/generate.cpp:5460-5470`）。
- GPU cache が全 expert を保持し `STRATA_FILE_TIER_IDLE` が未設定または `atoi != 0` の場合、Linux 既定で有効になった I/O prefetch は一時停止される。この既定経路では gate も止まり、再開時に `set_io_prefetch(true, ...)` が設定を読み直す。明示的な `STRATA_IO_PREFETCH=1` はこの idle policy による停止対象外（`engine/src/program/generate.cpp:10251-10258, 10275-10285, 10341-10368`）。

## 実行時の詳細

環境変数はプロセス起動時の一度だけではなく、I/O prefetch を開始するたびに読み込む。通常は generate 初期化時、また serve の GPU cache 状態に応じた file-tier 再開時にも `set_io_prefetch(true, ...)` で評価される。読み取り値は `FileExpertSource` のメンバーに保持され、各 decode window で環境を再取得する処理はない。外部から環境を変える操作や子プロセスへの転送はこの設定経路にはない（`engine/src/core/expert_source.cpp:1261-1267, 1299-1303`; `engine/src/program/generate.cpp:10363-10368`）。

既定値は `gate_lo_ = 0.55`。gate open 中、16 decode window ごとに cgroup v2 の制限（祖先を含む）から非 file 使用量を差し引いた room、または `MemAvailable` を expert bytes で割った比率を再評価する。値が未取得・0 の場合は状態を維持する。gate は初期状態で open。room が下限未満なら閉じ、capacity により閉じた gate は `STRATA_IO_PF_GATE_HI` を超えるまで閉じたままになる。room 条件を満たしていても、read-ahead が 16-window 区間で 128 MiB 未満、またはその有用率が `STRATA_IO_PF_GATE_USEFUL` 未満なら別理由で閉じ、256 window ごとの probe を行う（`engine/include/strata/core/expert_source.hpp:1105-1117`; `engine/src/core/expert_source.cpp:2324-2358`）。

閉じている間、decode 中の未キャッシュ blob の `pread` を行わず mapping からコピーし、通常の page fault 読み込みに委ねる。lookahead は読み先 depth を 1 に縮める。開いている場合は読み込み worker に先読みをキューイングできる。これらは読み込み方法・先読み量を変える処理で、コード上、生成 token や router の選択結果を変更する制御ではない（`engine/src/core/expert_source.cpp:1896-1920, 3483-3501, 3698-3702, 1228-1259`）。

## ログと測定値

この変数専用の警告や終了経路はない。Linux 既定で I/O prefetch が開始されると stderr に `strata generate: file tier (Linux defaults, ...)` が出て、gate が有効かを `the decode's read-ahead only while the page cache has room for it and it pays (STRATA_IO_PF_GATE=1)` 相当の文言で示す。serve の request I/O ログでは gate が有効な場合に `decode gate: cache room ...`、状態 `open` / `closed`、閉じた window 数と flips を表示する。これらの値は `src.io_prefetch()` / `src.gate_on()` が真で I/O sampling が有効な場合のログである（`engine/src/program/generate.cpp:8705-8718, 23836-23863`）。

`docs/DETAILS.md:310` は gate を `STRATA_IO_PF_GATE=1` と `STRATA_IO_PF_GATE_LO` / `_HI` の閾値で説明しており、実装の既定有効・下限値の使い方と整合する。ただし現行コードでは `STRATA_IO_PF_GATE` 未設定でも I/O prefetch とともに gate が有効になる（`engine/src/core/expert_source.cpp:1299-1303`）。同資料にある性能値は測定条件付きの資料上の記述であり、この調査では再測定していない。

## 根拠

- `engine/src/core/expert_source.cpp:1261-1312` — Linux 制限、設定読み取り、既定値の上書き。
- `engine/src/core/expert_source.cpp:2324-2358` — cache-room 比率、下限・上限と更新規則。
- `engine/src/core/expert_source.cpp:1896-1920, 3483-3501` — gate 閉鎖時の読み込み経路。
- `engine/src/program/generate.cpp:8693-8724, 10275-10285, 10341-10377` — prefetch 起動条件、既定経路の停止・再開。
- `engine/src/program/generate.cpp:23836-23863` — 観測可能な request I/O ログ。
