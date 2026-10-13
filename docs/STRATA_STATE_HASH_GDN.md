# `STRATA_STATE_HASH_GDN`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

GDN（gated delta network）の状態を、状態ごとの短いハッシュ列として stderr に出す診断用フックです。Prefill 完了時の `GDN_HASH` 出力はこの変数だけで有効になります。serve の request 完了時に出る `STATE_HASH_GDN` は、別変数 `STRATA_STATE_HASH` が有効な状態ハッシュ処理の中で追加されます。

CUDA と SYCL にそれぞれ実装があります。通常の利用設定や計算結果を選ぶスイッチではなく、診断ログの出力を制御します。

## 値と判定

| 状況 | 動作 |
|---|---|
| 未設定 | この変数に対応する GDN ハッシュログを出さない |
| 何らかの値を設定 | 有効。値の文字列・数値変換は行わない |
| 空文字、`0`、`false` など | 設定済みなので有効 |

いずれの読み取り箇所も `std::getenv("STRATA_STATE_HASH_GDN") != nullptr` を使います。真偽値や数値として parse せず、設定値の内容、大文字小文字、前後の空白は判定に影響しません。

## 有効になる条件

- **Prefill**: Prefill の処理が成功経路の末尾まで到達したとき、変数が設定済みなら GDN 状態を読み取り、`strata prefill: GDN_HASH ...` を stderr に出します。`ss.gdn_alloc` が 0 の場合は状態ごとの反復がなく、列は空です。
- **serve の request 完了時**: `STRATA_STATE_HASH` が設定済みで、request がキャンセルされず、`o.prompt_cache > 0` の場合に限り状態 fingerprint 処理が動きます。その中で本変数も設定済みかつ `ss.gdn_alloc > 0` なら、状態ごとの `STATE_HASH_GDN` を追加出力します。本変数だけでは serve 側の fingerprint 処理全体は有効になりません。
- 対象実装は CUDA と SYCL の各 Prefill / serve 経路です。Windows/Linux などの OS による本変数自体の値判定差は見つかりません。

## 実行時の詳細

Prefill は `ss.gdn_alloc` 個の状態を順に読みます。各状態について `gdn_floats * 4` byte をホストへコピーし、FNV-1a（初期値 `1469598103934665603`、乗数 `1099511628211`）を計算して、下位 16 bit を 4 桁の16進数で出力します。CUDA は `m.cs` を同期してから `cudaMemcpy`、SYCL は `m.cs` を待ってから queue の `memcpy(...).wait()` を行います。出力ラベルは `strata prefill: GDN_HASH ` です。

serve の request 完了時の出力は `strata serve: STATE_HASH_GDN ` です。これは `ConvStateSizes` が示す GDN 領域を `ss.gdn_alloc` で割ったサイズずつハッシュします。CUDA/SYCL とも `hash_dev` が最大 65536 byte のチャンクで状態データを読み、同じ FNV-1a を使い、各状態の下位 16 bit を4桁の16進数で連結します。値の列は状態の割当順で、各値の後ろに空白が付きます。CUDA の `hash_dev` は `cudaMemcpyDefault`、SYCL は in-order queue の memcpy と wait を使用します。

Prefill の読み取り条件は関数実行時に毎回評価され、serve 側の追加出力条件も request の fingerprint 処理中に評価されます。これらの箇所では本変数を static cache していません。一方、serve 側の親となる `STRATA_STATE_HASH` は `static const bool` に保存され、最初の判定後はプロセス内で再評価されません。

この診断では GPU 状態の同期・ホストへのコピー・ハッシュ計算が発生します。コードは診断出力と実装を示すもので、実行時間への影響量は測定していません。関連する `docs/DETAILS.md` に本変数の説明は見当たりませんでした。

## 根拠

- `src/prefill/prefill.cpp:4192-4205`: CUDA Prefill での設定有無判定、同期、状態ごとのコピーと FNV-1a、`GDN_HASH` 出力。
- `sycl/src/prefill/prefill.cpp:4657-4672`: SYCL Prefill の対応実装。
- `src/program/generate.cpp:12221-12223,12261-12272`: CUDA serve 側の親 `STRATA_STATE_HASH` 条件と GDN ごとの追加ハッシュ・出力。
- `sycl/src/program/generate.cpp:11368-11371,11424-11434`: SYCL serve 側の対応実装。
- `src/program/generate.cpp:12237-12249, sycl/src/program/generate.cpp:11386-11412`: serve 側のチャンク単位コピーと FNV-1a 処理。
- `src/program/generate.cpp:1481-1484, sycl/src/program/generate.cpp:1401-1404`: `fnv1a` の実装と乗数。
