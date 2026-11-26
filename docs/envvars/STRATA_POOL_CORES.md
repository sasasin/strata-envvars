# `STRATA_POOL_CORES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU expert pool の worker thread を、指定した論理プロセッサへ順番に pin する実験的な設定。GPU の選択、計算内容、結果を変える分岐ではなく、`ExpertPool` が worker topology と配置を決める際に使う。環境変数を読むのは `engine/src/program/generate.cpp` と `engine/sycl/src/program/generate.cpp` で、共通の設定先は `set_pool_cores()`、適用箇所は `ExpertPool` の構築処理である（`engine/src/program/generate.cpp:4703-4713`、`engine/sycl/src/program/generate.cpp:2238-2248`、`engine/src/kernels/cpu/pool.cpp:88-91,823-839`）。

## 値と判定

エンジンは `std::getenv` で値を読み、`std::string` にコピーする。CLI の `--pool-cores` が空でなければそちらを優先し、空の場合だけ環境変数を使う。環境変数が未設定または空文字なら設定を登録せず、pool の通常配置を使う。設定文字列は `parse_pool_cores()` が全体を走査し、整数リスト・昇順範囲・任意の正の step を解釈する。先頭文字だけの判定や `atoi` ではない（`engine/src/program/generate.cpp:4705-4712`、`engine/sycl/src/program/generate.cpp:2240-2247`、`engine/include/strata/kernels/cpu/pool_plan.hpp:183-224`）。

| 条件 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| エンジンでの解析 | リストなし。既定の worker 配置 | `0`、`2,4,6`、`2-14:2`、` 6 , 2 `。0 以上の十進数字を受け付け、空白は ASCII space と tab を要素の周囲で読み飛ばす | `true`、`off`、`0anything`、`-1`、空要素を含む `0,,2`、降順 `6-2`、step 0 の `0-8:0`、上限超過、または 4096 個を超える異なる番号 |

重複番号は最初の出現だけ残り、順序は維持される。範囲は `first-last[:step]` で、step 省略時は 1。各数値は 100000 を超えると解析失敗になり、最終リストは異なる番号 4096 個まで。`0` は無効化値ではなく論理プロセッサ 0 の指定である（`engine/include/strata/kernels/cpu/pool_plan.hpp:187-224`）。

無効な非空値は起動失敗にはせず、stderr に `strata generate: --pool-cores: <理由>; the pool uses its default placement` を出して既定配置へ戻る。構文が有効でも、実行プロセスが使用できない番号や存在しない番号は topology 確認で除外され、stderr に `strata cpu pool: --pool-cores: ...` の警告が出る。指定がすべて除外されると `no usable logical processor in the list; the pool uses its default placement` と出して既定配置にする。SMT sibling 同士や host thread と同じ processor は警告するが、指定どおり保持する（`engine/src/kernels/cpu/pool.cpp:825-839`、`engine/include/strata/kernels/cpu/pool_plan.hpp:236-275`）。

## 有効になる条件

- `ExpertPool` が構築される実行経路で有効。指定した番号はプロセスが実際に使える processor の topology と照合される。利用できない番号だけのリストは既定配置に戻る（`engine/src/kernels/cpu/pool.cpp:823-839`）。
- SYCL engine の `--no-pool` は pool callback を `nullptr` にするため CPU pool を計算に使わない。ただしこの経路でも `ExpertPool` 自体は構築されるので、設定の解析・配置表示・thread pin の試行は起こり得る（`engine/sycl/src/program/generate.cpp:4803,5933-5938`）。
- `--pool-workers N` が指定されると worker 数は N になり、リストの先頭 N 個を使う。N がリストより大きい場合、余った worker は pin されず OS 配置になる。worker 数が未指定なら有効なリストの長さが worker 数になる（`engine/src/kernels/cpu/pool.cpp:865-881,991-994,1006-1012`）。
- 設定済みの worker 数が CPU pool の既定 worker 数と異なっても、リストから決まった数をそのまま使う。host thread の配置は別設定であり、この変数は host thread を指定しない（`engine/src/kernels/cpu/pool.cpp:865-881`）。
- Linux かつ `STRATA_GPU_METAL` でないビルドには追加の相互作用がある。複数 NUMA node などの条件を調べる GPU node 自動配置処理で、空でない `--pool-cores` または `STRATA_POOL_CORES` は「ユーザーが thread を配置した」印になり、GPU node に合わせたプロセス CPU 制限を自動適用しない理由になる。これは値の構文解析より前の判定なので、無効な非空値もこの判定では印として扱われる。1 NUMA node、`STRATA_NUMA_CARD` による停止、または他の先行条件で自動制限の判断が終わる場合は、この印による差はない（`engine/src/program/generate.cpp:4615-4627,4655-4664`、`engine/include/strata/kernels/cpu/card_node.hpp:118-149`）。
- サーバー設定の `pool_cores` は `--pool-cores` 引数に変換される。サーバー側では engine args に同引数があれば設定値を追加しない。エンジン側では非空の CLI 値が環境変数より優先される（`terminal/serve/server_parts/engines.py:857-877`、`engine/src/program/generate.cpp:4705-4708`）。

