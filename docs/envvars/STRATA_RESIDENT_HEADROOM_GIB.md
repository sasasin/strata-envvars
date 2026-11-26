# `STRATA_RESIDENT_HEADROOM_GIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

resident expert RAM mode が、GPU cache にない expert を RAM にコピーする際に空けておく headroom（GiB）を指定する。値は「残す RAM 量」であり、RAM copy の予算そのものではない。CUDA/HIP の `engine/src/program/generate.cpp` では `--resident-experts`、`--resident-budget-gib` と resident RAM fallback に使われ、SYCL 版では前二つの CLI mode に使われる。GPU 上の expert cache の容量はこの変数で直接変更しない（設定箇所: `engine/src/program/generate.cpp:4221-4229,4250-4257,8613-8618`、`engine/sycl/src/program/generate.cpp:2184-2203`）。

## 値と判定

engine は `getenv` で設定の有無を調べ、値を `std::atof` に渡す。設定文字列全体の妥当性検査はなく、変換値が `>= 0.0` の場合だけ採用する。採用値に `1073741824.0` を掛けて byte にし、`uint64_t` にキャストする。明示的な上限・clamp はない（`engine/src/program/generate.cpp:4223-4229,4253-4257,4283-4285,8613-8618`、`engine/sycl/src/program/generate.cpp:2184-2193,2194-2203`）。

| engine 経路 | unset | 設定時に有効になる値 | 無効値・扱い |
|---|---|---|---|
| CUDA/HIP: `--resident-experts` または `--resident-budget-gib N`（N > 0） | 既定 4 GiB | `atof(value) >= 0` のとき変換した GiB 値。例: `0`、`2.5` | `atof(value) < 0` または NaN は無視し、4 GiB のまま。後段で有効な `--ram-keep-gib` / `STRATA_RAM_KEEP_GIB` がより大きければそちらまで増える（ただしこの変数が有効値なら増やさない）。 |
| CUDA/HIP: RAM keep の適用後 | 変数が未設定または負値なら、resident headroom は `--ram-keep-gib` / `STRATA_RAM_KEEP_GIB` の値以上 | 有効値は `ram_keep` より小さくても優先される | 同上。 |
| CUDA/HIP: expert arena の RAM 不足 fallback | Windows 8 GiB、その他 4 GiB の安全 headroom と `ram_keep` の大きい方 | 有効値が安全 headroom より小さくても置き換える | 負値または NaN は無視され、安全 headroom / `ram_keep` に戻る。 |
| SYCL: `--resident-experts` または `--resident-budget-gib N` | 4 GiB | `atof(value) >= 0` の値 | 負値または NaN は無視して 4 GiB。 |

空文字、`true`、`0anything`、数値の後ろに文字が付いた値は、`atof` が変換できた先頭部分で判定されるため、いずれもこの実装では通常 0 として受理される。`2.5GiB` は 2.5 として受理される。先頭の空白は `atof` の変換に従い、文字列比較や大文字小文字判定はない。負数は無視される。非常に大きい値や正の無限大には上限検査がなく、byte への浮動小数点から整数への変換が範囲外となる場合の安全な扱いは実装されていない（同上）。

## 有効になる条件

- CUDA/HIP では `--resident-experts` または正の `--resident-budget-gib` を指定したとき、値が `o.resident_headroom` に入る。これらの CLI mode を使わない場合、変数は通常の resident RAM mode を単独では有効にしない（`engine/src/program/generate.cpp:4221-4257,11934-11935,12077-12080`）。
- CUDA/HIP の自動 fallback では、expert arena の読み込みが RAM 不足で失敗し、fallback が許可され、かつ `--expert-profile` が指定され、既に `--resident-cpu-experts` でなく、`STRATA_ARENA_FALLBACK_RESIDENT` の先頭文字が `0` でない場合に、RAM copy の headroom と予算に使われる。profile がない場合や `STRATA_ARENA_FALLBACK_RESIDENT=0` の場合はこの RAM copy fallback に入らない（`engine/src/program/generate.cpp:8602-8618,8890-8908`）。
- CUDA/HIP の arena fallback では、`STRATA_ARENA_RAM_FALLBACK=0`、明示的な `--ple-io ram`、または `--shared-expert-arena` により fallback が許可されない場合、この変数の headroom は RAM copy fallback に使われない（`engine/src/program/generate.cpp:8600-8604,8859-8863`）。
- SYCL 版では `--resident-experts` / `--resident-budget-gib N` の解析時だけこの変数を読み取る。CUDA/HIP 版にある `STRATA_RAM_KEEP_GIB` / `--ram-keep-gib` による後段の headroom 調整と arena RAM fallback の読み取りは SYCL 側にない（SYCL 側の直接読み取り箇所: `engine/sycl/src/program/generate.cpp:2184-2203`）。
- `app/host/server/native-resources.mjs` の work profile は、古い engine で RAM 設定を自動構成する場合、既存の `STRATA_RESIDENT_HEADROOM_GIB` がなければ設定値を追加する。一方、engine が `STRATA_RAM_KEEP_GIB` を扱える場合はそちらを優先して設定する。ユーザーがこの変数を設定済みなら、アプリの自動 headroom 値で上書きしない（`app/host/server/native-resources.mjs:89-112`）。`withRamReserve` は設定済み headroom が reserve より小さい場合に reserve 値へ引き上げる（同 `138-147`）。

