# `STRATA_SPLIT_MTP_BATCH`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。作業開始時の Strata 作業ツリーは `main` で clean。

## 役割

`--serve` の層分割（複数 GPU）で MTP draft layer の prompt K/V を作る方法を切り替えます。有効にすると、prompt を処理した最後の stage の `Prefill::draft_kv()` がチャンク単位のバッチ処理を試します。無効または条件不足なら、従来どおり `MtpDrafter::prefill()` が処理します。単一 GPU の serve では同じバッチ経路が環境変数と無関係に計画されるため、この変数は実質的に層分割用の opt-in です。

バッチ経路では draft K/V の射影に、利用可能な場合 Q8_1 x Q8_0 MMQ を使います。従来経路と丸めが異なるため draft の内容や採用数は変わり得ます。verify window が実モデルで token を検証して出力を決める構造です。

## 値と判定

値は `split_env_on()` が `std::atoi()` で整数変換し、結果が `0` かどうかで判定します。文字列全体の厳密な数値検証ではありません。

| 値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字、数字で始まらない文字列 | `atoi` の結果が 0 となり OFF |
| `0`、`00suffix`、`-0` など変換結果が 0 | OFF |
| `1`、`-1`、`2suffix` など変換結果が非 0 | ON |

`atoi` の通常の規則により、先頭空白と符号を受け付け、最初の数字列の後ろは判定に使いません（例: `  +2tail` は ON、`0tail` は OFF）。大文字小文字の比較はありません。コードは変換エラーや整数範囲外を個別に検査せず、clamp もしません。

## 有効になる条件

変数によるバッチ化には、serve で MTP (`--mtp`) が有効で、実際に異なる GPU を使う layer split が必要です。設定値が ON でも split の最終 stage に GGUF 形式の token embedding table がない（`--native` pack ではない）場合、計画段階で従来経路に戻ります。

計画を通過した後も `Prefill::draft_kv()` が実行条件を確認します。少なくとも次のいずれかに当たる場合は理由を返して decline し、draft の従来 pass に戻ります。

- `STRATA_MTP_BATCH=0`（先頭文字が `0`）でバッチ経路自体が停止されている。
- prompt scratch がない、チャンク行数が 0 以下、または 64-row batch に足りる scratch がない。
- draft K/V が通常の paged mode でない。ring mode は利用可能だが、`STRATA_MTP_BATCH_RING` の先頭文字が `0` なら対象外。hybrid K/V も対象外。
- drafter と prompt stage の GPU が異なる。
- 必要な drafter tensor が欠けている、または token embedding をこの経路で gather できない。

ring の batch size は、同じ batch 内のセルが ring slot を共有しないよう制限されます。MMQ が使えない、または行列サイズに合わない場合も、この変数による全経路の失敗とはせず、`draft_kv()` 内で native GEMM を選びます。

## 実行時の詳細

`generate.cpp` は `STRATA_SPLIT_MTP_BATCH` を `split_env_on()` に渡し、その結果と `use_mtp`、`multi_gpu`、native embedding の有無で計画を作ります。環境値の結果は関数内の `static const bool` に保存されるため、宣言に初めて到達した後の同一プロセス内の環境変更では再評価されません。要求値は起動時または初回 prompt chunk callback の設定時に反映させる必要があります。

層分割で有効化され、追加条件も通ると、最後の stage の `Prefill` に対し `draft_kv(mtp, R_rows, next_tokens, T, p0, ...)` を呼び、当該 chunk の draft K/V をまとめて書きます。成功時に stderr へ `strata serve: draft layer prompt K/V batched on CUDA%d (E-9 on the layer split, K/V mode %d)` を一度出します。計画または `draft_kv()` が条件不足で decline し、エラー文字列が空なら、stderr に `strata serve: STRATA_SPLIT_MTP_BATCH=1 declined, the drafter's own pass runs: <reason>` を一度出し、従来の `mtp.prefill()` を実行します。バッチ処理自体のエラーで `e` が設定されたときは旧方式への fallback ではなく、その prompt callback は失敗します。

単一 GPU では `plan()` が環境値より先に単一 GPU 用バッチ経路を選ぶので、この変数を unset または OFF にしても `Prefill::draft_kv()` は試されます。ただし `STRATA_MTP_BATCH` など `draft_kv()` 側の条件による decline は共通です。MTP を使わないときは draft K/V 処理そのものがありません。

## 文書・測定との照合

`docs/MULTI_GPU.md` はこの設定を restart-only、default off の層分割 opt-in と説明し、`--native`、paged/ring draft K/V の条件と decline log を記載しています。ソースではさらに `draft_kv()` 内の scratch、device、tensor、K/V mode 条件を確認できます。

同資料の測定は 2x RTX 3080 20 GB、UD-Q4_K_XL、`--layer-split 23`、`--batch-mtp`、2 slots、`--prefill auto:16384` の構成で、prompt read の pooled median が 25K tokens で 1,996→2,129 tok/s（+6.7%）、51K で 2,448→2,553（+4.3%）、104K で 2,846→2,940（+3.3%）と報告されています。記載された試行条件での値であり、他環境の性能を示すものではありません。同資料は draft の経路差により drafts が変わり得ること、decode の中央値は約 3%低かったがその差は確定していないことも記載しています。これらは資料中の測定報告であり、本調査では再測定していません。

## 根拠

- `include/strata/program/draft_kv_plan.hpp:16-42` — `atoi` による値判定と MTP / GPU split / embedding 条件。
- `src/program/generate.cpp:6940,8170-8201` — serve の MTP 状態、環境値の static cache、計画、stage 選択、ログ、従来 pass への fallback。
- `src/program/generate.cpp:2348` — `multi_gpu` の定義。
- `src/prefill/prefill.cpp:1346-1399,1422-1426,1448-1516` — `draft_kv()` の追加条件、batch sizing、処理およびエラー。
- `docs/MULTI_GPU.md:103-123` — 文書上の条件、観測ログ、測定条件と結果。
