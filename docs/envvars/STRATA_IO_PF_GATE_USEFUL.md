# `STRATA_IO_PF_GATE_USEFUL`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux の file tier I/O prefetch に付随する decode gate の「先読みが役立った割合」の下限を設定します。ここでの割合は、直近の判定区間で read-ahead された expert bytes のうち、要求時までに使われた bytes の比率です。値は gate を直接 ON/OFF するものではありません。gate は I/O prefetch の初期化時に別設定 `STRATA_IO_PF_GATE` で無効にできます。

## 値と判定

| 状態・値 | `gate_min_useful_` の値 |
|---|---:|
| 未設定 | `0.10`（クラスの初期値） |
| `0.0` 未満の数値 | `0.0` に clamp |
| `0.0` から `1.0` の数値 | その値 |
| `1.0` より大きい数値 | `1.0` に clamp |
| 空文字、数値として変換できない文字列 | `std::atof` が `0.0` を返し、`0.0` |

環境変数が設定されていれば `std::atof` で変換し、`std::clamp(..., 0.0, 1.0)` で制限します。`atof` は文字列全体の厳密な検証をしないため、数値の後ろに非数値文字があっても数値部分を変換します。`nan` は `atof` が NaN を返し、比較に基づく `std::clamp` では NaN のまま残ります。この場合、`gate_useful_ < gate_min_useful_` は偽になります。大文字小文字の扱いは数値変換関数に委ねられます。

根拠: `include/strata/core/expert_source.hpp:1034-1039`, `src/core/expert_source.cpp:1151-1155`。

## 有効になる条件

- `FileExpertSource::set_io_prefetch(true, ...)` が実行される経路でのみ環境変数を読みます。初期化が `on == false`、mapping/path が未設定、または direct I/O 経路の場合は早期 return し、この値は読み込まれません。
- 呼び出し側では Linux の file tier で I/O prefetch を有効にした場合に初期化します。既定で有効になるかは `STRATA_IO_PREFETCH` と file tier の Linux defaults によります。`STRATA_IO_PREFETCH=0` などで I/O prefetch が無効なら、この変数の値は適用されません。
- gate 自体は I/O prefetch 初期化時に既定で ON です。`STRATA_IO_PF_GATE` が空でない値として設定されている場合、`atoi` の結果が 0 なら OFF、それ以外なら ON に上書きされます。gate が OFF なら `STRATA_IO_PF_GATE_USEFUL` は実際の制御に使われません。
- gate は decode thread の新しい window で容量・有用率を判定します。値が設定されていても、page cache の容量条件や read-ahead 量が不足するなど、別条件により有用率の比較が実行されない場合があります。

根拠: `src/core/expert_source.cpp:1114-1156`, `src/program/generate.cpp:5655-5690`, `src/core/expert_source.cpp:3276-3292`。

## 実行時の詳細

設定値は I/O prefetch の初期化中に `FileExpertSource` のメンバーへ一度読み込みます。リクエストごとに再読込するコードはなく、プロセス実行中に環境値を変えても、このオブジェクトの閾値には反映されません。

decode の新しい window ごとに gate 判定関数が呼ばれますが、容量判定は16 window ごとです。開いている gate で、page cache の容量条件を満たし、初期16 windowを過ぎた後、直近16 window の read-ahead が128 MiB未満、または read-ahead bytes に対する使用 bytes の割合が `gate_min_useful_` 未満なら、gate を閉じます。有用率は read-ahead が64 MiB以上ある区間でのみ更新されるため、それ未満では前回の値が使われます。比較は厳密な `<` です。

有用率不足を理由に閉じた gate は、容量条件が保たれている場合、閉鎖から256 window 後に再び開いて probe します。gate が閉じると予測 read-ahead の深さは1 layerになり、decode の demand read では uncached span に対する pread をせず mapping からコピーします。I/O prefetch に伴う prompt path の読み込みは gate の対象外です。

値そのものを表示する専用ログはありません。request I/O 統計が有効な場合、decode gate の状態、有用率、閉鎖 window 数、flip 数が stderr の `strata serve: ...; decode gate: ...` 行に出ます。有用率は `%` 表示で、閾値は表示されません。

根拠: `src/core/expert_source.cpp:1903-1917,1971-2004,1750-1767,2956-2990,3276-3292`, `src/program/generate.cpp:15400-15429`。

## 文書との照合

`docs/DETAILS.md:272-285` は、この閾値の既定値を10%とし、直近16 windowで128 MB以上のread-aheadがあり、そのうち10%が使われることを decode gate の条件として説明しています。コードでは read-ahead が128 MiB未満の場合も gate を閉じる条件で、割合の比較は `<` です。資料の説明と一致します（資料中のMB表記とコードのMiB定数は表記精度が異なります）。
