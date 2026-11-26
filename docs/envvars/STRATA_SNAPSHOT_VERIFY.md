# `STRATA_SNAPSHOT_VERIFY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

serve 実行中の MTP draft K/V の確認ログを有効にし、復元した会話スナップショットの draft K/V を実際の GPU 側状態と照合します。また、会話キャッシュの K/V 交換最適化を抑止します。MTP 自体を有効にする変数ではありません。CUDA 実装は `engine/src/program/generate.cpp`、SYCL 実装は `engine/sycl/src/program/generate.cpp`、交換最適化のガードは共通コアの `engine/src/core/conversation_state.cpp` にあります。

## 値と判定

いずれも `getenv(...) != nullptr` またはポインタの真偽値だけで判定し、内容は parse しません。未設定ならこの変数によるログ・復元照合・交換抑止はありません。空文字、`0`、`false`、`0anything` を含め、何らかの値が設定されていれば「設定あり」です。大文字小文字、空白、数値の妥当性、境界値は検査されません。判定はコード上で読み取り箇所に到達するたびに行われ、変数値を保持する static cache はありません。

| 実行経路 | unset | 設定あり（例） | 無効になる値 |
|---|---|---|---|
| CUDA / SYCL serve の MTP prefill・スナップショット復元 | この変数による追加ログ・draft 照合なし | 空文字、`0`、`1`、`true` など、値の内容を問わず有効 | 該当なし。設定有無のみ |
| CUDA serve の会話スナップショット交換準備 | 他の条件も満たせば交換準備を試行 | 設定有無を問わず交換準備を拒否 | 該当なし。設定有無のみ |

## 有効になる条件

- `DRAFT_PREFILL` ログには serve 経路で MTP (`use_mtp`) が使われている必要があります。`use_mtp` は `--mtp` の指定が空でないかで決まり、この環境変数だけでは MTP を有効化しません。プロンプト chunk ごとに prefill 後、`stderr` に `strata serve: DRAFT_PREFILL ...` を出します（CUDA: `engine/src/program/generate.cpp:14806-14808`、SYCL: `engine/sycl/src/program/generate.cpp:8633-8635`）。
- 復元照合には、MTP が有効で、serve が `incoming` 会話スナップショットを復元する経路に入る必要があります。値が設定されていても復元がなければ照合ログは出ません（CUDA: `engine/src/program/generate.cpp:19988-20022`、SYCL: `engine/sycl/src/program/generate.cpp:10971-11008`）。
- 交換抑止は CUDA serve の `conversation_snapshot_swap_prepare` 呼び出しで働きます。同関数はこの変数が設定されていると `false` を返し、serve 側の会話キャッシュ交換処理は通常の交換準備を進めません。呼び出し側の交換条件には RAM-tier の incoming 会話、非 batch などの追加条件があります（`engine/src/core/conversation_state.cpp:779-796`、`engine/src/program/generate.cpp:19755-19775`）。SYCL 側でこの交換準備関数を呼ぶ箇所は見つかりませんでした。
- CUDA と SYCL の serve に同等の prefill ログおよび復元照合箇所があります。ここで確認できる環境変数の読み取りには OS 別・build macro 別の値規則はありません。

## 実行時の詳細

`DRAFT_PREFILL` はプロンプト chunk の処理後に出力し、`path` は draft K/V の処理が `batched` か `token` か、`mode` は `mtp.kv_state().kv_mode`、`cells` は当該 chunk の token 数です（`engine/src/program/generate.cpp:14798-14808`、SYCL: `engine/sycl/src/program/generate.cpp:8623-8635`）。

スナップショット復元時は、各 stage の restore と同期を終えた後、保存された draft K/V (`draft_kv`) と MTP の resident state を `conversation_kv_verify` に渡します。比較に失敗すると `stdout` に `ERR verifying restored draft KV: <理由>` を出して serve 処理から `1` で戻ります。成功時は `stderr` に `strata serve: SNAPSHOT_VERIFY draft=%016llx cells=%lld mode=%d source=%s resident=%lld` の形式で fingerprint、cell 数、mode、固定ラベル `ram`、resident slot から算出した長さを出します（CUDA: `engine/src/program/generate.cpp:20009-20022`、SYCL: `engine/sycl/src/program/generate.cpp:10995-11008`）。

照合関数は保存イメージの K/V・scale・pooled bytes を resident 側から読み出し、一致しない場合は `conversation snapshot: restored K/V bytes differ` をエラーにします。`kv_mode == 2` の場合はさらに resident ring の末尾ページも比較します。一致時は保存された K/V bytes から fingerprint を計算します（CUDA: `engine/src/core/conversation_snapshot.cpp:1017-1058`、SYCL: `engine/sycl/src/core/conversation_snapshot.cpp:293-334`）。この経路は復元データを比較する診断であり、K/V や生成 token を書き換える処理ではありません。

環境変数は各分岐で実行時に読み取られ、値を起動時に保存する処理はありません。実行中にプロセス自身が環境を書き換えれば次の読み取りで再評価されますが、この名前を Strata が書き換える箇所はありません。子プロセスへの転送もありません。CUDA で設定ありの場合は snapshot swap の準備を断り、呼び出し側では snapshot restore の通常経路に進みます。ほかの設定で上書きされる規則はありません。

## ログと測定値

- MTP prefill chunk ごとの `stderr` ログ: `strata serve: DRAFT_PREFILL path=%s mode=%d cells=%lld`。
- draft K/V の復元照合成功時の `stderr` ログと失敗時の `stdout` エラーは、上記「実行時の詳細」のとおりです。照合失敗は serve を終了させます。
- `docs/DETAILS.md` にこの変数名の説明や測定値は見つかりませんでした。ソースに基づく機能説明のみとし、性能・正確性の測定値は記載しません。

## 根拠

- CUDA/SYCL の値判定と prefill ログ: `engine/src/program/generate.cpp:14806-14808`、`engine/sycl/src/program/generate.cpp:8633-8635`。
- CUDA/SYCL の復元後照合、エラー終了、成功ログ: `engine/src/program/generate.cpp:19988-20022`、`engine/sycl/src/program/generate.cpp:10971-11008`。
- 照合内容と mismatch 理由: CUDA `engine/src/core/conversation_snapshot.cpp:1017-1058`、SYCL `engine/sycl/src/core/conversation_snapshot.cpp:293-334`。
- CUDA snapshot swap 準備の拒否条件と呼び出し側条件: `engine/src/core/conversation_state.cpp:779-796`、`engine/src/program/generate.cpp:19755-19775`。
- MTP 有効条件: `engine/src/program/generate.cpp:12302-12314`、`engine/sycl/src/program/generate.cpp:7168-7180`。
