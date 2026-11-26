# `STRATA_IO_PF_GATE_USEFUL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

Linux の `FileExpertSource` が I/O prefetch と一緒に使う decode gate の「先読みの有用率」下限を指定する。直近の decode windows で先読みした bytes のうち demand 前に使われた割合がこの値を下回ると、page cache に十分な余裕があっても decode の先読みを閉じる。ただし、別条件の「16 windows あたり 128 MiB 未満しか先読みしなかった」場合にも閉じるため、この変数を `0` にしても gate 全体は無効にならない。gate が閉じると decode 中の `pread` を止め、同じ読み取りはマッピングからコピーされる。expert の選択やデータ内容をこの変数が直接変更する処理はない（`engine/src/core/expert_source.cpp:1303,1904-1920,2329-2358`）。

## 値と判定

値は `set_io_prefetch(true, ...)` の中で `std::getenv` により読み、設定されていれば `std::atof` の結果を `[0.0, 1.0]` に clamp してメンバー `gate_min_useful_` に保存する。`atof` の変換エラーは検査しないため、数値に変換できない文字列は `0` になり、数値の後ろに文字があっても数値の prefix が変換される。`std::clamp` が負値を `0`、`1` より大きい値を `1` にする。小数値はそのまま閾値になる（`engine/src/core/expert_source.cpp:1303`）。

| 条件 | unset | 有効になる値（例） | その他の値（例） |
|---|---|---|---|
| Linux で I/O prefetch の初期化が成功 | `gate_min_useful_` の初期値 `0.10` | `0.25` → `0.25`、`1` → `1.0`、`2` → `1.0` | 空文字 `""`、`abc`、`0anything` → `0.0`、`-1` → `0.0` |
| Linux 以外、または I/O prefetch を開始しない | この変数を読む処理に到達しない。メンバー初期値は `0.10` | 該当なし | 該当なし |

文字列全体の妥当性・末尾・小数の精度を検査せず、大文字小文字の比較もない。既定値 `0.10` はヘッダーのメンバー初期値による。環境変数を指定しても、実際に閾値条件で閉じるのは `gate_useful_ < gate_min_useful_` のときだけであり、等しい場合は閉じない（`engine/include/strata/core/expert_source.hpp:1105-1114`, `engine/src/core/expert_source.cpp:1303,2349`）。

## 有効になる条件

- `STRATA_IO_PREFETCH` による明示的な有効化、または Linux の `linux_io_defaults()` による既定有効化で `set_io_prefetch(true, ...)` が呼ばれること。明示値の判定は `std::atoi` で、未設定・空文字は既定判定へ進む（`engine/src/program/generate.cpp:8693-8703`）。
- Linux build であること。`set_io_prefetch` の実処理と対象変数の読み取りは `__linux__` 内にあり、Linux 以外では処理しない（`engine/src/core/expert_source.cpp:1261-1266,1303,1310-1312`）。CUDA/HIP など GPU backend の選択による別の読み取り箇所はない。
- file source が mapped file tier を使い、`base_` と `paths_` が有効で、`direct_` が空であること。条件を満たさない場合 `set_io_prefetch` は戻り、対象変数も読み取らない（`engine/src/core/expert_source.cpp:1265-1273`）。
- decode gate 自体が有効であること。prefetch 初期化時は既定で有効だが、`STRATA_IO_PF_GATE` が空でない場合は `atoi` の結果で上書きされるため、例えば `STRATA_IO_PF_GATE=0` なら本変数の値は gate 判定に使われない（`engine/src/core/expert_source.cpp:1299-1303,2257-2259`）。
- 16 decode windows ごとの cache room 判定で page-cache room 条件を満たし、gate が開いていて、16 windows を超えた後であること。room 条件を満たさない容量起因の閉鎖はこの閾値によらず起こる（`engine/src/core/expert_source.cpp:2329-2357`）。

`STRATA_IO_PF_GATE_LO` / `STRATA_IO_PF_GATE_HI` は別の cache room 閾値を変更する。CLI 引数や設定ファイルによる本変数の上書きは、Strata ソース内にない（読み取りは `engine/src/core/expert_source.cpp:1303` のみ）。

## 実行時の詳細

`set_io_prefetch` は prefetch を再初期化するたびに呼ばれ、対象変数が設定されている場合に値を読み直す。一方、呼び出しのたびに `gate_min_useful_` を既定値へ戻す処理はなく、再呼び出し時に変数が unset なら、それまでのメンバー値が保持される。通常の decode window ごとには環境を再読せず、保存値を使用する。serve 中は GPU cache の全 expert resident 状態に応じて prefetch を停止・再開する経路があり、再開時にも `set_io_prefetch(true, ...)` を呼ぶ（`engine/src/core/expert_source.cpp:1261-1264,1303`, `engine/src/program/generate.cpp:10275-10285,10341-10368`）。

gate capacity 判定は decode の window 境界で呼ばれ、16 windows ごとに実行される。先読み使用率は 16 windows の prefetch bytes に対する used bytes の比率として更新され、観測量が 64 MiB 未満なら前回値を維持する。page-cache room 条件を満たしたまま gate が開いており、16 windows 超で、先読み量が 128 MiB 未満または使用率が設定閾値未満なら gate を閉じる。使用率条件による閉鎖後は 256 windows ごとに probe し、room 条件と使用率・先読み量を再評価する（`engine/src/core/expert_source.cpp:2329-2358`）。

decode 中の file read は gate が閉じていれば `pread` を行わず、続く mapping からの `memcpy` 経路を使う。prompt path は `DecodeScope` の対象外なのでこの decode gate の計測・制御対象ではない（`engine/src/core/expert_source.cpp:1886-1922,2250-2254,2643`, `engine/include/strata/core/expert_source.hpp:1068-1080`）。

## ログと測定値

起動時の prefetch ログは gate の有効状態を表示するが、この閾値の値自体は表示しない（`engine/src/program/generate.cpp:8705-8718`）。gate 有効時の定期 I/O 統計には `; decode gate: cache room ... read-ahead used ... page cache held ... open|closed ...` が出力される。そこに表示する使用率は割合に換算されるが、閾値の値や閉鎖理由はログに表示されない（`engine/src/program/generate.cpp:23858-23863`）。

## 根拠

- `engine/include/strata/core/expert_source.hpp:1105-1114` — 閾値の既定値と gate state。
- `engine/src/core/expert_source.cpp:1261-1312` — Linux I/O prefetch の条件と環境変数の読み取り・変換。
- `engine/src/core/expert_source.cpp:1886-1922` — gate 状態による decode read の分岐。
- `engine/src/core/expert_source.cpp:2250-2270,2324-2358,3804-3820` — decode 判定、使用率・容量 gate の更新タイミング。
- `engine/src/program/generate.cpp:8693-8725,10275-10285,10341-10368,23858-23863` — prefetch の開始条件、serve での停止・再開、観測ログ。
