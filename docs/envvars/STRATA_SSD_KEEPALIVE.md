# `STRATA_SSD_KEEPALIVE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

PLE（per-layer token embedding）の表を direct I/O で読むとき、行読み要求がしばらくない間に表のランダムな1ページを読む周期をミリ秒で指定する。Strata が追加の読み出しを発行する動作であり、生成する token や PLE の選択結果を直接変更する設定ではない。CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL 系の `engine/sycl/src/program/generate.cpp` が値を読み、`PleReader::set_keepalive()` に渡す（`engine/src/program/generate.cpp:6277-6287`、`engine/sycl/src/program/generate.cpp:3358-3368`、`engine/src/kernels/ngram.cpp:449-465`）。

## 値と判定

両実装とも `std::getenv` で取得し、未設定または空文字なら `100.0` ミリ秒を使う。空でない値は `std::atof` で数値に変換した後、`std::clamp` で `0.0..10000.0` に制限する。文字列全体の妥当性検査や変換エラー検出はない。`atof` が読める数値の接頭辞を使い、後続文字は無視する。数値に変換できない接頭辞は 0 となる。空白は `atof` の変換規則に従う（`engine/src/program/generate.cpp:6281-6286`、`engine/sycl/src/program/generate.cpp:3362-3367`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `engine/src/program/generate.cpp` / SYCL 実装共通 | 100 ms | `1`、`1.5`、`10000`。正の数値接頭辞は最大 10000 ms に clamp | `0`、負数、`true`、`0anything`、空文字（空文字は無効値ではなく unset と同じ 100 ms） |

`10001` は 10000 ms に clamp され、`-1` は 0 ms に clamp される。`1tail` は 1 ms として扱われる。`nan` は正数判定を通らず off になり、正の無限大は clamp により 10000 ms になる。`pio.keepalive_ms > 0` が成立しない場合、reader の周期は off になる（`engine/src/ngram/ple_reader.cpp:596-603`）。

## 有効になる条件

- PLE 表が開かれ、`o.ple_gguf` が空でないこと。`--no-ple` で PLE を無効にした経路では、この値を読むブロック自体を通らない。native モデルでは表の shard を自動特定する経路もある（`engine/src/program/generate.cpp:5127-5134,5205-5214,6269-6287`、SYCL: `engine/sycl/src/program/generate.cpp:2576-2582,2619-2629,3350-3368`）。
- PLE I/O が `Direct` であること。`--ple-io mmap` または `--ple-io ram` では `keepalive_ms` を 0 にする。指定なしの `--ple-io` は `direct`（`engine/src/program/generate.cpp:818,6271-6286`、SYCL: `engine/sycl/src/program/generate.cpp:502,3352-3367`）。
- I/O worker thread を使うこと。既定では使うが、`--ple-sync-submit` は caller-thread I/O に切り替え、周期を 0 にする（`engine/src/program/generate.cpp:823,6276-6286`、`engine/sycl/src/program/generate.cpp:507,3357-3367`）。reader 側も `threaded` でなければ周期を無効化する（`engine/src/ngram/ple_reader.cpp:596-603`）。
- 暗黙の direct 選択時に PLE の residency policy が条件を満たすと、表を `Mmap` で再オープンして keep-alive を無効にする。通常は `STRATA_PLE_AUTO_RAM` が未設定なら `STRATA_DEFAULTS=026` でない場合に policy が許可され、明示値は `atoi` が非 0 なら許可、0 なら拒否。Apple では `STRATA_PLE_AUTO_RAM=1` の明示が必要。十分な空き RAM などの条件も必要（`engine/src/program/generate.cpp:6303-6315,6324-6331`、`engine/include/strata/core/ple_residency.hpp:25-37`）。明示的な `--ple-io direct` はこの自動 RAM 切替を抑止する（`engine/src/program/generate.cpp:6303-6305`）。
- 低速 direct 読みを検出し、かつ `STRATA_PLE_AUTO_MMAP` が非ゼロで、`--ple-io` が明示されていない場合は `Mmap` に切り替え keep-alive を無効化する。明示的な `--ple-io direct` は direct を維持する（`engine/src/program/generate.cpp:6350-6375`、SYCL: `engine/sycl/src/program/generate.cpp:3373-3398`）。

