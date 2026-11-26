# `STRATA_ADAPT_LAG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

適応 VRAM expert tier が入れ替えた expert のコピーを、通常の逐次 verify 経路で何 window 待ってから反映するかを指定する。値 `1` では次の window でコピー完了を待ってから residency 表へ反映し、`2` なら pending のコピーを二つ目の window まで保留してから待つ。適応 tier の候補選択や swap 数を直接変える設定ではない。CUDA/HIP 系と SYCL の `generate.cpp` に同じ読み取りと適用がある（`engine/src/program/generate.cpp:2248-2250, 22835, 25102-25103`; `engine/sycl/src/program/generate.cpp:1388-1390, 12742-12743, 14112-14113`）。

`STRATA_ADAPT_NOWAIT` が `1` の場合、window は待たずに完了状態を問い合わせるため、この lag による待機規則は使われない。コピーが未完了なら pending のまま次へ進む（`engine/src/program/generate.cpp:22818-22835, 24670-24680`; SYCL 側も `engine/sycl/src/program/generate.cpp:13822-13837`）。

## 値と判定

`adapt_lag()` は `std::getenv` の結果を `std::atoi` に渡し、`std::max(1, ...)` で最低値を 1 にする。関数内 `static const` なので、プロセスで最初に呼ばれた時の値を保存し、その後の環境変更は反映しない。整数の全体一致検査や上限 clamp はない（`engine/src/program/generate.cpp:2248-2250`; SYCL: `engine/sycl/src/program/generate.cpp:1388-1390`）。

| 条件 | unset | 有効になる値（例） | 無効・1 に丸められる値（例） |
|---|---|---|---|
| 読み取り時に環境変数をそのまま評価 | `1` | `2`, `3`, `2tail`, ` 2` は `atoi` の結果を最低 1 に clamp した値 | 空文字、`text`, `0`, `-1`, `0anything` は結果が 1 |
| CUDA 起動時に対象 NVIDIA 世代の既定値を適用 | ユーザーが未設定なら一部世代で `2` が設定される（下記） | 明示した値はそのまま判定される | 明示した空文字も「設定済み」扱いで既定値注入を止め、後で `1` に判定される |

`atoi` のため、先頭の空白と数値接頭辞の後ろの文字列は無視される。数値として読めない文字列は `0` 相当となり `1` になる。コード上の正の上限はない。`atoi` の `int` 範囲を超える文字列の結果はこの実装で検査・制限されない。CLI 引数による上書きはなく、他の環境変数が `adapt_lag()` の値自体を変更することもない。

CUDA 側では、全可視 GPU が同じ compute capability の場合に `apply_nv_defaults()` が起動時に呼ばれる。cc 8.6、8.9、6.0 の既定テーブルに `STRATA_ADAPT_LAG=2` がある。cc 8.6 と 6.0 は対応する `STRATA_SM86_PERF` / `STRATA_SM60_PERF` の値が `0` で始まるとテーブルが除外され、cc 8.9 は `STRATA_SM89_PERF` の値が `0` で始まる場合、または `STRATA_DEFAULTS` が完全一致で `026` / `0.2.6` / `v0.2.6` の場合に除外される。いずれもユーザーが変数を設定済みなら値にかかわらず保持するため、空文字も既定値で置換されず、後で `1` に判定される。混在 compute capability の複数 GPU ではこの一括テーブルを適用しない（`engine/src/core/nv_defaults.cpp:14-23, 37-42, 51, 75-85, 164-170`; `engine/src/core/nv_defaults.cpp:222-233`; `engine/include/strata/core/defaults_026.hpp:21-29`; 呼び出し条件 `engine/src/program/generate.cpp:4425-4449`）。SYCL ソースにはこの NVIDIA 既定値適用呼び出しがなく、上記テーブルは適用されない。

## 有効になる条件

- 適応 tier が有効であること。実行時コードは `drive.d.usage` が空でないことを tier 有効の判定に使う。適応頻度・swap 数などで tier が無効なら、この値による pending swap の反映待ちは発生しない（`engine/src/program/generate.cpp:15135, 15249-15252`; SYCL 側の同じ `adapt_lag()` 使用箇所は `engine/sycl/src/program/generate.cpp:12742-12744, 14112-14114`）。
- 逐次 verify window が前回の適応コピーを適用する経路で効く。コードコメントは batch paths、`--pipeline-windows`、peer tier を lag 対象外としている（`engine/src/program/generate.cpp:2243-2247`）。
- `STRATA_ADAPT_NOWAIT=1` のときは各 window で非待機 query を使い、`STRATA_ADAPT_LAG` の閾値で待つ分岐を通らない（`engine/src/program/generate.cpp:22818-22835, 25102-25103`）。
- CUDA の `STRATA_ADAPT_OVERLAP=1` は `adapt_lag() != 1` または `STRATA_ADAPT_NOWAIT` が有効だと起動条件を満たさず、理由を `not with STRATA_ADAPT_LAG / STRATA_ADAPT_NOWAIT` として扱う（`engine/src/program/generate.cpp:15122-15136`）。

