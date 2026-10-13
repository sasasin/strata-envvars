# `STRATA_NO_BATCH_KV_STEP`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Verifier と MTP drafter が、複数 token 分の K/V cache および QSA indexer の追記をまとめて行う経路を止め、token ごとの追記に戻します。Verifier では `STRATA_DEC_BATCH` による他の計算のバッチ化までは無効にしません。`src/core/verify.cpp` と `sycl/src/core/verify.cpp` の注釈は、この切替を #783 PR-d の per-token K/V と indexer append と説明しています。

## 値と判定

この変数は数値として parse せず、文字列の設定有無、空文字、先頭文字だけを調べます。未設定が既定です。

| 値 | 判定 |
|---|---|
| 未設定 | 無効。バッチ追記を許可する |
| 空文字 | 無効。`env_on` が空文字を除外する |
| 先頭文字が `0` | 無効。例: `0`, `0abc` |
| 空でなく先頭文字が `0` 以外 | 有効。例: `1`, `2`, `true`, `false`, ` 0` |

大文字小文字や末尾文字列は検査しません。`false` も有効であり、`atoi` の 0/非 0 判定ではありません。CUDA/HIP の Verifier では `env_on()` が、SYCL の Verifier にも同じ判定が実装されています。MTP は独立した同等の判定を使います（`src/core/verify.cpp:172-182`, `sycl/src/core/verify.cpp:92-103,151-152`, `src/core/mtp.cpp:735-739`, `sycl/src/core/mtp.cpp:860-864`）。

## 有効になる条件

- Verifier の K/V と indexer の窓単位追記は、`dec_batch` が有効で、`batch_rec_` ではないときだけ通常のまとめ追記を使います。`STRATA_NO_BATCH_KV_STEP` を有効にすると、その条件でも token ごとの追記に切り替わります。`dec_batch` が無効、または `batch_rec_` のときは元から token / row ごとの経路です。複数 row の batch-rec は row ごとに異なる state を扱うため、環境変数の値にかかわらず row ごとに追記します（`src/core/verify.cpp:1263-1322`, `sycl/src/core/verify.cpp:1121-1175`）。
- Verifier で無効にするのは K/V cache と indexer の追記単位です。たとえば `qb` による投影・norm/RoPE の複数 row 処理は別の条件で決まり、この変数だけでは無効になりません（`src/core/verify.cpp:1215-1248,1263-1322`）。
- MTP drafter では、`record_front()` の複数 row の K/V cache 追記に使います。Q4 または INT8 cache なら、無効時に `kv_append_q4_steps` / `kv_append_q8_steps` を呼び、有効時には token ごとの `kv_append_q4_step` / `kv_append_q8_step` に進みます。その他の cache 形式はどちらの設定でも既に token ごとの `kv_append_step` です（`src/core/mtp.cpp:677,730-775`, `sycl/src/core/mtp.cpp:801,855-901`）。
- MTP のこの分岐は、MTP drafter が実行されて `record_front()` に到達した場合に限り関係します。この cache append 経路を通らない処理には影響しません。

## 実行時の詳細

CUDA/HIP と SYCL の Verifier では、`g_no_batch_kv` がファイルスコープの `const bool` として初期化されます。そのため設定は該当翻訳単位の静的初期化時に読み取られ、同じプロセスで後から環境を書き換えても再評価されません。MTP 側の `no_batch_kv` は `record_front()` 内の関数ローカル `static` で、最初にこの関数へ到達した時に読み取り、その後キャッシュされます。設定値を CLI や別の環境変数で上書きする処理はこれらの箇所にはありません。

バッチ追記が選ばれると、Verifier は K/V pool ごとに `kv_append_*_steps`、indexer に `native_qsa_indexer_append_steps` を呼びます。個別追記では各 row の step とデータを使って `kv_append_*_step` および `native_qsa_indexer_append` をループします。commit 時の indexer tail 更新も、無効時は step 追記、有効時は各 token の追記です（`src/core/verify.cpp:1265-1322,2008-2021`, `sycl/src/core/verify.cpp:1123-1175,1875-1887`）。

環境変数に対する専用ログやエラー出力は確認できませんでした。`docs/DETAILS.md` にこの変数を直接説明する記述は見当たらず、動作の根拠は上記ソースです。

## 根拠

- 値判定と Verifier のキャッシュ: `src/core/verify.cpp:172-182`, `sycl/src/core/verify.cpp:92-103,151-152`
- Verifier の K/V と indexer append: `src/core/verify.cpp:1263-1322,2008-2021`, `sycl/src/core/verify.cpp:1121-1175,1875-1887`
- MTP の判定と K/V append: `src/core/mtp.cpp:677,730-775`, `sycl/src/core/mtp.cpp:801,855-901`
- バッチ計算の別条件: `src/core/verify.cpp:845,1215-1248`
