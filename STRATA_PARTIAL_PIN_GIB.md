# `STRATA_PARTIAL_PIN_GIB`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

SYCL 実装の resident RAM mode で、通常の `sycl::malloc_host` による host allocation が失敗した後、`STRATA_PARTIAL_PIN=1` が有効な場合に GPU 用 alias として扱う RAM 領域の上限を GiB で指定します。対象領域は cache complement の先頭（profile rank の高い expert から配置された範囲）です。上限より後ろは working set に lock を試み、残りは resident RAM として CPU 側の expert 処理に使います。

ただし、現在の SYCL ソースでは既存メモリを GPU に登録する `cudaHostRegister` 相当の処理が DPCT 変換コメント付きの no-op に置き換わっています。その後 `arena` のアドレスを device alias に設定しているため、この経路が実際に物理 pin / GPU 可視登録を行うとはソースから確認できません。ログ上の「registered」表現は実処理の保証として扱えません。

## 値と判定

変換は `std::atof` で行い、文字列全体の妥当性検査はありません。`atof(v) > 0` の場合だけその数値を使い、それ以外は既定値 24 GiB です。結果を `1073741824.0` 倍して `uint64_t` に変換します。

| 値 | `pin_cap` |
|---|---:|
| 未設定 | 24 GiB |
| 空文字、数値に変換できない文字列、`0`、負数 | 24 GiB |
| 正の数 | その数値 GiB（小数可） |
| 数値の後ろに文字が続く値 | `atof` が読む先頭の数値部分。例: `8junk` は 8 GiB |

先頭の空白や `atof` が認識する指数表記も変換に従います。値は正のときに有効ですが、実際の部分 alias 範囲は `min(cache complement の byte 数, pin_cap)` 以下です。2 GiB 未満の上限ではループ条件を満たさず、部分範囲を作りません。expert blob の途中で切らないよう、上限が blob 内に入る場合はその blob の開始 offset まで範囲を下げます。

`nan` は `> 0` 判定に失敗して既定値になります。`inf` や非常に大きな正数は bytes 換算後に `uint64_t` の範囲を超え得ますが、範囲検査はありません。

## 有効になる条件

- Strata の SYCL 実装で resident CPU expert 経路を使い、`pin_cache_complement()` が呼ばれること。呼び出し元は `o.resident_cpu_experts` の場合です。
- `pin` 引数が true であること。`--resident-experts` と `--resident-budget-gib N` は pin を有効にしますが、両方とも `STRATA_RESIDENT_PIN=0` で無効にできます。
- `sycl::malloc_host(bytes, queue)` が失敗し、通常の `std::malloc(bytes)` に fallback すること。host allocation が成功した場合はこの環境変数を読みません。
- `STRATA_PARTIAL_PIN` が `std::atoi(value) != 0` であること。未設定・空文字・`0`・数値変換が 0 になる文字列は無効、`1` や `-1` は有効です。`atoi` は先頭の数値部分を変換します。
- `budget_bytes > 0` であること。明示した `--resident-budget-gib` のほか、`--resident-experts` の soft retry が `kResidentWhatFits`（`~0ull`）を渡す場合も条件を満たします。予算 0 の初回試行では部分範囲を作りません。

`STRATA_PARTIAL_PIN_GIB` 単独では機能を有効にしません。実際に有効とする別スイッチは `STRATA_PARTIAL_PIN` です。

## 実行時の詳細

両環境変数は `pin_cache_complement()` 内の `static` 初期化で読み取られます。初期化は `bytes > 0` の allocation で `pin` が true、かつ `sycl::malloc_host` が失敗して fallback に入ったときに初めて評価されます。その後はプロセス内で値を再評価しません。

`STRATA_PARTIAL_PIN` が有効で予算が正なら、実装は `min(bytes, pin_cap)` から 2 GiB 単位の候補を作り、expert 境界に合わせた先頭範囲を device alias として設定します。残りの範囲は `lock_resident()` に渡されます。部分範囲ができた場合、`pinned()` はその範囲内に完全に収まる expert だけを pinned と判定し、`device_alias()` はその expert の address を返します。GPU の PCIe share を実際に使うには、別途 `--pcie-frac` の share が正で、実行計画に対象 miss が入る必要があります。

ただし、この partial path の `cudaHostRegister` 相当箇所はコメントで「SYCL currently does not support registering of existing host memory」と説明された上で `(void)0` に置換されています。直後の `if (0 == 0)` は常に通り、非 null の `arena` を alias にして `partial_pin` に候補 byte 数を格納します。よって現行ソースはこの byte 範囲を内部的に device-readable / pinned と扱いますが、ドライバーへの登録自体は行っていません。GPU が pageable `malloc` 領域を安全に直接読めることもこのコードからは確認できず、機能の実効性にはこの制限があります。

alias 範囲が設定されると stderr の resident ready ログに pinned byte 数が出て、部分 alias の説明文も付加されます。例外的に alias pointer が null ならその候補では部分範囲が設定されません。`docs/UNSLOTH_Q4.md` は上限の既定値を 24 GiB と記し、RTX 5070 での測定を載せていますが、その数値は資料の記載であり、本調査で再測定していません。

## 根拠

- `sycl/src/core/expert_source.cpp:1650-1654,1855-1928` — resident complement の入口、pin 指定、`sycl::malloc_host` と pageable fallback。
- `sycl/src/core/expert_source.cpp:1927-2007` — 部分範囲の有効条件、`STRATA_PARTIAL_PIN` と本変数の parse、2 GiB 刻み、blob 境界調整、登録 no-op、残余領域の lock。
- `sycl/src/core/expert_source.cpp:2130-2146,2391-2412` — alias byte 数の保存、ログ、部分範囲内だけを pinned 判定する処理。
- `sycl/src/program/generate.cpp:1931-1950,6357-6381` — CLI / `STRATA_RESIDENT_PIN` による pin 設定と resident complement の呼び出し。`--resident-experts` の soft retry は `include/strata/core/expert_source.hpp:565-568` の `kResidentWhatFits` を使います。
- `sycl/src/core/expert_source.cpp:2608-2635,2657-2670` — `--pcie-frac` から計算された miss share と pinned expert の PCIe 計画。
- `docs/UNSLOTH_Q4.md:228-235` — 本変数の既定値・目的・測定についての資料記述。
