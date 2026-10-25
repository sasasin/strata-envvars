# `STRATA_QSA_SLOTS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

検証器が複数 slot の行を一つの batch window で処理するとき、QSA の block scores、top-k、attention を slot ごとに呼ぶ代わりに、複数行をまとめた CUDA kernel launch にします。各行は自分の slot の indexer key と K/V pool を読み、自分の出力領域へ書きます。通常の単一 slot の窓や、batch 窓以外の QSA 処理には適用されません。

## 値と判定

環境変数を `env_on()` で判定します。unset と空文字は無効、値の先頭文字が `0` の場合も無効です。それ以外の非空文字列は有効です。文字列全体の parse、大文字小文字、数値としての妥当性は検査しません。したがって `1`, `true`, `false`, `2` は有効ですが、`0`, `0anything` は無効です。

判定結果は `verify.cpp` のグローバル `const bool` 初期化時に一度だけ読み取られます。実行中の環境変更はこの値に反映されません。

## 有効になる条件

- QSA を含む検証器の batch window であること（内部の `batch_rec_` が true）。
- その window の行が streamed KV mode でないこと。どれかの行が streamed なら、slot ごとに block scores、top-k、K/V resolve、attention を行う分岐になります。
- `STRATA_BATCH_ATTN_ROWS` による行単位の一括経路が先に選ばれないこと。その経路は `STRATA_QSA_SLOTS` の値に関係なく選ばれます。

slot まとめ起動では最大8行ずつ処理します。block-scores launcher が現在の条件で multi kernel を使えない場合は各行の launcher に戻ります。attention launcher も、KV format の混在や対象外 geometry / architecture などで一括起動できない場合は各行の attention に戻ります。コード上で挙げられている条件には、pre-sm_75 attention variant、gfx906 query-swizzle variant などがあります。これらの fallback でも batch window 自体は続行します。

## 実行時の詳細

`Verifier::record_window()` の QSA layer 処理で、batch window かつ本変数が有効で、streamed KV がない場合に slot ごとの pooled/dead indexer pointers と K/V pools を配列にまとめます。最大8行のグループごとに `qsa_block_scores_slots()`、`qsa_block_topk()`、`qsa_decode_attn_slots()` を呼び出します。scores と attention の launcher が `false` を返す場合、その段階のみ従来の一行ずつの launcher に切り替えます。

`docs/BATCHING.md` はこのスイッチを batch window の QSA 処理を行単位で一括 launch する opt-in と説明しています。実装コメントと kernel API の説明では、各行を自身の indexer/K/V で計算し、個別呼び出しと同じ算術を行う設計です。この調査では性能差や全モデルでの出力同一性を独立に測定していません。

## 根拠

- `src/core/verify.cpp:220-223,237-241`: 空文字を含む値判定と、グローバル初期化される `g_qsa_slots`。
- `src/core/verify.cpp:1731-1733,1742-1763`: streamed KV の検出、`STRATA_BATCH_ATTN_ROWS` 経路の優先、slot 一括経路の条件。
- `src/core/verify.cpp:1763-1795`: 最大8行単位の呼び出しと launcher が対応しない場合の per-row fallback。
- `include/strata/kernels/qsa_select.hpp:42-47`: block scores slots API と multi kernel 不使用時の fallback 契約。
- `include/strata/kernels/qsa_decode_attn.hpp:53-66`, `src/kernels/cuda/qsa_decode_attn.cu:1072-1098`: 8 query 上限、KV format が揃わない場合や対象外 kernel variant の拒否。
- `docs/BATCHING.md:110-123`: batch 窓スイッチの文書上の説明。
