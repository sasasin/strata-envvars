# `STRATA_IDX_FP16_CHECK`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA の prompt prefill で、pooled indexer key と現在の query tail (`dead`) を FP16 に丸めた場合に、選択セルが通常の選択とどの程度一致するかを測る診断用フックです。通常の選択結果を差し替える設定ではありません。CUDA/HIP 側の `src/prefill/prefill.cpp` と SYCL 側の `sycl/src/prefill/prefill.cpp` に同じ診断があります。

## 値と判定

値は parse されず、`std::getenv("STRATA_IDX_FP16_CHECK") != nullptr` だけで有効になります。未設定なら無効、設定されていれば空文字・`0`・`false` を含むどの文字列でも有効です。最初に診断箇所へ到達したとき `static const bool` に保存されるため、そのプロセスでは以後の環境変更は反映されません。

| 状態 | 動作 |
|---|---|
| unset | 診断を実行しない |
| 設定あり（空文字を含む） | FP16 丸め後の再選択と比較を実行 |

根拠: `src/prefill/prefill.cpp:2771-2776`, `sycl/src/prefill/prefill.cpp:3061-3066`。

## 有効になる条件

設定が有効でも、QSA indexer の prompt prefill 選択ループを実行する場合に限って動きます。QSA を使わないモデルや、この prefill 経路に入らない処理では診断箇所に到達しません。ソース上では別の CLI 設定や環境変数による追加の有効条件はありません。

## 実行時の詳細

各 prefill chunk の通常選択後、`st.idx_pooled` の全行と `st.idx_dead` を FP16 の round-to-nearest-even で丸め、float に戻した診断用バッファへ書きます。そのバッファで `qsa_block_scores` と `qsa_block_topk` を再実行し、通常の `m.sel_ids` と診断用 `ids16` をホストへコピーして比較します。したがって、FP16 の実ストレージや KV streaming を有効化するものではなく、メモリ確保・追加カーネル・デバイスからホストへの転送と同期を伴う診断です。

通常経路は利用可能な場合に `qsa_block_scores_tc` を使い、診断の再選択は `qsa_block_scores` を使います（通常経路が旧選択指定、または TC 経路を使えない場合も `qsa_block_scores`）。よって出力は実際の通常選択との一致を示しますが、FP16 丸め以外にスコア計算経路の差が影響する場合があります。

各 query について、幅 `w` の二つの ID 配列を二つの index で走査して共通 ID 数 `c` を数え、`c == w` なら同一選択として全 query 数 (`queries`) とともに累積します。また `p0 + t + 1 > m.cap` の query について、共通セル数と選択セル数を別途累積し、セル共有率を出します。QSA の最後の層を処理した chunk ごとに stderr へ次の形式で表示します。

```text
strata prefill: FP16 indexer keys: <same> of <queries> selections identical; where the selection is sparse, <percent>% of cells shared (<queries> queries)
```

カウンターは関数内 static 変数なので、同じプロセス内の後続 chunk / 呼び出しにも累積します。診断バッファは初回実行時に確保します。確保に失敗すると `STRATA_IDX_FP16_CHECK: no room for its buffers` を `err` に設定し、prefill は `false` を返します。CUDA は `cudaMalloc`、SYCL は `sycl::malloc_device` で確保します。

根拠: `src/prefill/prefill.cpp:2740-2749,2771-2816`, `sycl/src/prefill/prefill.cpp:3024-3032,3061-3129`; CUDA の丸めは `src/prefill/kernels.cu:1712-1715,1824-1827`、SYCL は `sycl/src/prefill/kernels.dp.cpp:2066-2078,2237-2255`。

## 文書との照合

`docs/DETAILS.md` を検索した範囲では、この環境変数の診断結果や測定値を説明する記載は見つかりませんでした。したがって、一致率や性能・精度の評価はここでは示しません。コードが出力する比較値は観測値であり、特定のモデルや環境での実測結果ではありません。

## 根拠

- CUDA/HIP prompt prefill の通常選択と診断: `src/prefill/prefill.cpp:2738-2816`
- SYCL prompt prefill の通常選択と診断: `sycl/src/prefill/prefill.cpp:3021-3129`
- FP16 round-to-nearest-even を float へ戻す処理: `src/prefill/kernels.cu:1712-1715`, `sycl/src/prefill/kernels.dp.cpp:2066-2078`