## 実行時の詳細

CLI 引数の解析中に、`--resident-experts` または `--resident-budget-gib` の各分岐で環境を読み取る。CUDA/HIP では引数解析後にも `STRATA_RAM_KEEP_GIB` 等との優先判定があり、arena を開く直前に fallback 用の headroom をもう一度計算する。static cache はなく、engine 起動ごとに評価される。起動後の環境変更を再読込する経路はない（`engine/src/program/generate.cpp:4221-4229,4250-4285,8613-8618`）。SYCL の読み取りも CLI 引数解析時である（`engine/sycl/src/program/generate.cpp:2184-2203`）。

resident mode では算出 headroom と RAM budget を `pin_cache_complement` に渡す。resident experts の RAM 配置により、GPU cache にない expert のうちどれを RAM copy に置き、どれを model files から読むかが変わる。arena 不足時の CUDA/HIP fallback は、利用可能 RAM から headroom を引いて resident budget を算出する。空き RAM が headroom に 1 GiB を足した量以下なら fallback budget は 0 となり RAM copy を作らない（`engine/include/strata/core/ple_residency.hpp:174-182`、`engine/src/program/generate.cpp:8898-8908,12077-12080`、`engine/sycl/src/program/generate.cpp:7098-7107`）。

明示的な `--resident-experts` では全 complement が収まらない場合、soft mode が有効なら収まる分だけを残す fallback に進む。そうでなく resident mode / budget も作れない場合は起動エラーとなる。これは headroom の値だけで成功が保証されるわけではなく、モデル・GPU cache・実際の空き RAM に依存する（`engine/src/program/generate.cpp:12091-12117,12203-12217`、`engine/sycl/src/program/generate.cpp:7100-7151`）。

## ログと測定値

成功した resident mode は stderr に `strata generate: resident RAM mode: ... GiB of experts in RAM ...` を出す。全 complement が収まらず soft fallback した場合は `WARNING: the whole resident RAM mode does not fit` と、RAM に残した expert 量・残りを model folder から読む旨を出す。resident mode / budget を確保できない経路は、警告付きで mmap から読むか、`strata generate: CPU expert residency: ...` で終了コード 1 になる（`engine/src/program/generate.cpp:12091-12217`、`engine/sycl/src/program/generate.cpp:7100-7151`）。

CUDA/HIP の arena RAM fallback に入ったときは、まず `strata generate: not enough RAM for the expert arena (...): this run reads the experts from the file, like --mmap-experts ...` を stderr に出す。`--serve` では同じ案内を stdout にも出す。resident RAM fallback の選択後は resident mode のログも出る（`engine/src/program/generate.cpp:8876-8908,12196-12202`）。

この変数単独の性能測定値は、今回確認した現行ソース上にないため記載しない。

## 根拠

- 変数名の全参照を `rg` で確認。値を読む engine 実装は CUDA/HIP の `engine/src/program/generate.cpp:4227-4228,4255-4256,4283-4285,8613-8618` と SYCL の `engine/sycl/src/program/generate.cpp:2191-2192,2202-2203`。
- 値の単位変換と fallback 方針: `engine/include/strata/core/ple_residency.hpp:140-182`。
- arena RAM 不足時の判定・fallback 条件: `engine/src/core/expert_source.cpp:6533-6558,6604-6618`、`engine/src/program/generate.cpp:8600-8618,8876-8908`。
- resident budget/headroom の適用と結果ログ: `engine/src/program/generate.cpp:12077-12117,12196-12217`、`engine/sycl/src/program/generate.cpp:7098-7151`。
- native app の自動設定・ユーザー値の保持: `app/host/server/native-resources.mjs:89-112,138-147`。
