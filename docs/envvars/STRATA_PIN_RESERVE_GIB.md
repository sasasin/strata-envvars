# `STRATA_PIN_RESERVE_GIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux の CUDA/HIP 共通 `FileExpertSource::pin_cache_complement` が、resident expert copy を段階的に page-lock するときに、各段階の後も残す RAM の下限を GiB で指定する。正数を指定するとその値が下限になり、未設定・0 以下・数値に変換できない値では `max(headroom_bytes, 2 GiB)` が使われる。これは resident copy 全体のサイズや `--resident-budget-gib` の値を設定するものではなく、段階 pin に入るか、各段階でどこまでページを確保するかを判定する値である（`engine/src/core/expert_source.cpp:4323-4327`, `engine/src/core/expert_source.cpp:4355-4367`, `engine/src/core/expert_source.cpp:4460-4465`）。

この設定が効果を持つのは `pin_cache_complement` に `pin=true` が渡り、Linux の実装経路に入る場合だけ。通常は `--resident-experts` または正数の `--resident-budget-gib` / `--ram-experts-gb` が resident copy を有効にし、`STRATA_RESIDENT_PIN=0` なら pin を無効にする。expert arena が RAM に収まらない場合の自動 resident copy も同じ pin 設定を使う。単独の `--resident-cpu-experts` は resident copy を有効にするが、pin を有効にはしない（`engine/src/program/generate.cpp:4220-4228`, `engine/src/program/generate.cpp:4242-4257`, `engine/src/program/generate.cpp:8892-8908`, `engine/include/strata/core/resident_ram_copy.hpp:11-22`, `engine/src/program/generate.cpp:12077-12080`）。

## 値と判定

環境値を `std::getenv` で取得し、`std::atof(v) > 0` なら `atof(v) * 1073741824.0` を `uint64_t` に変換する。文字列全体の数値検証はなく、`atof` が認識する先頭部分を使う。したがって `1abc` は 1 GiB、前後の空白を含む ` 1 ` も 1 GiB として扱われる。整数への変換では小数 GiB の端数バイトが切り捨てられる。変換失敗・空文字・0・負数では既定値に戻る。大文字小文字の真偽値比較はなく、`true` / `false` は正数にならない。正の無限大など、有限範囲を超える値の浮動小数点から整数への変換はコードで検査されないため、有効な設定値として扱えるとはいえない（`engine/src/core/expert_source.cpp:4323-4327`）。

| 条件 | unset | 有効になる値（例） | 無効値と扱い |
|---|---|---|---|
| 値の変換 | `max(headroom_bytes, 2 GiB)` | `1`, `0.5`, `1abc` → 正数として GiB 換算 | ``, `0`, `0anything`, `-1`, `true`, `false`, `abc` → 既定値 |
| headroom との関係 | resident 処理へ渡された headroom と 2 GiB の大きい方 | `2` より大きい値もそのまま reserve 値にする | 2 GiB 未満の正数は明示値として使われる（最低 2 GiB には clamp されない） |

`headroom_bytes` は `--resident-experts` と正数の `--resident-budget-gib` では通常 4 GiB から始まり、`STRATA_RESIDENT_HEADROOM_GIB` が 0 以上ならその値に置き換わる。さらに `--ram-keep-gib` または `STRATA_RAM_KEEP_GIB` があり、`STRATA_RESIDENT_HEADROOM_GIB` が有効値でなければ、headroom は `ram_keep` まで引き上げられる。そのため対象変数が unset 等の場合の reserve は通常 4 GiBだが、明示 headroom が 0 なら最低値の 2 GiBとなり、`ram_keep` が大きければ 4 GiBを超える。これらの設定は対象変数に正数が指定されている場合、その reserve 値を上書きしない（`engine/src/program/generate.cpp:4221-4228`, `engine/src/program/generate.cpp:4242-4257`, `engine/src/program/generate.cpp:4277-4285`）。

## 有効になる条件