## 実行時の詳細

適応 round がコピーを開始すると swap は `pending` に保持され、`pending_age` は 0 に戻る。各逐次 window の前に、`STRATA_ADAPT_NOWAIT` が無効なら pending が空でない場合に age を増やし、`pending_age >= adapt_lag()` でコピー完了を待つ。待機後は RAM 側の交換を commit し、コピー済み expert を host residency 表へ登録し、必要なら device residency 表も更新して pending と age を消去する。したがって lag は「コピー開始後に何回の window を経て表へ反映するか」の閾値で、コピー完了を保証する時間上限ではない。閾値時点で未完了なら event 同期が完了まで待つ（`engine/src/program/generate.cpp:15197-15234, 22818-22835, 24670-24700`; SYCL: `engine/sycl/src/program/generate.cpp:8807-8833, 13822-13848`）。

値は最初の `adapt_lag()` 呼び出しで static cache される。CUDA 起動時の NVIDIA 既定値注入は engine のスイッチ読み取り前に行われるため、既定表の対象世代では初回評価から `2` が見える。ユーザーが設定した変数は既定値注入より優先される。実行中に環境を書き換えても cache 済みの値は変わらない（`engine/src/program/generate.cpp:4425-4449, 2248-2250`; `engine/src/core/nv_defaults.cpp:222-233`）。

CUDA の単独 `strata generate` 経路と serve の verify loop、および SYCL の generate 経路に閾値分岐がある。`strata generate` では `STRATA_TRACE_ADAPT` が設定されていると、非待機適用でコピーが未完了の場合 `strata: PENDING not landed, %zu stay non-resident this window`、完了時には `strata: PENDING landed, %zu experts become resident` を stderr に出す。この診断は `STRATA_ADAPT_LAG` 自体が出すログではない（`engine/src/program/generate.cpp:24670-24683`; SYCL: `engine/sycl/src/program/generate.cpp:13822-13837`）。コピー失敗時は serve 側で `strata serve: adaptive swap copy failed ...`、generate 側で適応 refill 失敗を報告する経路があるが、これらは lag 値の検証エラーではない（`engine/src/program/generate.cpp:15458-15464, 15489-15493`; SYCL: `engine/sycl/src/program/generate.cpp:12744-12746`）。

## ログと測定値

`STRATA_ADAPT_LAG` の値を単独で表示する有効化ログは確認できなかった。`docs/DETAILS.md` は `=2` の測定として Tesla P100 (PCIe 3.0 x16) で 6 組中 6 組 +3.5%、RTX 5070 で 4/6 +0.2%、RTX 3060 で 0/6 -1.3%、また Xeon E5-2673 v3 / DDR3 と RTX 4060 Ti / PCIe 3.0 x8 で 1 window あたり 160 swaps の測定 +7.9% を記載する。これは資料中の測定値であり、ここで再測定した結果ではない（`docs/DETAILS.md:1719`）。同資料は `=2` を CUDA と記載し、sm_86・sm_60 の NVIDIA 既定値を記載するが、現行 `nv_defaults.cpp` には cc 8.9 の既定値もある（`docs/DETAILS.md:1261, 1486-1489`; `engine/src/core/nv_defaults.cpp:75-85`）。

## 根拠

- 値の読み取りと cache: `engine/src/program/generate.cpp:2248-2250`; `engine/sycl/src/program/generate.cpp:1388-1390`
- pending コピー適用: `engine/src/program/generate.cpp:15197-15234, 22818-22835, 24670-24700`; `engine/sycl/src/program/generate.cpp:8807-8833, 12742-12744, 13822-13848, 14112-14114`
- NVIDIA 既定値と適用条件: `engine/src/core/nv_defaults.cpp:37-42, 51, 75-85, 164-170, 222-233`; `engine/src/program/generate.cpp:4425-4449`
- 他設定との適用条件・測定記録: `engine/src/program/generate.cpp:15122-15136, 15249-15252`; `docs/DETAILS.md:1261, 1486-1493, 1719`
