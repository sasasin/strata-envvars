# `STRATA_IO_PF_GATE_HI`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

I/O prefetch の decode gate が容量不足で閉じた後、再び開くためのページキャッシュ空き容量比の上側しきい値を指定する。値は `FileExpertSource::set_io_prefetch` で `gate_hi_` に設定され、`gate_capacity` の再開判定で使われる。既定値は `0.65`。gate が開いている間の閉鎖しきい値 `STRATA_IO_PF_GATE_LO`（既定 `0.55`）と組み合わせたヒステリシスに関与する（`engine/src/core/expert_source.cpp:1299-1303,2329-2358`、`engine/include/strata/core/expert_source.hpp:1105-1106`）。

## 値と判定

`std::getenv` で設定有無を見て、存在すれば `std::atof` で数値変換し、`std::clamp(value, gate_lo_, 1.0)` を適用する。未設定ならメンバー初期値 `0.65` のまま。空文字は設定済みとして変換され `0` になり、下限 `gate_lo_` に丸められる。`atof` は文字列全体の厳密な数値検証をせず、数値に続く文字は変換結果に含めない（例: `0.7junk` は `0.7`、数値として読めない文字列は `0`）。空白や符号も `atof` の変換規則に従う。`nan` を変換できる実装では `std::clamp` も NaN をそのまま返すため、容量不足で閉じた gate の `gate_ratio_ > gate_hi_` 判定は成立しない。大文字小文字を比較する処理はない。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux の file tier で I/O prefetch を開始し、decode gate が有効 | `0.65` | `gate_lo_` 以上 `1.0` 以下に clamp された数値。例: `0.7`, `1`, `2`（`1` に丸める） | 独立した無効値判定はない。空文字・`abc`・`0` は `0` として変換後、`gate_lo_` に丸められる。負値も `gate_lo_` になる |
| I/O prefetch 無効、decode gate 無効、または Linux 以外 | gate 上側しきい値として読まれない／使われない | 該当なし | 該当なし |

下限は先に `STRATA_IO_PF_GATE_LO` を `[0,1]` に clamp して設定し、その値を本変数の clamp 下限に使う。このため `HI < LO` となる入力も `LO` に丸められる。数値変換のエラー報告や警告はない（`engine/src/core/expert_source.cpp:1299-1303`）。

## 有効になる条件

- `FileExpertSource::set_io_prefetch(true, ...)` が実行されること。通常の `strata generate` 経路では、Linux 既定が適用される file tier、または `STRATA_IO_PREFETCH` が非ゼロのときに有効化を試みる。既定経路の対象は GGUF をその場で読む file tier、または `experts.bin` tier で、後者は初期 page-cache 空き比が `0.55` 以上の場合。明示的な prefetch も unbuffered read では使えず、設定開始処理は Linux 以外では何もしない（`engine/src/program/generate.cpp:8688-8704,8722-8724`、`engine/include/strata/core/expert_source.hpp:1081-1093`、`engine/src/core/expert_source.cpp:1261-1267,1310-1312`）。
- `STRATA_IO_PF_GATE` が `0` 相当で gate を無効にしていないこと。gate は prefetch 開始時に既定で有効。`STRATA_IO_PF_GATE` が未設定または空文字なら既定の有効状態、非空なら `atoi(value) != 0` で判定されるため、`1` は有効、`0` や `0junk` は無効（`engine/src/core/expert_source.cpp:1299-1303`）。gate 無効時、本変数の値は読まれても gate 制御に使われない。
- gate の容量判定は decode scope で新しい decode window が始まるときに行う。prompt 読み取りは gate scope 外であり、この上側しきい値の対象ではない（`engine/src/core/expert_source.cpp:2250-2254,3818-3819`）。
- `STRATA_IO_PF_GATE_USEFUL` による read-ahead の有用性判定も gate を閉じたり再プローブしたりする。容量に余裕があっても、read-ahead が少ない／使われない場合は閉鎖され、本変数だけでは再開タイミングを決めない（`engine/src/core/expert_source.cpp:2334-2358`）。
- GPU cache が全専門家を保持すると、既定で有効になった prefetch は `STRATA_FILE_TIER_IDLE` の既定ポリシーにより停止される。空きが生じて再有効化されたとき `set_io_prefetch` が再度呼ばれ、環境変数を再読込する。この自動停止・再開は `io_pf_by_default` の経路に限られる（`engine/src/program/generate.cpp:10251-10285,10341-10368`）。

## 実行時の詳細

読み取り時期は `set_io_prefetch(true, ...)` の実行時で、プロセス起動時に一度だけ固定する static cache ではない。通常は generate の file-tier 設定時に呼ばれる。GPU cache の状態に応じて既定 prefetch を停止し、その後再開する経路では再度読み取るため、環境値をその間にプロセス内で変更できる実装環境なら再開時の値が使われる（`engine/src/core/expert_source.cpp:1261-1303`、`engine/src/program/generate.cpp:10351-10368`）。

容量判定は decode window 16 回ごとに行い、総 expert bytes に対する page-cache 利用可能量の比を更新する。gate が開いているときは比率が `gate_lo_` 未満なら閉じる。容量不足で閉じているときは比率が `gate_hi_` を**超えた**とき再開する（等しいだけでは再開しない）。有用性不足を理由に閉じている場合は `gate_lo_` 以上で条件を満たし、256 window ごとの probe を行う別経路となる。page-cache 量が不明、または expert bytes が 0 の場合は状態を維持する（`engine/src/core/expert_source.cpp:2329-2358`）。

gate が閉じると decode 中の read-ahead enqueue と uncached blob の demand `pread` を抑える。閉じた状態でも通常の file/mapping 読み取りへ進むため、これは file tier の読み取りを全般停止する設定ではない。read-ahead と demand pread の gate 条件、および fallback の mapping copy は `engine/src/core/expert_source.cpp:1904-1921,3485-3500` にある。生成 token の選択やモデル計算を本変数が変える処理は確認できない。

## ログと測定値

この変数専用の警告・エラー・終了経路はない。serving の file-tier I/O ログが出る場合、prefetch と gate が有効なら `; decode gate: cache room ...` に続けて gate の open/closed 状態、閉じていた window 数、切替回数を stderr に出す。`STRATA_IO_PF_GATE_HI` の設定値自体は表示しない（`engine/src/program/generate.cpp:23840-23863`）。

## 根拠

- `engine/src/core/expert_source.cpp:1261-1312` — Linux prefetch の有効化条件、環境変数の読み取り・変換と clamp。
- `engine/include/strata/core/expert_source.hpp:1066-1083,1105-1110` — gate の対象とメンバー既定値。
- `engine/src/core/expert_source.cpp:1904-1921,2250-2254,2324-2358,3818-3819` — decode scope、容量比・上側しきい値の判定、閉時の読み取り抑制。
- `engine/src/program/generate.cpp:8688-8724,10251-10285,10341-10378,23840-23863` — 起動経路、GPU cache による既定 prefetch の停止・再開、観測ログ。