- OS が Linux であること。段階 pin と reserve 判定は `#if defined(__linux__)` 内にある。Windows の CUDA/HIP 実装は `cudaHostAlloc` による一括確保経路を使い、この値での段階判定はない。SYCL の別実装 `engine/sycl/src/core/expert_source.cpp` にも対象名の読み取りはない（`engine/src/core/expert_source.cpp:4328-4336`, `engine/src/core/expert_source.cpp:4374-4397`, `engine/sycl/src/core/expert_source.cpp:1661-1675`）。
- resident copy があり、その `pin` 引数が true であること。`STRATA_RESIDENT_PIN=0` は完全一致で pin を無効にする。それ以外の値または未設定は pin を有効にする（`engine/include/strata/core/resident_ram_copy.hpp:11-15`）。
- 対象変数が選ぶ reserve の影響が実際に現れるには、段階 pin 経路が選択されること。Linux では `STRATA_PIN_GUARD=2` が段階経路を強制し、既定の `1` など 0 以外では `free_now < bytes + reserve` の場合に mapped model file の cache を解放してから再判定する。`STRATA_PIN_GUARD=0` は段階経路を抑止するが、NUMA placement が有効な場合は NUMA 経路が段階 pin を強制する。guard 値は別の関数内 static に保存される（`engine/src/core/expert_source.cpp:4329-4333`, `engine/src/core/expert_source.cpp:4335-4357`）。
- Linux の有効な NUMA placement がある場合、`STRATA_PIN_GUARD=0` でも段階 pin になり、NUMA の空き RAM 判定には reserve の半分を渡す（`engine/src/core/expert_source.cpp:4335-4349`）。
- resident copy のサイズ・採用 expert の決定は別に行われる。`--resident-budget-gib`、利用可能 RAM、`STRATA_RESIDENT_HEADROOM_GIB`、`STRATA_RAM_KEEP_GIB` などで copy が 0 bytes なら、対象変数の値は段階 pin に作用しない（`engine/src/core/expert_source.cpp:3985-3995`, `engine/src/core/expert_source.cpp:4311-4327`）。

## 実行時の詳細

値は `pin_cache_complement` 内で、resident complement のサイズ計算後、確保処理に入るたびに読み取られるローカル変数であり、関数内 static cache ではない。通常の resident copy では起動時の同関数呼び出し中に一度評価される。`--resident-experts` 等の soft fallback が最初の試行に失敗し、「what fits」の再試行をする場合は関数が再度呼ばれ、値も読み直される。関数実行中に環境を変えても選択済みの reserve や段階処理は変わらない（`engine/src/core/expert_source.cpp:3985-3990`, `engine/src/core/expert_source.cpp:4323-4327`, `engine/src/program/generate.cpp:12079-12099`）。

段階経路では、最大 1 GiB ずつ RAM を使う前に利用可能 RAM を読み、次の step と reserve の合計以上あるかを確認する。足りない、または RAM を読めない場合はページの確保を止める。確保できた先頭部分だけを GPU 用に登録し、残りは resident だが pageable な領域として保持する。未登録領域から GPU へコピーするときは CPU 経由になる。対象変数はこの停止基準に使われ、GPU cache の expert 構成や token 選択は変更しない（`engine/src/core/expert_source.cpp:4450-4473`, `engine/src/core/expert_source.cpp:4482-4523`, `engine/src/core/expert_source.cpp:4724-4738`）。

段階経路が選ばれなければ一括 `cudaHostAlloc` を試し、失敗した場合は pageable memory に fallback する。この値自体は確保失敗を起こす処理ではなく、段階経路の reserve 判定に作用する（`engine/src/core/expert_source.cpp:4374-4403`）。

## ログと測定値

この変数名や採用 reserve 値を直接表示するログはない。段階経路では stderr に `FileExpertSource: STRATA_PIN_GUARD=2: page-locking the complement in steps` または `FileExpertSource: STRATA_NUMA_SPLIT: page-locking the complement in steps` が出る。段階で RAM が足りなくなり、全量を登録できない場合は `WARNING: only ... could be page-locked (...); the rest is resident but pageable, so its copies to the GPU go through the CPU (#1250)` が出る。NUMA 以外の guard 経路では段階処理が必ずしも選ばれるわけではなく、既定値のまま一括経路に進む場合にはこの段階 pin ログは出ない（`engine/src/core/expert_source.cpp:4351-4367`, `engine/src/core/expert_source.cpp:4514-4523`）。

対象変数単体の測定値は記載しない。`docs/TROUBLESHOOTING.md:271-279` は Linux の OOM 回避について説明し、reserve の既定を `STRATA_RESIDENT_HEADROOM_GIB`（4 GiB）と記載している。現行コードは `max(headroom_bytes, 2 GiB)` で、headroom が 2 GiB 未満なら 2 GiBを使うため、資料の記述はこの下限条件を省略している。`docs/DETAILS.md:267-286` の resident RAM 説明とも照合したが、対象変数固有の測定値はない。

## 根拠

- `engine/src/core/expert_source.cpp:4323-4327` — 値取得、`atof`、既定 reserve。
- `engine/src/core/expert_source.cpp:4328-4367` — Linux / pin 条件、guard と NUMA 分岐、段階経路選択。
- `engine/src/core/expert_source.cpp:142-165`, `engine/src/core/expert_source.cpp:4460-4523` — reserve を含む停止判定と段階 pin 結果。
- `engine/src/program/generate.cpp:4220-4257`, `engine/src/program/generate.cpp:4277-4285`, `engine/src/program/generate.cpp:12077-12099` — resident mode、headroom、通常経路と soft fallback。
- `engine/include/strata/core/resident_ram_copy.hpp:11-22` — `STRATA_RESIDENT_PIN` と自動 resident copy の pin 判定。
- `engine/sycl/src/core/expert_source.cpp:1661-1675` — SYCL 版の同関数に対象変数の読み取りがないこと。
