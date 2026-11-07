# `STRATA_ADAPT_FETCH`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

適応 tier が動作している CUDA の `serve` / `generate` で、PCIe share が GPU に送る expert miss を VRAM cache に直接取り込み、同じ layer の未使用 resident expert の slot と入れ替えます。RAM tier から別途 swap するのではなく、PCIe share が元々転送する blob を cache slot に書き、host residency table を更新します。`=1` は適応 tier 自身の swap も通常どおり行い、`=2` は PCIe share がフェッチした layer では、そのフェッチ可能な expert を tier 自身の次回 swap 候補から外します。

## 値と判定

`adapt_fetch()` は `std::getenv` の結果に `std::atoi` を適用し、`std::max(0, std::min(2, ...))` で 0〜2 に clamp します。未設定は 0 です。空文字や数値として始まらない文字列は `atoi` により 0 となり、先頭の空白や符号を含む数値文字列、数値の後ろに文字が付く文字列は `atoi` が変換できる先頭部分で判定します。たとえば `2tail` は 2、`-1` は 0、`9` は 2 です。文字列全体の妥当性検査はありません。

| 入力例 | 判定値 | 結果 |
| --- | ---: | --- |
| unset、空文字、`abc`、`0`、`-1` | 0 | 無効（既定） |
| `1`、`1tail` | 1 | admission 有効、tier 自身の swap も継続 |
| `2`、`2tail`、`9` | 2 | admission 有効、該当 layer の一部の tier swap を抑止 |

値は `adapt_fetch()` が初めて呼ばれたときの `static const` に保存されます。プロセス中に環境を変更しても再評価されません。CLI に同等の値を指定する引数はありません。

## 有効になる条件

値が 1 または 2 でも、次の条件を満たさなければ `fetch_admit` は設定されず機能は動作しません。

- 適応 tier が有効で、`--adapt-every` と `--adapt-swaps` による routing usage table がある。
- residency table と GPU plan があり、PCIe share の数が 0 より大きい。share は `--pcie-frac` などから `drive.d.pcie_num` に設定されます。
- 単一 GPU の serial window 経路である。`serve` では layer split、`--peer-device`、helper GPU、`--adapt-async`、`--pipeline-windows`、`--batch` を拒否し、`generate` では `--spec-split`、layer split、peer tier、helper GPU を拒否します。
- `--pcie-mode` が `dma` / `direct` ではない。実際の `fetch_can()` も plan の `pcie_mode == 2` と `dst2` の存在を要求します。
- `src.complement_ready()` の resident RAM mode ではなく、Foresight swap-space (`fs`) もないこと。また、対象 layer の source が PCIe から読み出せること。
- `serve` では `STRATA_ADAPT_OVERLAP` が有効でないこと。`serve` は `adapt_overlap()` が true の場合に FETCH を停止します。`generate` の同じ条件判定には overlap の確認がありません。

無効となる条件は stderr に `strata serve: STRATA_ADAPT_FETCH is off (...)` または `strata generate: STRATA_ADAPT_FETCH is off (...)` と理由付きで出ます。条件を通った場合は値と閾値を示す初期化ログが stderr に出ます。`=1` / `=2` という有効値だけでは admission が保証されず、実際の window に PCIe miss があり、tier の routing counts と resident slot の比較条件を満たす必要があります。

## 実行時の詳細

値の読み取りと有効条件判定は `serve` / `generate` の起動時に行われます。機能が有効な場合のみ、`STRATA_ADAPT_FETCH_MIN` と `STRATA_ADAPT_FETCH_MARGIN` を `std::atof` で読み、未設定なら `fetch_min=1.0`、`fetch_margin=0.5` を使います。これらは全体文字列の検証や clamp をせず、設定値が変換できなければ `atof` の結果（通常 0）を採用します。

各 window で PCIe share の miss 数が正なら、pool dispatcher は未 resident かつ pinned の routed miss から、その layer の usage が高いものを share 枠数まで選びます。さらに、対象 expert の usage が `fetch_min` 以上で、コピー中でなく、window が使わない resident expert のうち usage が低い候補に対し、`incoming_usage >= resident_usage + fetch_margin` なら既存 VRAM slot を割り当てます。コピー先を staging からその cache slot に切り替え、host residency table では退場 expert を nonresident、新 expert をその slot に設定します。差分は verifier の次回 launch 前に device residency table へ反映されます。候補や閾値を満たさないとき、通常の PCIe staging のままです。

`=2` では PCIe fetch が発生した layer の `fetch_avail` を適応 tier の次回 swap 判定に渡し、pinned な fetch 候補を tier 側の候補から除外します。`=1` はこの抑止を行いません。`STRATA_ADAPT_FETCH_VERIFY` は `generate` だけで設定有無を確認し、空文字を含む設定時に各 admission slot を後から読み戻します。不一致時は `strata: FETCH VERIFY layer ...`、周期ログには `strata: fetch verify: ... admitted slots read back, ... differ` が出ます。`serve` ではこの検査変数を読みません。

観測できる結果は、初期化時の有効 / 無効ログ、`generate` 終了時の stdout `fetch admission ... experts admitted from the PCIe share` 集計です。device residency table の patch に失敗した場合は verifier pre-launch hook が `the residency table update failed: ...` をエラーにし、呼び出し元の window 処理が失敗します。

## 文書・測定値との照合

`docs/DETAILS.md:1076` は CUDA の適用条件に `STRATA_ADAPT_OVERLAP=1` を記していますが、現行の `serve` コードは `adapt_overlap()` が true なら FETCH を無効化します（`src/program/generate.cpp:12772-12784`）。このため、適用条件の説明はソースコードと食い違います。同表に記載された RTX PRO 5000 などの性能・token forcing の数値は資料に記された測定結果であり、この調査では再測定・独立検証していません。

## 根拠

- `src/program/generate.cpp:2005-2011` — `atoi`、0〜2 clamp、unset の既定値、初回評価時の static cache。
- `src/program/generate.cpp:12772-12795,12956-12959,12979-12999` — `serve` の無効条件、ログ、閾値の読み取り、mode 2 の条件、residency table 更新失敗。
- `src/program/generate.cpp:20441-20473,20501-20525` — `generate` の PCIe mode / share、無効条件、閾値・検証変数、residency table 更新。
- `src/core/expert_source.cpp:4734-4738,5013-5029` — pool 側の実効条件と miss 選択。
- `src/core/expert_source.cpp:5095-5137` — staging / cache slot の選択、threshold 比較、residency table 更新と検証記録。
- `src/program/generate.cpp:13054-13065,20592-20603` — `=2` で tier 自身の候補から fetch 可能 expert を外す処理。
- `src/program/generate.cpp:20976-20995,21183-21188` — 読み戻し検証ログと admission 集計。
- `src/core/verify.cpp:2411-2416`, `include/strata/kernels/verify_kernels.hpp:145-152` — CUDA verify 経路で `dst2` を渡す実装経路。
