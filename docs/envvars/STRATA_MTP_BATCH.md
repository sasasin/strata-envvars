# `STRATA_MTP_BATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MTP drafter があるとき、プロンプト読み込み中に draft layer の K/V を prompt path の `Prefill::draft_kv` でまとめて計算する経路を止める。値が無効化条件に当たると、この関数は理由 `STRATA_MTP_BATCH=0` で decline し、呼び出し元は drafter 自身の `MtpDrafter::prefill` を実行する。MTP 自体や decode 時の `--batch-mtp` を無効化する設定ではない。CUDA/HIP と SYCL の両実装に読み取り箇所がある。`engine/include/strata/prefill/prefill.hpp:60-67`、`engine/src/prefill/prefill.cpp:2991-3013`、`engine/sycl/src/prefill/prefill.cpp:1857-1873`。

## 値と判定

両 backend とも `std::getenv` の結果を関数内 `static const bool off` に初回呼び出し時だけ保存し、値が非 null かつ `v[0] == '0'` のときだけ batched 経路を止める。文字列全体や数値としての妥当性は検査しない。したがって、unset・空文字・`1`・`true`・`false`・先頭が空白の ` 0` は止めず、`0`、`0anything`、`00`、`0.5` は止める。大文字小文字は関係しない。プロセス中に環境を変更しても、この static 値は再評価されない。CUDA/HIP: `engine/src/prefill/prefill.cpp:2999-3008`。SYCL: `engine/sycl/src/prefill/prefill.cpp:1857-1869`。

| 条件 | unset | batched 経路を止める値 | 止めない値 |
|---|---|---|---|
| CUDA/HIP `Prefill::draft_kv` | 有効（`off == false`） | 先頭文字が `0`（例: `0`, `0abc`） | 空文字、`1`, `true`, `false`, ` 0` |
| SYCL `Prefill::draft_kv` | 有効（`off == false`） | 先頭文字が `0`（例: `0`, `0abc`） | 空文字、`1`, `true`, `false`, ` 0` |
| Metal の CUDA/HIP 側実装 | この関数では判定前に decline | 適用なし | 適用なし |

数値変換、境界値、無効文字列時の fallback はない。条件は先頭 1 文字の比較だけである。Metal は `STRATA_GPU_METAL` 分岐で先に戻るため、この読み取りに到達しない（`engine/src/prefill/prefill.cpp:2994-3001`）。

## 有効になる条件

- `--mtp` 等で MTP drafter が有効になり、prompt chunk の callback が `draft_kv` を呼ぶ必要がある。単一 GPU の generate では `o.mtp` が空でないとき callback が登録される（`engine/src/program/generate.cpp:24137-24149`、SYCL: `engine/sycl/src/program/generate.cpp:13360-13371`）。serve 側も `use_mtp` のとき batched 経路を試す（`engine/src/program/generate.cpp:14777-14798`、SYCL: `engine/sycl/src/program/generate.cpp:8622-8628`）。
- 1 GPU では MTP 使用時に prompt path が batched 経路を試す。CUDA/HIP の multi-GPU 層分割では `STRATA_SPLIT_MTP_BATCH` が有効で、drafter が先頭 stage ではなく (`!mtp_first`)、かつ split の最終 stage に native embedding がある場合に限って試す。split 用の変数は `split_env_on` が `atoi(value) != 0` で判定する別設定であり、この文書の変数とは独立している（`engine/include/strata/program/draft_kv_plan.hpp:16-42`、呼び出し: `engine/src/program/generate.cpp:14779-14785`）。SYCL の serve は `multi_gpu` の場合 batched 経路を呼ばない（`engine/sycl/src/program/generate.cpp:8622-8627`）。
- `STRATA_MTP_BATCH` が停止値でないことに加え、draft K/V が paged (`kv_mode == 0`) か、ring (`kv_mode == 2`) かつ `STRATA_MTP_BATCH_RING` が停止値でない必要がある。hybrid K/V は対象外。同じ device 上であること、prompt scratch region があることも必要（CUDA/HIP: `engine/src/prefill/prefill.cpp:3007-3013`、SYCL: `engine/sycl/src/prefill/prefill.cpp:1867-1873`）。
- MTP の必要 tensor と gather 可能な token embedding があり、scratch が 64 行分以上必要。満たさない場合も batched 計算は decline して drafter 自身の経路に戻る（CUDA/HIP: `engine/src/prefill/prefill.cpp:3018-3052`、SYCL: `engine/sycl/src/prefill/prefill.cpp:1878-1913`）。

