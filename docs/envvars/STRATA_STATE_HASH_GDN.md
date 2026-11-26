# `STRATA_STATE_HASH_GDN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GDN のセッション状態を層ごとにハッシュし、診断用の行を stderr に出す環境変数です。生成状態や token の選択を変更する設定ではありません。chunk-major prefill の完了時には `strata prefill: GDN_HASH ...` を出し、serve の状態 fingerprint が有効な場合には `strata serve: STATE_HASH_GDN ...` を追加します。実装は通常の GPU prefill と SYCL prefill、および各 backend の serve にあります（`engine/src/prefill/prefill.cpp:8046-8059`、`engine/sycl/src/prefill/prefill.cpp:5773-5789`、`engine/src/program/generate.cpp:23432-23478`、`engine/sycl/src/program/generate.cpp:12983-13045`）。

prefill 側では各 GDN 状態のバイト列をホストへコピーしてハッシュするため、設定時は同期と追加の読み戻しが発生します。serve 側も通常の全体 fingerprint に加えて GDN ごとのハッシュを計算します。これは状態を観測する診断処理であり、全体 fingerprint の有効化やセッション保存をこの変数単独で行うものではありません（同ファイルの範囲）。

## 値と判定

値の内容は parse されず、`std::getenv(...) != nullptr` のみで判定されます。unset なら無効、空文字を含む何らかの値が設定されていれば有効です。`0`、`1`、`false`、`0anything`、大小文字、空白、数値としての妥当性に違いはありません（各読み取り箇所は下記「根拠」参照）。

| 経路 | unset | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA/HIP 系 chunk-major prefill、SYCL chunk-major prefill | GDN_HASH 行を出さない | 空文字、`0`、`1`、`false`、その他すべて | なし（環境変数が存在すれば有効） |
| CUDA/HIP 系 serve、SYCL serve | `STATE_HASH_GDN` 行を出さない | 空文字、`0`、`1`、`false`、その他すべて。ただし `STRATA_STATE_HASH` による全体 fingerprint の条件を満たす必要がある | なし（上記の親条件を満たした後は、環境変数が存在すれば有効） |

## 有効になる条件

- prefill の `GDN_HASH` は `Prefill::run_impl` の chunk-major 経路の末尾にあります。処理がエラーで早期 return した場合は到達しません。CUDA/HIP 系の `Prefill::run` が `STRATA_GPU_METAL` の Metal prompt 経路を選ぶ場合は `run_impl` を通らず、layer-major prefill が選ばれて早期 return する場合もこの GDN_HASH 箇所を通りません（`engine/src/prefill/prefill.cpp:9629-9650, 9677-9705`）。SYCL prefill は `run_impl` の末尾に同じ診断処理があります（`engine/sycl/src/prefill/prefill.cpp:2693-2701, 5773-5790, 5959-5972`）。
- serve の `STATE_HASH_GDN` は `STRATA_STATE_HASH` が設定済みで、リクエストがキャンセルされず、`o.prompt_cache > 0` の場合だけ実行されます。親の `STRATA_STATE_HASH` 判定は関数内 `static` に一度保存されます。この対象変数自体は GDN 行の直前に毎回 `getenv` で検査されます（`engine/src/program/generate.cpp:23432-23433, 23470-23478`、`engine/sycl/src/program/generate.cpp:12983-12984, 13037-13045`）。
- serve ではさらに `ss.gdn_alloc > 0` が必要です。GDN 状態が割り当てられていない場合、対象変数が設定されていても GDN 別の行は出ません（上記 serve の GDN 分岐）。
- CLI 引数、設定ファイル、別変数によるこの変数自体の上書きは見つかりません。`STRATA_STATE_HASH` は serve 側で全体 fingerprint を実行するための別の条件であり、prefill の `GDN_HASH` には要求されません。Strata の設計資料も全体 fingerprint を `STRATA_STATE_HASH` として説明しています（`docs/SPLIT_SERVE.md:123-126`）。

## 実行時の詳細

- 値は文字列として保持せず、読み取りのたびに設定有無を確認します。prefill では一回の `run_impl` が末尾まで成功したときに検査し、GDN 状態の各行を順にハッシュします。CUDA/HIP 系は stream を同期して状態を host buffer にコピーし、SYCL は queue を待ってから状態をコピーします（`engine/src/prefill/prefill.cpp:8046-8059`、`engine/sycl/src/prefill/prefill.cpp:5773-5789`）。
- prefill は各 GDN 状態のバイト列に初期値 `1469598103934665603` の FNV-1a を適用し、下位 16 bit を `%04llx ` 形式で連結して `GDN_HASH` として出します。`ss.gdn_alloc == 0` でも設定有無の分岐に入り、空の値で行を出します（CUDA/HIP 系は `engine/src/prefill/prefill.cpp:8046-8059`、SYCL は `engine/sycl/src/prefill/prefill.cpp:5773-5789`）。
- serve の GDN 別ハッシュは各 GDN 状態の範囲を別々にハッシュし、同じく下位 16 bit の列を出します。この処理は全体 fingerprint の計算ブロック内にあり、この変数を unset にしても全体 fingerprint の他の項目は変わりません（`engine/src/program/generate.cpp:23432-23478, 23529-23538`、`engine/sycl/src/program/generate.cpp:12983-13045, 13096-13105`）。
- この名前の判定結果を Strata 内で static cache する箇所はありません。対して serve の親 `STRATA_STATE_HASH` は初回評価後に cache されます。対象変数をプロセス稼働中に Strata のコードが変更する処理は見つからず、CLI 優先順位や子プロセスへの転送もありません。

## ログと測定値

設定時の prefill 出力は `strata prefill: GDN_HASH %s\n`、serve 出力は `strata serve: STATE_HASH_GDN %s\n` です。unset 時にはこれらの行を出しません。測定値はありません。

prefill の CUDA/HIP 系コードでは同期・コピーの戻り値をこの箇所で検査せず、追加ハッシュ専用のエラー行もありません（`engine/src/prefill/prefill.cpp:8046-8059`）。SYCL prefill でコピー待ちが例外を投げた場合は、周囲の catch が例外内容と `Exception caught at file:..., line:...` を stderr に出して `exit(1)` します（`engine/sycl/src/prefill/prefill.cpp:5773-5795`）。serve の全体 fingerprint 中にコピーが失敗すると、CUDA 系は `ERR reading state fingerprint` を stdout に出して `return 1` し、SYCL 系のコピー例外は例外内容を stderr に出して `exit(1)` します（`engine/src/program/generate.cpp:23444-23455, 23529-23531`、`engine/sycl/src/program/generate.cpp:12997-13022, 13096-13099`）。

## 根拠

- `engine/src/prefill/prefill.cpp:8046-8059` — 環境変数の設定有無、同期、GDN 状態のコピーとハッシュ、stderr 行。
- `engine/sycl/src/prefill/prefill.cpp:5773-5795` — SYCL 側の同じ処理と例外経路。
- `engine/src/prefill/prefill.cpp:9629-9650, 9677-9705` — Metal prompt 経路と layer-major 経路が chunk-major `run_impl` を通らない条件。
- `engine/src/program/generate.cpp:23432-23478, 23529-23538` — serve 側の親条件、GDN 別ハッシュ、および fingerprint 失敗の扱い。
- `engine/sycl/src/program/generate.cpp:12983-13045, 13096-13105` — SYCL serve 側の親条件、GDN 別ハッシュ、例外・失敗経路。
- `docs/SPLIT_SERVE.md:123-126` — 設計資料上の全体状態 fingerprint の説明。実行条件の根拠は上記ソース。
