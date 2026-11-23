# `HY4S_SYNCALL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の SYCL runner にある `PS` 区間の前後で、SYCL queue を同期する診断用スイッチです。設定されていると `PS` のコンストラクターとデストラクターで `wait()` を呼び、`Q().wait_and_throw()` によりその時点までの queue 処理を待ちます。演算内容やモデル設定を直接切り替える分岐ではなく、非同期処理の完了位置を区切ります（`engine/src/hy4flash/sycl/sy_graph.h:428-447`、`engine/src/hy4flash/sycl/sy_common.h:154-179`）。

## 値と判定

`sync_all_env()` は `std::getenv("HY4S_SYNCALL") != nullptr` のみで判定します。環境変数が未設定なら無効、設定されていれば値の内容を問わず有効です。したがって `1`、`0`、`true`、`false`、空文字、`0anything` はすべて有効で、文字列比較・数値変換・大文字小文字・空白の検査や値域の境界はありません（`engine/src/hy4flash/sycl/sy_graph.h:428-431`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Hy4-Flash SYCL runner の `PS` 区間 | 同期しない | 空文字を含む任意の値 | なし（値は判定に使わない） |

## 有効になる条件

- 対象は `engine/src/hy4flash/sycl/` の Hy4-Flash SYCL runner です。CUDA/HIP や他の Strata runner でこの名前を読む箇所は、調査対象 commit の全参照検索では見つかりません（同 `sy_graph.h:428-429`）。
- 実行経路が `PS` オブジェクトを通る必要があります。たとえば eager の `forward_chunk()` は層処理に進み、`attention_layer_core()` や `lin()` 内で `PS` 区間を作ります（`engine/src/hy4flash/sycl/sy_graph.h:476-479`、`960-965`、`1382-1422`）。
- SYCL command graph が使われる経路では、graph 内の処理が `PS` 区間を通らず、この変数による区間同期も入りません。`HY4S_SYNCALL` 自体は graph を無効化しません。graph 対応ビルドかつ対応 device/runtime で、`HY4S_GRAPH` が未設定または先頭文字が `0` 以外なら `graph_enabled` になり得ます。さらに `forward_chunk()` の graph 経路は `T <= 8` などの条件を要求し、`prof2`、dump、tap、hash、vision 等の状態では使いません（`engine/src/hy4flash/sycl/sy_common.h:9-14`、`engine/src/hy4flash/sycl/sy_graph.h:621-627`、`1382-1392`）。DFly2 の graph 経路も `graph_enabled` かつ `!prof2 && !dump && !tap` のときに選びます（`engine/src/hy4flash/sycl/sy_dfly2.h:703-718`、`928-940`）。
- CLI の `--prof2` は区間タイミングを有効にし、`PS` に marker event を記録しますが、`HY4S_SYNCALL` の有無判定とは独立しています。`prof2` が有効なときは上記 graph 経路が抑制されるため、`PS` の同期箇所を通る eager 経路になります（`engine/src/hy4flash/sycl/sy_main.cpp:99-100`、`177-178`、`283-292`、`engine/src/hy4flash/sycl/sy_graph.h:432-447`）。
- `--serve` でも同じ `Runner::forward_chunk()` / `head()` を通ります。serve 用 `Runner` は `prof2` を設定せず既定値のままで、同期の有無は `PS` を通るか（たとえば graph 経路が使われるか）で決まります（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`、`engine/src/hy4flash/sycl/sy_serve.h:258-268`、`432-442`、`509-515`）。

## 実行時の詳細

値はプロセス起動時ではなく、最初に `sync_all_env()` が呼ばれたときに読み取られ、関数内 `static const bool` に保存されます。通常は最初の `PS` 区間の構築時です。その後プロセス内で環境値を変更しても再読込されません。各 `PS` の構築時に有効なら処理前に `wait()` し、破棄時にも `wait()` します。`prof2` が無効でもこの待ち分岐は実行されますが、marker event と集計記録は `on` が真（`prof2` 有効）のときだけ行われます（`engine/src/hy4flash/sycl/sy_graph.h:428-447`）。

`PS` 以外の queue 操作を一律に囲む設定ではありません。graph replay の経路など `PS` を通らない処理にはこの同期は追加されません。また、読み取った値を子プロセスに渡したり上書きしたりするコードは見つかりません（同 `sy_graph.h:428-447`）。

## ログと測定値

この変数専用のログ、警告、値の出力はありません。同期処理は `Q().wait_and_throw()` を呼ぶため、queue の非同期エラーがあればその呼び出しから例外が伝播し得ますが、`PS` 内にこの変数固有の例外捕捉・エラーメッセージはありません（`engine/src/hy4flash/sycl/sy_common.h:179`、`engine/src/hy4flash/sycl/sy_graph.h:436-447`）。Strata の資料にこの変数の測定値は確認できませんでした。

## 根拠

- 値の読み取りと cache、`PS` の前後同期: `engine/src/hy4flash/sycl/sy_graph.h:428-447`
- queue の定義と `wait_and_throw()`: `engine/src/hy4flash/sycl/sy_common.h:154-179`
- eager/graph 経路の選択条件: `engine/src/hy4flash/sycl/sy_graph.h:621-627`、`1382-1392`
- `--prof2` の読み取りと runner への設定: `engine/src/hy4flash/sycl/sy_main.cpp:99-100`、`177-178`、`283-292`
- DFly2 graph 経路: `engine/src/hy4flash/sycl/sy_dfly2.h:703-718`、`928-940`