`--batch-mtp` は batch decode の別機能であり、この設定の有効条件ではない（CLI の説明: `engine/src/program/generate.cpp:1318-1321`）。

## 実行時の詳細

CUDA/HIP の通常の単一 GPU generate は各 prompt chunk で `draft_kv` を呼び、成功すれば batched pass でその chunk の draft K/V を計算する。false かつ error が空なら `mtp.prefill` にフォールバックする（`engine/src/program/generate.cpp:24142-24149`）。SYCL generate も同じく `draft_kv` の false 後に `mtp.prefill` を呼ぶ（`engine/sycl/src/program/generate.cpp:13365-13371`）。serve の単一 GPU 経路も false なら drafter の prefill を実行する（CUDA/HIP: `engine/src/program/generate.cpp:14797-14798`、SYCL: `engine/sycl/src/program/generate.cpp:8626-8628`）。

したがって停止値は prompt path の batched K/V 計算を選ばなくするが、MTP drafter 自身の prompt K/V 計算は残る。source comment は batched pass と drafter 自身の pass で draft 値が bit-identical とは限らず、target の token logits は変わらないと記す（`engine/include/strata/prefill/prefill.hpp:60-65`）。別の CLI 優先順位やこの設定値による終了経路はない。fallback 自体が error を返せば chunk callback は失敗し、そのエラーを呼び出し元へ返す。

設定の読み取りは `draft_kv` の最初の呼び出し時であり、起動時ではない。CUDA/HIP と SYCL のそれぞれで関数内 static に cache されるため、同一プロセス内の後続 prompt や要求で環境変数を変更しても反映されない（`engine/src/prefill/prefill.cpp:3001`、`engine/sycl/src/prefill/prefill.cpp:1861`）。

## ログと測定値

通常の単一 GPU decline は `why` に理由を返すだけで、通常経路ではその理由を表示しない。serve の CUDA/HIP multi-GPU 層分割では、`STRATA_SPLIT_MTP_BATCH` により試行が有効になったうえで decline した場合、プロセスにつき一度 `strata serve: STRATA_SPLIT_MTP_BATCH=1 declined, the drafter's own pass runs: %s` を stderr に出す。停止値の場合の理由文字列は `STRATA_MTP_BATCH=0`（`engine/src/program/generate.cpp:14781-14795`、設定理由: `engine/src/prefill/prefill.cpp:3007-3009`）。`STRATA_SNAPSHOT_VERIFY` が設定されている serve は、fallback 後に `DRAFT_PREFILL path=token` を出す（CUDA/HIP: `engine/src/program/generate.cpp:14806-14808`、SYCL: `engine/sycl/src/program/generate.cpp:8633-8635`）。

`docs/DETAILS.md` にこの変数固有の説明や測定値は見当たらない。`docs/SETTINGS.md` には関連する `STRATA_MTP_BATCH_F16` と `STRATA_MTP_BATCH_RING` は載るが、この変数自体の行はない（`docs/SETTINGS.md:421-422`）。リポジトリ内の `terminal/tools/conversation_cache_growth.py:98-103` と `terminal/tools/conversation_cache_disabled.py:128-133` は子プロセス環境に `STRATA_MTP_BATCH=1` を設定している。

## 根拠

- CUDA/HIP の値判定・decline: `engine/src/prefill/prefill.cpp:2991-3013`
- SYCL の値判定・decline: `engine/sycl/src/prefill/prefill.cpp:1857-1873`
- 呼び出しと fallback: `engine/src/program/generate.cpp:14777-14798`、`engine/src/program/generate.cpp:24137-24149`、`engine/sycl/src/program/generate.cpp:8622-8628`、`engine/sycl/src/program/generate.cpp:13360-13371`
- split 経路の gate: `engine/include/strata/program/draft_kv_plan.hpp:16-42`
- 実装差と対象出力に関する source comment: `engine/include/strata/prefill/prefill.hpp:60-67`
