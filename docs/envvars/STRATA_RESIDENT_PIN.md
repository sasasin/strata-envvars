# `STRATA_RESIDENT_PIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

expert の GPU cache 外を RAM にコピーする resident RAM mode で、そのコピーを page-locked として確保するか、通常の pageable RAM として確保するかを選ぶ。未設定を含め、値全体が文字列 `"0"` のときだけ pageable になる。その他の値は page-lock を要求する。対象のコピーは `--resident-experts`、正の `--resident-budget-gib`、および CUDA/HIP 系エンジンの expert arena 不足時に作られる自動 RAM copy。ページロックの指定はコピー内容や expert の選択順位を変えず、RAM copy とファイル読み出しの割り振りを指定するものではない（`engine/include/strata/core/resident_ram_copy.hpp:11-23`、`engine/src/program/generate.cpp:4221-4257, 8890-8908`、`engine/sycl/src/program/generate.cpp:2184-2203`）。

## 値と判定

CUDA/HIP 系では `resident_pin_from_env()` が null でない値を `strcmp(value, "0") == 0` で比較する。SYCL 系も `std::string(v) == "0"` で同じ完全一致判定をする。数値変換、trim、大文字小文字変換はしない。無効値によるエラーや警告はなく、完全一致しなければ pin 指定になる（`engine/include/strata/core/resident_ram_copy.hpp:13-15`、`engine/sycl/src/program/generate.cpp:2189-2190, 2200-2201`）。

| 条件 | 未設定 | pageable になる値 | pin 指定になる値 |
| --- | --- | --- | --- |
| `--resident-experts`、正の `--resident-budget-gib`、または CUDA/HIP 系自動 RAM copy | pin | `0` | 空文字、`1`、`true`、`false`、`00`、`0anything`、前後に空白がある ` 0 ` など |
| `--resident-cpu-experts` 単独 | このフラグは本変数を読まず、初期値の pageable のまま | 本変数を読まない | 本変数を読まない |

## 有効になる条件

- `--resident-experts` は `--mmap-experts` と静的な `--expert-profile` を伴う resident RAM mode にする。要件を満たさない場合、エンジンは `--resident-cpu-experts requires --mmap-experts and a static --expert-profile` と stderr に出して終了コード 2 で終了する（`engine/src/program/generate.cpp:4221-4228, 4870-4872`、SYCL は `engine/sycl/src/program/generate.cpp:2184-2193, 2339-2341`）。
- 正の `--resident-budget-gib` も env 値を読み、mmap と resident CPU experts を有効にする。値 0 は `--ssd-experts` と同じ設定にして resident CPU experts と pin を無効化し、負数や NaN は `N >= 0` エラーで終了する。したがって 0 の budget では本変数は読まれない（`engine/src/program/generate.cpp:4242-4257`）。SYCL は `--resident-budget-gib` に `N > 0` を要求し、0 以下で終了コード 2。ここでも有効な値の場合だけ本変数を読む（`engine/sycl/src/program/generate.cpp:2194-2203`）。
- `--resident-cpu-experts` 単独は CPU resident mode を指定するが、`resident_pin` の初期値は false で、本変数を読む分岐を通らない。フラグの指定順が後で `--resident-experts` または正の budget に至ればその分岐で読み直して設定される。後続の `--ssd-experts` または CUDA/HIP 系の `--resident-budget-gib 0` は pin を false に戻す（`engine/src/program/generate.cpp:876-891, 4220-4257`、SYCL は `engine/sycl/src/program/generate.cpp:554-566, 2182-2203`）。
- CUDA/HIP 系では expert arena が RAM 不足で開けず、かつ静的 expert profile があり、既に resident mode ではなく、`STRATA_ARENA_FALLBACK_RESIDENT` が先頭文字 `0` で始まらない場合に、自動 RAM copy fallback が本変数を読む。profile がない場合や fallback を無効化した場合はこの読み取り・RAM copy が行われない（`engine/src/program/generate.cpp:8602-8607, 8876-8908`）。SYCL の `generate.cpp` にこの自動 fallback の読み取り箇所はない。
- `terminal/strata_control/setup_config.py` は ROCm の `resident` 設定時に run config の env へ `STRATA_RESIDENT_PIN="0"` を書く。設定を再生成する際、setup 自身が書く `"0"` は更新し、手動設定の別値（例 `"1"`）は維持する（`terminal/strata_control/setup_config.py:474-475`、`terminal/setup.py:7544-7553, 7569-7579`）。

