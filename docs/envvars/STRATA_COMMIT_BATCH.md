# `STRATA_COMMIT_BATCH`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

CUDA/HIP verifier が speculative verify window 後に実行する commit graph で、GDN 層と QSA 層の commit 処理を複数層まとめた GPU kernel に切り替えます。GDN では convolution history と state の更新を層ごとに発行する代わりに、複数層をまとめた処理を試みます。QSA では複数層の indexer tail 復元と append をまとめます。対象処理が使えない場合は、該当部分だけ従来の層ごとの処理に戻ります。

## 値と判定

CUDA/HIP 側では文字列全体を parse せず、環境変数の有無と先頭文字だけを見ます。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（既定値） |
| 空文字 | 有効（設定文字列の先頭は `\0` で、`'0'` ではない） |
| 先頭文字が `0` | 無効。例: `0`, `0abc` |
| それ以外 | 有効。例: `1`, `true`, `false`, ` 0` |

大文字小文字、空白、後続文字、数値としての妥当性は検査されません。Metal 用のコードでは値にかかわらず `false` 固定です。

## 有効になる条件

- CUDA/HIP verifier の標準 commit graph 経路で使われる必要があります。Metal は別 engine に処理を渡し、この環境変数を読みません。
- GDN 層がないモデルでは GDN のまとめ処理はありません。QSA 層がないモデルでは QSA のまとめ処理はありません。
- GDN のまとめ kernel は、`STRATA_GDN_SPLIT=1`、`STRATA_GDN_COMMIT_SPLIT=0`、`STRATA_DBG_GDN=1` のいずれかが有効な場合、または kernel の引数制約を満たさない場合に失敗扱いとなり、従来の層ごとの処理になります（`src/kernels/cuda/verify_kernels.cu:1019-1031`）。これらは helper 内で別途評価されます。
- QSA のまとめ処理は `g_no_batch_kv` が偽で、QSA 層数が `QsaIndexerLayers::kMax` 以下、各層の `max_cells` が同一で、必要な `indexer.k_norm.weight` がある場合に使われます。上限・容量が合わない場合は層ごとの処理に戻ります。必要な weight がない場合は commit graph の capture 自体が失敗します（`src/core/verify.cpp:2061-2085,2088-2119`）。

## 実行時の詳細

`Verifier::capture_commit()` 内の関数 static が最初に初期化されるときに環境変数を読み、その後は値をキャッシュします。通常の window 実行は `capture()` とともに commit graph を capture し（`src/core/verify.cpp:2251`）、pipelined 用の `capture_all()` も commit graph を capture します（同:3374）。したがって、初回 capture 後にプロセス環境を変更しても、同じプロセス内では再判定されません。

変数が有効なら、GDN 層の `ssm_norm.weight` を確認して `gdn_commit_layers()` を試します。成功すれば各 GDN 層の convolution history と state をまとめて更新し、失敗すれば後続の層ループが `gdn_conv_commit()` と `gdn_step_norm_multi()` を各層で呼びます（`src/core/verify.cpp:2043-2059,2088-2105`、`src/kernels/cuda/verify_kernels.cu:1019-1039`）。QSA 層は条件を満たせばまとめた append を発行し、そうでなければ tail を復元して各層で append します（`src/core/verify.cpp:2061-2085,2107-2119`）。

この環境変数専用の有効・無効ログはありません。capture や graph launch が失敗した場合は、通常の verifier error が返されます。実装コメントはまとめ処理が従来と同じ演算（bitwise）で graph node を減らす設計と説明していますが、この調査では性能測定を行っていません（`src/core/verify.cpp:2035-2037`）。`docs/DETAILS.md` を含む docs に、この変数の追加説明は見つかりませんでした。

## 根拠

- 読み取り、既定値、Metal 固定値、GDN/QSA 分岐: `src/core/verify.cpp:2015-2044`
- GDN 層の重み確認とまとめ処理: `src/core/verify.cpp:2045-2059`
- QSA のまとめ条件と層ごとの fallback: `src/core/verify.cpp:2061-2119`
- verifier の capture 呼び出し: `src/core/verify.cpp:2251,3367-3374`
- GDN まとめ kernel の追加条件と起動: `src/kernels/cuda/verify_kernels.cu:1019-1039`
- SYCL の別実装には `STRATA_COMMIT_BATCH` の直接参照がなく、CUDA/HIP のこの分岐を適用できる根拠はありません（`sycl/src/core/verify.cpp` 全体検索）。