OS や backend による値の parse 差は、確認した CUDA/HIP 系と SYCL 系の2実装にはない。Metal 用実装でこの環境変数を読む箇所は見つからなかった。

## 実行時の詳細

値は `generate` の PLE 表初期化時に一度読み取られ、`PleIoOptions` 経由で direct reader の open 後に設定される。プロセス実行中の環境変更を再読込する処理はない（`engine/src/program/generate.cpp:6269-6288`、`engine/sycl/src/program/generate.cpp:3350-3369`、`engine/src/kernels/ngram.cpp:449-465`）。

reader は最初の行要求より前には keep-alive を発行しない。行要求から `keepalive_ms` 経過し、worker が idle で、最後の行要求から `STRATA_SSD_KEEPALIVE_WINDOW`（既定 60 秒、明示値は空なら 60、そうでなければ `atof` 後 1..86400 秒に clamp）以内なら、表内のランダムな1ページを読む。keep-alive の読み出し完了も次回周期の基準時刻になる。要求が window を超えて途絶えると停止し、次の要求で再開する（`engine/src/ngram/ple_reader.cpp:127-132,190-208,310-320,433-441,596-603`）。

keep-alive 用ページの submit または完了が失敗した場合、reader は周期を無効にするが、その失敗だけでは reader 全体をエラーにしない。通常の表読みの失敗は別経路で `PleReader: a table read failed` などのエラーとなり、`PleTable::gather` は stderr に `PleTable::gather: <error>` を出して出力埋め込みをゼロにする（`engine/src/ngram/ple_reader.cpp:166-179,210-236`、`engine/src/kernels/ngram.cpp:882-891`）。

## ログと測定値

有効なら初期化時に stderr へ次の形式で出る（`%.0f` 表示なので小数の設定値は丸めて表示される）。Direct でも周期が無効なら別の文言が出る（`engine/src/program/generate.cpp:6404-6409`、SYCL: `engine/sycl/src/program/generate.cpp:3424-3429`）。

```text
strata generate: the SSD is kept awake while rows are read: one page of the table after %.0f ms without a read, until %.0f s after the last request (STRATA_SSD_KEEPALIVE=0 turns it off)
strata generate: SSD keep-alive off: the SSD may fall asleep between reads
```

`--stats` を指定した場合、Direct reader の統計に keep-alive 実績があれば stdout の `ple io` 行へ `SSD kept awake by N reads (slowest X ms)` が追加される（`engine/src/kernels/ngram.cpp:865-879`、出力箇所: `engine/src/program/generate.cpp:25462-25476`、SYCL: `engine/sycl/src/program/generate.cpp:14446-14460`）。調査対象の資料にはこの変数による性能測定値は見当たらない。

## 根拠

- 読み取り、既定値、変換、I/O mode と thread 条件: `engine/src/program/generate.cpp:6277-6288`、`engine/sycl/src/program/generate.cpp:3358-3369`
- 値の reader への反映、周期、窓、失敗時の処理: `engine/src/kernels/ngram.cpp:449-465`、`engine/src/ngram/ple_reader.cpp:127-132,166-179,190-228,310-320,433-441,596-603`
- PLE と CLI の条件: `engine/src/program/generate.cpp:5127-5134,5205-5214,6269-6288`、`engine/sycl/src/program/generate.cpp:2576-2582,2619-2629,3350-3369`
- 自動切替: `engine/src/program/generate.cpp:6303-6331,6350-6375`、`engine/include/strata/core/ple_residency.hpp:25-37`、SYCL: `engine/sycl/src/program/generate.cpp:3373-3398`
- 観測可能なログ: `engine/src/program/generate.cpp:6404-6409,25462-25476`、`engine/sycl/src/program/generate.cpp:3424-3429,14446-14460`、`engine/src/kernels/ngram.cpp:865-879`
