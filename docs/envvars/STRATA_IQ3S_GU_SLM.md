# `STRATA_IQ3S_GU_SLM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の IQ3_S gate/up 行カーネルで、入力 activation (`block_q8_1`) を work-group local memory に一時コピーする専用 kernel を選ぶ opt-in 変数。通常の `native_gu_kernel` と比べ、最大 4 entry 分の activation を local memory にまとめてから IQ3_S 行の dot を計算する。変数が変えるのはこの gate/up 計算の kernel 選択であり、読み取り箇所から生成 token やモデル全体の出力への影響は確認できない。読み取りと分岐は `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6040-6050`、専用 kernel は同ファイル `2769-2832` にある。

## 値と判定

`strata::bm_default_on` は `std::getenv` で値を取得する。値が unset または空文字なら引数の既定値を返す。この変数は `false` を既定値として渡すため、unset と空文字はいずれも無効。空でない値は先頭 1 文字だけを見て、`'0'` なら無効、それ以外なら有効とする。文字列全体の parse、数値検証、空白除去、大文字小文字変換はしない。`engine/sycl/include/strata/sycl_queue.hpp:196-200`。

| 条件 | unset / 空文字 | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| SYCL kernel の通常のビルド | 無効（既定値 `false`） | `1`, `true`, `false`, ` 1`, `2` | `0`, `0anything` |

したがって `true` / `false` は真偽語として解釈されず、どちらも先頭が `f` なので有効。` 0` も先頭が空白なので有効。Battlemage 上でもこの変数自体は既定で無効であり、値を明示したときは GPU 世代にかかわらずその値判定が使われる。helper の Battlemage 既定動作とこの呼び出しの `false` 引数は `engine/sycl/include/strata/sycl_queue.hpp:193-200` および `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6040`。

## 有効になる条件

- SYCL backend で IQ3_S (`TG == 21`) の gate/up kernel dispatch に到達すること。format dispatch の形式一覧に `21` が含まれ (`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1058-1060`)、switch が `launch_gu<T>` を呼ぶ (`7874-7878`)。
- `STRATA_OLD_IQ_MMVQ` が有効でないこと。これが有効だと専用 kernel の条件を通らず、通常の経路に進む（判定は `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3932, 6041`）。
- `L.n_embd == 2560` かつ `L.n_ff == 640` であること（同ファイル `6041`）。条件外では SLM kernel を起動せず、後続の通常 kernel 選択に進む。
- `STRATA_IQ3S_GU_ROW_REUSE` による Battlemage の row reuse 分岐が先に kernel を起動して return していないこと。row reuse は既定で Battlemage では有効で、`STRATA_GRID_SLM` が 0 のビルドでは、さらに `STRATA_OLD_IQ_MMVQ` と `STRATA_EXPERT_SPLIT` が無効、`STRATA_GU_LANES` が 8、上記の形状である場合に SLM 分岐より先に実行される（同ファイル `6025-6038`、`engine/sycl/include/strata/sycl_queue.hpp:193-200`）。この経路を避けるには row reuse を明示的に無効にするか、別条件にする必要がある。
- `STRATA_GRID_SLM=1` の build では row reuse 分岐の `#if !STRATA_GRID_SLM` がコンパイルから除外される。SLM 分岐自体はこの macro に囲まれていない（同ファイル `484-488`, `6025-6041`）。

`STRATA_EXPERT_SPLIT` は row reuse 分岐の条件には含まれるが、後続の `STRATA_IQ3S_GU_SLM` 分岐の条件には含まれない。SLM 条件を満たすと split kernel 選択より前に専用 kernel を起動して return する（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6040-6050`）。

## 実行時の詳細

`launch_gu<21>` が呼ばれると、まず（ビルド時に有効な場合）Battlemage row reuse を調べ、そこから return しなければ `STRATA_IQ3S_GU_SLM` の値を評価する。値が有効で、旧 kernel が無効かつ shape が一致すれば、work-group ごとに最大 4 entry の `xq` activation を local memory へコピーし、各 IQ3_S gate/up row の dot 結果を出力先へ格納して return する。専用 kernel の grid と kernel 起動は `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6040-6050`、コピー・entry ごとの dot・格納は同ファイル `2774-2829`。

対象変数の判定は `launch_gu` 内の関数局所 `static const bool` であり、`launch_gu<21>` で条件分岐に初めて到達したときに一度だけ取得される。その後の環境変更は同プロセスの同 template specialization には反映されない。helper はその初回の `s->get_device()` で Battlemage 既定値を判定する。値が false または追加条件を満たさない場合は、`STRATA_EXPERT_SPLIT` などに従う通常の lane/multi kernel 選択へ進む（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6040-6067`）。

## ログと測定値

この変数の分岐に伴う明示的なログ出力やエラー処理は確認できない。専用 kernel の起動失敗時の扱いはこの分岐内に記述されていない（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6040-6050`）。`docs/INTEL.md:602` は row reuse が有効な間は SLM 分岐に到達しない旨を記載しており、コード上も row reuse 条件を満たす場合は先に return する。性能測定値は同資料にこの変数単独の数値がないため記載しない。

## 根拠

- `engine/sycl/include/strata/sycl_queue.hpp:193-200` — Battlemage helper の環境値判定。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:2769-2832` — SLM kernel の activation staging と IQ3_S dot 計算。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1058-1060, 3927-3937, 6020-6067, 7874-7878` — format 一覧、旧 kernel 判定、kernel 選択順、format dispatch。
- `docs/INTEL.md:589-612` — SYCL runtime controls の資料記載と row reuse との関係。
