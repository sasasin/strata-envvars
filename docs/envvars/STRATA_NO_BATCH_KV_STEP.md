# `STRATA_NO_BATCH_KV_STEP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

複数 token の K/V cache append と QSA indexer append を一括実行する経路を抑え、token ごとの append に切り替える診断用スイッチです。CUDA/HIP の verifier、SYCL verifier、および各 backend の MTP drafter が読みます。K/V の形式や生成設定を選ぶ変数ではなく、append の実行単位を変えます。`engine/src/core/verify.cpp:348-349`、`engine/sycl/src/core/verify.cpp:242-243`、`engine/src/core/mtp.cpp:1251-1255`、`engine/sycl/src/core/mtp.cpp:954-959`。

## 値と判定

各実装は値全体を parse せず、未設定でなく、空文字でなく、先頭文字が `0` でない場合に ON とします。verifier の `env_on` helper と MTP 内の判定はこの点で一致します（`engine/src/core/verify.cpp:336-339,349`、`engine/sycl/src/core/verify.cpp:151-154,243`、`engine/src/core/mtp.cpp:1252-1255`、`engine/sycl/src/core/mtp.cpp:956-959`）。

| 条件 | unset | append の一括処理を抑止する値 | 抑止しない値 |
|---|---|---|---|
| CUDA/HIP verifier、SYCL verifier、CUDA/HIP/SYCL MTP drafter | OFF | 空文字以外で先頭が `0` 以外。例: `1`、`2`、`true`、`off`、` 0` | 空文字、または先頭が `0`。例: `0`、`00`、`0anything` |

大文字小文字、空白、数値としての妥当性、文字列全体は検査しません。したがって `false` や `off` も ON で、先頭に空白がある ` 0` も ON です。未設定と空文字はともに OFF です。数値変換・境界値・無効値時の fallback はありません。

## 有効になる条件

- verifier では、複数行の decode window を処理し、QSA layer の K/V または indexer append がある場合に、一括 append の分岐を外します。`STRATA_DEC_BATCH=0` などで `dec_batch` が無効なら、もともと一括経路に入らず、この変数の効果はありません（`engine/src/core/verify.cpp:1488-1496,2105-2125,2350-2411`）。
- 複数 slot の `batch_rec_` 経路では各 slot の状態を個別に扱うため、通常の K/V append は行ごとの経路です。この変数が ON の場合、`STRATA_BATCH_SLOT_RUNS` が有効でも、indexer append の同一 slot 内まとめ処理も抑止されます（`engine/src/core/verify.cpp:1494-1496,2105-2125,2376-2410`）。SYCL verifier も複数 slot 経路では K/V と indexer を行ごとに処理します（`engine/sycl/src/core/verify.cpp:1360-1421`）。
- MTP drafter では複数行 `T` の K/V を append する時に効きます。単一行では一括処理と per-token 処理の差がありません。MTP の full layer は `T == 1` を要求しますが、K/V のみを処理する呼び出しは複数行を受け取ります（`engine/src/core/mtp.cpp:1177-1183,1246-1292`、`engine/sycl/src/core/mtp.cpp:884-892,950-996`）。
- MTP の K/V 状態が Q4 または INT8 の場合、OFF では `kv_append_q4_steps` / `kv_append_q8_steps`、ON では token ごとの `kv_append_q4_step` / `kv_append_q8_step` に分岐します。通常 pool 形式はどちらの値でも token ごとの `kv_append_step` です（`engine/src/core/mtp.cpp:1275-1292`、`engine/sycl/src/core/mtp.cpp:979-996`）。
- verifier で変わるのは QSA の K/V と indexer append のまとめ方です。GDN の状態処理や GR の複数行処理を無効にする変数ではありません（例: `engine/src/core/verify.cpp:2350-2411` の K/V/indexer 分岐と `engine/src/core/verify.cpp:2986` の GR 分岐）。

## 実行時の詳細

verifier 側は namespace scope の `const bool g_no_batch_kv` として初期化されるため、プロセス起動時に一度読み取ります。MTP 側は `record_front` 内の block-scope `static const bool` で、最初に該当処理へ入った時に一度読み、その後の変更は反映されません。CUDA/HIP と SYCL で値の判定は同じです（`engine/src/core/verify.cpp:336-349`、`engine/sycl/src/core/verify.cpp:151-154,242-243`、`engine/src/core/mtp.cpp:1246-1255`、`engine/sycl/src/core/mtp.cpp:950-959`）。

MTP では K projection・V projection、K norm/RoPE、および必要な K/V rotation は T 行をまとめて計算するままで、変数が切り替えるのは cache append です。Q4/INT8 cache の append を T 行一括から各行の append に変えます（`engine/src/core/mtp.cpp:1246-1292`、`engine/sycl/src/core/mtp.cpp:950-996`）。

verifier では ON にすると、decode window 用 K/V cache append の一括 branch と QSA indexer append の一括 branchを使わず、各 token の append に進みます。OFF では `dec_batch` が有効かつ `batch_rec_` でない window で一括 branch を利用できます。slot ごとの行をまとめる経路も、この変数が ON なら一行ずつになります（`engine/src/core/verify.cpp:2105-2125,2350-2411`、`engine/sycl/src/core/verify.cpp:1367-1421`）。

## ログと測定値

この変数の値や分岐を知らせる専用ログは見つかりませんでした。MTP append 処理中に例外が発生した場合は `record_front` の catch が `mtp: ` を先頭につけたエラー文字列を返しますが、変数固有の失敗経路ではありません（`engine/src/core/mtp.cpp:1293-1298`、`engine/sycl/src/core/mtp.cpp:997-1001`）。`docs/DETAILS.md` と `docs/BATCHING.md` にこの変数の説明はなく、`docs/bench-results/2026-10-04-community-4090-32gb-ram-512k/README.md:137-150` の PR #783 比較も PR 全体の測定で、この変数単独の効果を分けていません。そのため測定値は記載していません。

## 根拠

- 候補名のソース参照全件: `engine/src/core/verify.cpp:349,2106,2114,2352,2381,3473,3528`、`engine/sycl/src/core/verify.cpp:243,1369,1409,2251`、`engine/src/core/mtp.cpp:1251-1254`、`engine/sycl/src/core/mtp.cpp:955-958`。コメントにだけ現れる MTP 行を除き、各 backend の verify と MTP の実装が値を読みます。
- 判定 helper: `engine/src/core/verify.cpp:336-339`、`engine/sycl/src/core/verify.cpp:151-154`。
- verifier の QSA K/V・indexer append 分岐: `engine/src/core/verify.cpp:2105-2125,2350-2411,3471-3537`、`engine/sycl/src/core/verify.cpp:1367-1421,2245-2259`。
- MTP drafter の読み取り・append 分岐: `engine/src/core/mtp.cpp:1177-1183,1246-1298`、`engine/sycl/src/core/mtp.cpp:884-892,950-1001`。
