# `STRATA_STATE_HASH`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` の会話状態を診断用に指紋化し、リクエストごとに `STATE_HASH` 行として stderr へ出します。状態を変更する設定ではなく、prompt-cache の実行前後などで状態が一致するかを比較するための出力です。CUDA 実装と SYCL 実装の両方にあります。

## 値と判定

値の内容は parse せず、`std::getenv("STRATA_STATE_HASH") != nullptr` で設定有無だけを見ます。未設定なら無効、空文字を含め何らかの値が設定されていれば有効です。`0`、`false`、大小文字、空白などによる無効化はありません。

判定値は関数内の `static const bool` に保存されます。そのコード行に初めて到達した時点で一度だけ評価され、以後同一プロセスで環境を書き換えても再評価されません。

## 有効になる条件

- `--serve` のリクエスト処理を通ること。
- `o.prompt_cache > 0` であること。`--prompt-cache 0` では出力しません。
- リクエストがキャンセルされていないこと。

完了した非キャンセルリクエストごとに出力します。ソースコメントは checkpoint が 0 の場合も対象としていますが、実際の条件は `o.prompt_cache > 0` です。値を指定しても通常の非 serve 経路ではこのコードを通らず、出力されません。

## 実行時の詳細

ハッシュ計算前にデバイス処理を同期します。CUDA では `cudaDeviceSynchronize()`、SYCL では現在の device queue の `queues_wait_and_throw()` を使います。固定長 64 KiB の作業バッファへ状態データを読み込み、FNV-1a（初期値 `1469598103934665603`、乗数 `1099511628211`）で集約します。

stderr の行は `strata serve: STATE_HASH L=... gdn=... ple=... tail=... pooled=... kv=... mtp=... stale=... dead=... pooled_full=... ple_prev=...` の形式です。`L` は現在の live session の token 数です。各フィールドは次の状態を指します。

- `gdn`: セッションの GDN/畳み込み状態全体。
- `ple`: PLE 履歴全体。
- `tail` と `dead`: 各 QSA 状態の indexer tail と spare/dead key。
- `pooled`: `L / idx_block` 個の完了済み pooled indexer 行。
- `pooled_full`: `pooled` に次の block 完了時に上書きされる spare 行も含めた範囲。
- `kv`: 各 QSA 状態の KV データのうち token cell `[0, L)`。
- `stale`: 最後の KV page 内で `[L, page-rounded-up(L))` にある未使用 cell。
- `mtp`: MTP が有効な場合の draft KV データ（長さは `min(L, max_cells)`）。無効なら初期値のハッシュが出ます。
- `ple_prev`: `ss.ple_prev[0]` と `[1]` の整数値で、ハッシュではありません。

KV のハッシュ対象配列は状態の KV 形式（Q4、hybrid、int8、通常）と host/device mode に応じて選ばれます。QSA 状態が複数ある場合は session が所有する状態を順に同じハッシュへ追加します。`STRATA_STATE_HASH_GDN` も設定されていて GDN 状態が割り当て済みなら、別途 GDN 各層の下位16 bit のハッシュ列を `strata serve: STATE_HASH_GDN ...` として stderr に出します。この追加出力は別変数によるものです。

同期に失敗すると stdout に `ERR synchronizing state fingerprint` を出してプロセスを終了し、データ読取りに失敗すると `ERR reading state fingerprint` を出して終了します。SYCL のハッシュ読取り例外では例外情報とファイル・行を stderr に出した後 `exit(1)` します。

## 根拠

- `src/program/generate.cpp:12221-12229` は設定有無の判定、適用条件、CUDA 同期、live 長を示します。
- `src/program/generate.cpp:1481-1485` は FNV-1a の初期値と更新式、`src/program/generate.cpp:12235-12331` は対象領域と出力形式です。
- `src/program/generate.cpp:12263-12272` は関連する `STRATA_STATE_HASH_GDN` の追加出力、`src/program/generate.cpp:12322-12331` は失敗処理と `STATE_HASH` 行です。
- `sycl/src/program/generate.cpp:11368-11383,11424-11494` は SYCL 側の対応箇所です。
- `docs/DETAILS.md` には `STRATA_STATE_HASH` の説明を確認できませんでした。
