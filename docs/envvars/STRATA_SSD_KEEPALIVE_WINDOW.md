# `STRATA_SSD_KEEPALIVE_WINDOW`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

PLE（per-layer token embedding）テーブルを direct I/O で読むとき、最後に行を要求してから SSD keep-alive のページ読み込みを続ける時間を秒で指定する。`engine/src` 側と SYCL 側の `strata generate` が `PleIoOptions::keepalive_window_s` に設定し、`PleTable::open` から `PleReader::set_keepalive` に渡す。keep-alive 自体の周期は別変数 `STRATA_SSD_KEEPALIVE` が決める。この変数だけでは keep-alive を有効化せず、周期が 0 の場合や direct I/O でない場合には window 値は使われない（`engine/src/program/generate.cpp:6269-6288`, `engine/sycl/src/program/generate.cpp:3350-3369`, `engine/src/kernels/ngram.cpp:449-465`）。

## 値と判定

PLE テーブルの初期化時に `std::getenv` で読み、空でなければ `std::atof` を適用して `[1, 86400]` 秒に `std::clamp` する。文字列全体の妥当性検査はない。`atof` が数値として読めない文字列は 0 となり下限 1 秒へ clamp される。数値の後ろの文字は無視される。未設定または空文字は 60 秒。CUDA 系と SYCL 系で同じ判定である（`engine/src/program/generate.cpp:6281-6286`, `engine/sycl/src/program/generate.cpp:3362-3367`）。

| 条件 | unset | 有効になる値（例） | 無効値・境界の例 |
|---|---|---|---|
| `engine/src` 側 / SYCL 側で PLE 初期化 | `60` 秒 | `30` → 30 秒、`1tail` → 1 秒、`90000` → 86400 秒 | 空文字 → 60 秒、`0` / `-5` / `true` / `abc` / `0anything` → 1 秒、`0.5` → 1 秒 |

値を明示したとき負数や 0 を使って window を無効化することはできず、最小値は 1 秒。`atof` が認識する NaN 表記は通常の数値範囲へ clamp されない可能性がある（`std::clamp` は NaN を数値へ置換しない）。変換・範囲制限は `generate` 内で一度行われ、環境を実行中に変更しても既に初期化された reader の値は変わらない（`engine/src/program/generate.cpp:6281-6288`, `engine/src/ngram/ple_reader.cpp:596-604`）。

## 有効になる条件

- `strata generate` が PLE テーブルを開く経路であること。`o.ple_gguf` が空でない場合だけ環境値を読み込む。PLE が無効、または `--ple-gguf` がない経路では読み取りも適用もない（`engine/src/program/generate.cpp:6269-6288`; オプション判定は `engine/src/program/generate.cpp:5205-5215`）。
- `--ple-io` が `direct`（既定）であること。`mmap` / `ram` は `PleIo::Mmap` となり、keep-alive 周期を 0 にするため window は作用しない（`engine/src/program/generate.cpp:6270-6286`）。
- `--ple-sync-submit` を指定していないこと。同期 submit では `pio.io_thread` が false となり、周期も 0 にされる。reader 側も worker thread がない場合は周期を 0 にする（`engine/src/program/generate.cpp:6274-6286`, `engine/src/ngram/ple_reader.cpp:596-602`）。
- `STRATA_SSD_KEEPALIVE` の周期が正であること。未設定・空文字の既定は 100 ms、空でない値は `atof` 後 `[0, 10000]` に clamp されるため、`STRATA_SSD_KEEPALIVE=0` では window に関係なく停止する（`engine/src/program/generate.cpp:6282-6286`）。
- 初期設定が direct でも、その後 mmap に切り替わる経路では周期が 0 にされる。`engine/src` 側では条件を満たす PLE residency policy が `--ple-io ram` を選ぶ場合、また `engine/src` 側・SYCL 側とも direct 読み取りの低速 probe 後に `STRATA_PLE_AUTO_MMAP` が許可して自動切替する場合が該当する（`engine/src/program/generate.cpp:6303-6331,6352-6375`, `engine/sycl/src/program/generate.cpp:3373-3397`）。
- reader worker が行要求を受けてからの window であり、要求後に無通信の時間が window を超えると keep-alive を止める。次の行要求で再び window を開始する（`engine/src/ngram/ple_reader.cpp:190-194,433-441`）。

## 実行時の詳細

設定は `PleIoOptions` に格納され、direct モードで PLE table を開いた直後に `PleReader::set_keepalive` へ渡る。reader は `window_s` をマイクロ秒へ換算して保持する。worker は周期ごとにテーブル内の異なる 1 ページをキューし、最後の行要求から window を過ぎた場合は新しい行要求まで追加しない。ページは表データの範囲から選ぶ（`engine/src/kernels/ngram.cpp:449-465`, `engine/src/ngram/ple_reader.cpp:596-604,190-208,310-320`）。

値は各 `generate` の PLE 初期化時に環境から読み、reader に渡した後はその reader の設定として保持される。リクエストごとの再読込や CLI 引数による window の上書きはこの実装にはない。なお `STRATA_SSD_KEEPALIVE` の有効値により周期が 0 でも、設定された window 自体は reader に渡るが、周期が 0 なので keep-alive は発生しない。`engine/src` 側の residency policy による RAM 化または両実装の auto-mmap 切替は、reader の再 open 時に keep-alive 周期を明示的に 0 にする（`engine/src/program/generate.cpp:6281-6288,6324-6344,6369-6375`; `engine/sycl/src/program/generate.cpp:3362-3369,3385-3397`; `engine/src/ngram/ple_reader.cpp:596-603`）。

## ログと測定値

両実装は周期が有効なら stderr に `strata generate: the SSD is kept awake while rows are read: one page of the table after %.0f ms without a read, until %.0f s after the last request (STRATA_SSD_KEEPALIVE=0 turns it off)` を出し、window 値を秒表示する。direct モードで周期が 0 なら `strata generate: SSD keep-alive off: the SSD may fall asleep between reads` を出す。mmap モードではこの keep-alive の有効／無効ログ分岐は出ない（`engine/src/program/generate.cpp:6404-6409`, `engine/sycl/src/program/generate.cpp:3424-3429`）。

keep-alive ページ読み込みが失敗した場合、reader は周期を 0 にして keep-alive のみを止め、通常の reader error にはしない（`engine/src/ngram/ple_reader.cpp:167-172,218-227`）。Strata の `docs/DETAILS.md` にこの変数の説明や測定値は見つからなかった。速度・遅延への効果を定量化する資料は確認できていない。

## 根拠

- `engine/src/program/generate.cpp:6269-6288,6404-6409`
- `engine/sycl/src/program/generate.cpp:3350-3369,3424-3429`
- `engine/include/strata/kernels/ngram.hpp:167-181`
- `engine/src/kernels/ngram.cpp:449-465`
- `engine/include/strata/ngram/ple_reader.hpp:75-81`
- `engine/src/ngram/ple_reader.cpp:167-172,190-208,218-227,310-320,433-441,596-604`