## 実行時の詳細

値は engine 起動時、worker pool を作る前に読み取られ、解析後の番号リストをプロセス内の `g_pool_cores` に設定する。読み取り後に環境を再確認するループやリクエスト単位の更新はない。通常の CUDA/HIP 系 `generate` は pool 構築前の Linux NUMA 判定でも同じ環境変数を参照し、その後 pool 用に再度参照する。SYCL 系は pool 構築前の設定箇所で参照する（`engine/src/program/generate.cpp:4615-4664,4703-4713`、`engine/sycl/src/program/generate.cpp:2232-2248`、`engine/src/kernels/cpu/pool.cpp:88-91`）。

pool は番号を topology と照合し、採用された順で worker thread に割り当てる。各 thread は起動時に pin を試みる。OS の affinity 設定に失敗した場合は既存 affinity を保持する。非 Windows では `strata cpu pool: affinity for worker %d (CPU %d) failed: %d; previous affinity kept`、Windows では `strata cpu pool: SetThreadGroupAffinity for worker %d (group %u, mask 0x%llx) failed: %lu; previous affinity kept` を stderr に出す。pool 起動時には worker の論理プロセッサ配置を stderr に表示する（`engine/src/kernels/cpu/pool.cpp:624-634,991-1012`、`engine/src/kernels/cpu/pool_affinity_win.hpp:17-25`、`engine/src/program/generate.cpp:9022-9036`、`engine/sycl/src/program/generate.cpp:4810-4820`）。

## ログと測定値

無効なリスト、使用できない processor、同じ物理 core の sibling、host thread と同じ processor、OS の pin 失敗は上記のとおり stderr で観測できる。構文エラーは警告して既定配置を選び、環境変数自体を理由に終了する経路は確認できない。起動時の配置表示は `strata generate: %d pool workers on logical processors ...` と `CPU workers on logical processors ...`（SYCL では前者と `pool.placement_line()`）である（`engine/src/program/generate.cpp:9022-9036`、`engine/sycl/src/program/generate.cpp:4810-4820`）。

`docs/DETAILS.md` は `--pool-cores` / `STRATA_POOL_CORES` について worker の配置、リスト形式、worker 数との関係を説明している。性能測定値はこの文書では引用しない（`docs/DETAILS.md:1425-1431`）。

## 根拠

- 環境変数の読み取り、CLI 優先、構文エラー時の fallback: `engine/src/program/generate.cpp:4703-4713`、`engine/sycl/src/program/generate.cpp:2238-2248`
- リスト構文と上限: `engine/include/strata/kernels/cpu/pool_plan.hpp:183-224`
- topology による除外と警告: `engine/include/strata/kernels/cpu/pool_plan.hpp:236-275`、`engine/src/kernels/cpu/pool.cpp:823-839`
- worker 数・pin・配置表示: `engine/src/kernels/cpu/pool.cpp:865-881,991-1012`
- Linux 非 Metal の GPU NUMA 自動配置との相互作用: `engine/src/program/generate.cpp:4615-4664`、`engine/include/strata/kernels/cpu/card_node.hpp:118-149`
- サーバー設定から engine CLI への変換: `terminal/serve/server_parts/engines.py:857-877`
- 説明資料との照合: `docs/DETAILS.md:1425-1431`
