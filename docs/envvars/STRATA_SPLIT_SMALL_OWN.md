# `STRATA_SPLIT_SMALL_OWN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` で複数 GPU の layer split があり、prompt 用の stage (`pf_parts`) と host residency table がある場合に、layer split の各 stage 用 cache の末尾に prompt buffer 用 slot を確保する token chunk サイズ `S` を決める。通常の prompt borrowing と比べ、短い prompt は stage cache の予約済み領域を prompt buffer に使い、その領域にあった expert を起動時に non-resident にして CPU / PCIe 経路に回す。対象は serve の prompt path であり、単一 GPU や通常の一回生成経路ではこの値は参照されない（`engine/src/program/generate.cpp:12302,13171-13183`）。

## 値と判定

値は `std::getenv` で取得し、設定されていれば `std::atoll` で数値変換した後、`request_chunk` が 256-token 単位に切り上げ、実行時の `o.prefill_chunk` 以下に制限する。`request_chunk` は入力または上限が 0 以下なら 0 を返す（CUDA: `engine/src/program/generate.cpp:11159-11165,13177-13183`、SYCL: `engine/sycl/src/program/generate.cpp:6640-6646,7635-7641`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `--serve` の layer split（`multi_gpu && !pf_parts.empty() && !host_res.empty()`） | `S=0`。予約・小 prompt 用分岐なし | 正の数値 prefix。例: `1` は 256、`300` は 512、`512tokens` は 512。ただし `o.prefill_chunk` が小さければその値まで | 空文字、`0`、`0anything`、`true`、`false`、負数、数値 prefix のない文字列は変換後 0 となり無効 |
| 上記以外 | 読み取り箇所に入らず機能しない | なし | なし |

`atoll` の結果に独自の完全文字列検査、真偽値解釈、大文字小文字判定、範囲エラー処理はない。正の値でも `request_chunk` が有効 `--prefill` chunk で cap する。後続の `STRATA_SPLIT_SMALL_MAX` は独立に `atoll` され、未設定なら `S`、設定時は `max(S, atoll(value))` が prompt の適用上限になる。従って空文字や無効な値は 0 となり、下限 `S` のため既定相当の上限になる。`S<=0` なら上限も 0 で機能しない（`engine/src/program/generate.cpp:13177-13183`、SYCL: `engine/sycl/src/program/generate.cpp:7635-7641`）。

## 有効になる条件

- `--serve` が有効であること。読み取り箇所は serve 初期化の `if (o.serve)` ブロック内（`engine/src/program/generate.cpp:12302,13171-13183`）。
- 実行時に layer split が選択され、`multi_gpu`、`pf_parts`、`host_res` がそれぞれ有効であること。条件を満たさないと環境変数を読み取らず、予約も行わない（同 `:13177-13183`）。
- `S > 0` で、個々の `PfPart` が有効な `p.first >= 0` であること。対象 part の cache tail について `host_res` に記録された slot が閾値以上なら non-resident に変更される（同 `:13184-13197`）。
- prompt segment の token 数が `split_small_max` 以下のとき、小 prompt 分岐で必要 chunk を `min(want_full, S)` にする。上限を超える segment は通常の `want_full` を使う（同 `:11403-11411`）。`STRATA_SPLIT_SMALL_MAX` は既定で `S`、明示値は `S` 未満でも `S` 以上に引き上げられる（同 `:13181-13183`）。
- 有効な `S` は `request_chunk(..., o.prefill_chunk)` で cap されるため、`--prefill` 等で決まった実行時 chunk が `S` より小さい場合はその小さい値になる（同 `:11159-11165,13179-13183`）。

## 実行時の詳細

変数は serve の prompt path 初期化後に読み込まれ、`split_small` と `split_small_max` に保存される。static cache や request ごとの再読込ではない。以後の prompt lending が保存値を使うため、実行中に環境値を変えてもこの serve session の判定には反映されない（`engine/src/program/generate.cpp:13142-13183,11403-11411`）。SYCL 側も同じタイミングと処理（`engine/sycl/src/program/generate.cpp:7607-7641`）。

`S>0` の場合、各有効 part で `first_s = max(p.first, cache.slots() - part_slots(p,S))` を求め、その part が担当する layer の expert residency slot `r >= first_s` を `kNotResident` にする。1 件以上変更した場合は head と各 stage の device residency table を更新する。これにより予約 tail の expert は GPU resident 扱いでなくなる（CUDA: `engine/src/program/generate.cpp:13184-13206`、SYCL: `engine/sycl/src/program/generate.cpp:7642-7665`）。

serve 中の prompt segment では、token 数が `split_small_max` 以下なら `want_full` を最大 `S` に制限する。予約範囲の experts は既に non-resident のため、その範囲を prompt buffer に使い、通常の expert lend/refill は発生しない。適用上限を超える segment は通常の chunk 選択に戻り、予約範囲を超える必要があれば追加 slot を借りる（CUDA: `engine/src/program/generate.cpp:20609-20616`、SYCL: `engine/sycl/src/program/generate.cpp:11403-11429`）。

## ログと測定値

予約が有効な part ごとに stderr へ `strata serve:   CUDA%d keeps %lld slots for %lld-token prompts (%lld experts no longer resident)` を出す。`S<=0`、または part が無効ならこの行は出ない。変更 expert が 1 件以上ある場合に限り residency table を再送する。環境変数固有のエラー終了経路や測定値はない（CUDA: `engine/src/program/generate.cpp:13184-13206`、SYCL: `engine/sycl/src/program/generate.cpp:7642-7665`）。

## 根拠

- CUDA backend の serve 条件と値取得・変換: `engine/src/program/generate.cpp:12302,13171-13183`
- CUDA chunk の 256-token 切り上げと上限: `engine/src/program/generate.cpp:11159-11165`
- CUDA residency 更新・診断ログ: `engine/src/program/generate.cpp:13184-13206`
- CUDA prompt segment ごとの chunk 選択・borrowing: `engine/src/program/generate.cpp:20609-20616`
- SYCL 実装の同じ値取得・更新: `engine/sycl/src/program/generate.cpp:7629-7665`
- SYCL chunk の上限処理と segment ごとの borrowing: `engine/sycl/src/program/generate.cpp:6640-6646,11403-11429`