## 実行時の詳細

環境変数は generate の CLI 引数を走査して該当する分岐に入った時点で読み、値を `o.resident_pin` に格納する。自動 fallback の場合は arena 不足が確定した分岐で読む。共通 helper に static cache はなく、該当分岐ごとに `getenv` を呼び、以降はオプション値を resident source の `pin_cache_complement()` に渡す。読み取り後のプロセス環境変更を再取得する処理は確認できない（`engine/src/program/generate.cpp:4221-4257, 8898-8903`、`engine/include/strata/core/resident_ram_copy.hpp:13-23`、SYCL は `engine/sycl/src/program/generate.cpp:2184-2203, 7098-7099`）。

resident source は GPU cache に入っていない expert を RAM copy の対象にし、profile 順で budget 内に収まる expert を選ぶ。`pin=false` では pageable RAM を確保する。`pin=true` では page-locked allocation を試み、失敗した場合は pageable 確保を試す。したがって `"0"` は確保するコピーをなくす値ではなく、コピーの pin 指定を外す値である。RAM 不足などで resident mode 自体を作れない場合の fallback は `resident_soft` / budget に従い、file source へ戻るか警告・終了となる（`engine/src/core/expert_source.cpp:3985-4003, 4311-4314, 4380-4402, 4420-4429`、SYCL は `engine/sycl/src/core/expert_source.cpp:1661-1698, 1866-1936`、呼び出し結果は `engine/src/program/generate.cpp:12079-12107, 12203-12217`、`engine/sycl/src/program/generate.cpp:7098-7116, 7131-7151`）。

`--resident-experts` では expert cache が GPU に保持する分を除いた complement を RAM に置く。正の budget と自動 fallback では profile 順に指定 budget 分まで RAM に置き、残りはファイルから読む。budget や利用可能 RAM による clamp はこの変数とは独立して行われる（`engine/src/core/expert_source.cpp:4044-4066, 4131-4151`、`engine/src/program/generate.cpp:8892-8908`）。

## ログと測定値

変数自体についての警告や無効値エラーはない。resident complement 確保時には stderr に `FileExpertSource: allocating ... page-locked cache complement` または `... pageable resident cache complement` が出る。完了時の `FileExpertSource: ... cache complement ready: resident ... GiB, pinned ... GiB ...` は結果を示す。pin 要求が失敗して pageable 確保へ進む場合は `FileExpertSource: ...; trying pageable memory` が出る（`engine/src/core/expert_source.cpp:4311-4314, 4391-4402, 4734-4738`、SYCL は `engine/sycl/src/core/expert_source.cpp:1866-1869, 1922-1926, 2153-2157`）。

resident RAM mode の確保失敗は、soft mode なら `WARNING: the resident RAM mode does not fit (...)` を出して mmap/file cache の経路へ移る。budget mode なら `WARNING: the RAM budget ... cannot be kept (...)` を出し、file tier に切り替える。soft mode でも budget mode でもない resident mode は `strata generate: CPU expert residency: ...` を stderr に出して終了コード 1 となる（`engine/src/program/generate.cpp:12203-12217`、SYCL は `engine/sycl/src/program/generate.cpp:7138-7151`）。

測定値は記載しない。ソース内コメントや設計資料にある測定結果は、この変数の実装動作そのものを再測定した結果ではないため。

## 根拠

- `engine/include/strata/core/resident_ram_copy.hpp:11-23`
- `engine/src/program/generate.cpp:4220-4257, 8602-8618, 8876-8908, 12079-12217`
- `engine/src/core/expert_source.cpp:3985-4003, 4044-4066, 4311-4432, 4724-4738`
- `engine/sycl/src/program/generate.cpp:2182-2203, 2339-2349, 7098-7151`
- `engine/sycl/src/core/expert_source.cpp:1661-1698, 1739-1790, 1866-1938, 2141-2157`
- `terminal/strata_control/setup_config.py:474-475`
- `terminal/setup.py:7544-7553, 7569-7579`
