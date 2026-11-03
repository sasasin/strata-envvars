# `STRATA_SELECT_GEMM_MIN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の native prefill で QSA indexer の block score を計算するとき、oneMKL FP32 GEMM を自動選択する最小 block 数を指定します。単位は block（4 cells）です。この値だけでは GEMM を有効化せず、関連変数 `STRATA_SELECT_GEMM` が自動判定モードで、かつ GPU が Battlemage のときにだけしきい値として参照されます。

## 値と判定

`std::atoll` で符号付き整数に変換します。文字列全体の妥当性は検査しないため、先頭の空白と符号、数値の後ろの文字は `atoll` の規則に従い、数値に変換できない文字列や空文字は 0 になります。

| 値 | 判定結果 |
| --- | --- |
| 未設定 | 2048 blocks |
| `2048` など整数として変換できる値 | 変換結果をしきい値にする |
| 空文字、数値で始まらない文字列 | 0 blocks |
| `0` または負数 | しきい値比較を満たしやすくする（`active` は 0 以上）。ただし自動モードと Battlemage 条件は別途必要 |

たとえば `2048tail` は 2048、`junk` は 0 として扱われます。桁あふれ時の結果には依存できません。値は関数内の `static const` に保存され、最初に QSA block selection のコードへ到達した時点で一度読み取られます。その後に同一プロセス内で環境を変更しても再評価されません。

## 有効になる条件

この変数がしきい値として働くには、以下が必要です。

- SYCL の `Prefill::run_impl()` で QSA layer の prefill selection を実行する。
- `STRATA_SELECT_GEMM` が未設定、または `std::atoi` の結果が負である（自動判定モード）。
- 対象 GPU が `IntelGpuGen::Battlemage` と判定される。
- 現在の selection batch における `active` block 数が、この変数の値以上である。

`STRATA_SELECT_GEMM` が正の値なら block 数や GPU 世代にかかわらず GEMM を選択し、0（未設定時以外）なら GEMM を選択しません。これは `atoi` 判定なので、例として `STRATA_SELECT_GEMM=invalid` も 0 になります。従って、`STRATA_SELECT_GEMM_MIN` を設定しても、`STRATA_SELECT_GEMM=0` の選択を覆しません。

しきい値を満たして GEMM 選択になっても、`STRATA_SELECT_OLD` が設定されている場合、attention scratch がない場合、indexer の形状が `idx_dim == 128` かつ `idx_n_head == 4` でない場合、または計算された GEMM tile が 256 未満の場合は GEMM 経路を実行しません。tile は最大 8192 で、attention scratch の量と batch 幅から計算されます。

## 実行時の詳細

各 QSA selection batch で、最後の query の `n_bid + 1` を `active` として取得し、`active >= STRATA_SELECT_GEMM_MIN` を評価します。GEMM 経路では、pooled indexer keys と batch の queries の FP32 GEMM を tile ごとに実行し、その結果から `qsa_block_scores_reduce()` で block scores を作ります。その後の top-k 選択は GEMM の有無にかかわらず同じ `qsa_block_topk()` に進みます。

GEMM が利用できない場合や条件を満たさない場合は、`STRATA_SELECT_OLD` が設定されていれば warp scorer を使います。そうでなければ先に `qsa_block_scores_tc()` を試し、それが使えない場合に `qsa_block_scores()` へ fallback します。GEMM の実行中に `std::exception` が発生した場合は `stderr` に `prefill: the GEMM block scores failed (%s); the warp kernel instead` を一度だけ出し、`sel_done` を未完了のまま後続 scorer の fallback 判定へ進みます。このログ文言には “warp kernel” とありますが、実際の分岐では `STRATA_SELECT_OLD` が無効なら warp scorer の前に `qsa_block_scores_tc()` を試します。

ソースコメントは GEMM scorer が warp scorer と bitwise 同一ではなく選択結果が変わり得ると記しています。ここではこの実装コメントと分岐のみを確認しており、速度・品質の独立した測定結果は示しません。確認した `docs/DETAILS.md` にこの変数の追加説明はありません。

## 根拠

- `sycl/src/prefill/prefill.cpp:2421-2430` — SYCL prefill の `run_impl()` と model/session 状態の取得。
- `sycl/src/prefill/prefill.cpp:3350-3355` — selection batch と `active` block 数の算出。
- `sycl/src/prefill/prefill.cpp:3356-3375` — 旧 scorer、関連変数の parse、既定値、Battlemage としきい値の分岐、GEMM の追加条件。
- `sycl/src/prefill/prefill.cpp:3376-3401` — tiled GEMM、score reduction、例外ログ、TC/warp scorer と top-k への fallback。
