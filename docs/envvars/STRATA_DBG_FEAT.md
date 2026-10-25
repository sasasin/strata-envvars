# `STRATA_DBG_FEAT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

バッチ prefill の MoE routing 後に、各 MoE layer・chunk の routed expert ID と routing weight をバイナリファイルへ記録します。`STRATA_DBG_FEAT_LAYERS` で選ばれた layer では、router 入力の hidden state も BF16 で記録します。これは研究・診断用フックで、値が未設定ならこの出力処理は動きません。通常の生成・routing を置き換える機能ではありません。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | 他の `STRATA_DBG_ROUTE_OVERRIDE` も未設定なら処理ブロックを実行せず、出力しない。 |
| 設定あり（空文字を含む） | `getenv()` が非 null となり処理ブロックに入る。最初の実行時にその値を `fopen(path, "wb")` へ渡す。空文字では通常ファイルを開けず、失敗は通知されない。 |
| 有効な書き込み先 | 初回にバイナリ書き込みで開き、既存ファイルがあれば切り詰める。MoE layer/chunk ごとにレコードを追記する。 |
| 開けない書き込み先 | `ff == nullptr` のまま dump 部分を飛ばす。再試行やエラー出力はない。 |

値を真偽値や数値として parse しません。パス文字列をそのまま使います。環境変数と `FILE*` は関数内の `static` に保持されるため、最初の MoE chunk で評価・open された後にプロセス環境を変更しても反映されません。`fopen` は一度だけ試みます。根拠: `src/prefill/prefill.cpp:2873-2878`。

## 有効になる条件

- 対象は `src/prefill/prefill.cpp` の batched prefill の layer loop にある MoE 分岐です。router projection と `route(...)` が終わった後、各 MoE layer/chunk で実行されます。decode 専用経路や QSA layer ではこの箇所を通りません（`src/prefill/prefill.cpp:2133-2137,2473-2478,2860-2875`）。
- 設定値があるだけでファイル出力されるわけではありません。出力先を開けた場合に限り、dump 処理がデータを書きます。
- `STRATA_DBG_ROUTE_OVERRIDE` が設定されている場合も同じ処理ブロックに入ります。この変数を未設定にして `STRATA_DBG_FEAT` だけを使う場合、override の読み込みは空の map になります。反対に `STRATA_DBG_FEAT` が未設定で override だけが設定されている場合、このブロックは override 処理のために実行されますが、feature ファイルは開きません。
- `STRATA_DBG_FEAT_LAYERS` は隠れ状態を出す layer を選びます。未設定時の既定は `3,4,15,16,27,28,39,40`。指定文字列はカンマで分割し、各要素を `atoi` で整数化して `0..63` のみ有効にします。選択外の layer も ID と weight は記録します。なお、この companion 変数の読み取りは dump/override ブロックが初めて実行されたときだけです（`src/prefill/prefill.cpp:2878-2885,2913-2921`）。

## 実行時の詳細

各レコードは次の順で書かれます。`T` は現在の prefill chunk の token 数、MoE の top-k `K` はこの実装で 10、router 入力幅 `N` は 2560 です（`src/prefill/prefill.cpp:102,2133-2137,2860-2869,2907-2921`）。

1. 4 個の `int32` header: `{layer, layer 内の chunk 開始位置, T, hidden state を含むか (0/1)}`。
2. `T * K` 個の expert ID を `uint16` に変換した配列。
3. `T * K` 個の routing weight を BF16 bit pattern (`uint16`) に丸めた配列。
4. header の flag が 1 の場合、router 入力 hidden state `m.mixed_bf` を `T * N` 個の BF16 (`uint16`) で記録。

chunk 開始位置は layer ごとに保持する `posl` に、その layer の各 chunk の `T` を加算して求めます。ID は範囲検査なしに `uint16` へ変換され、weight は float の上位 16 bit に丸め処理を加えて BF16 化されます。CUDA stream を同期してから GPU 上の ID、weight（選択 layer では hidden state）を host へコピーし、`fwrite` します。ファイル open、copy、write の失敗をこの箇所でログしたり、prefill のエラーとして返したりする処理はありません。根拠: `src/prefill/prefill.cpp:2886-2887,2904-2921`。

同じブロックの後段では `STRATA_DBG_ROUTE_OVERRIDE` のレコードを照合し、一致した場合には IDs と weights を device にコピーして routing 結果を置き換えます。これは別の環境変数による機能であり、`STRATA_DBG_FEAT` 自体は dump 前に現在の routing 結果を記録します（`src/prefill/prefill.cpp:2888-2903,2923-2927`）。

## 根拠

- `src/prefill/prefill.cpp:2133-2137,2473-2478`: prompt を chunk 単位で処理し、layer loop に入る箇所。
- `src/prefill/prefill.cpp:2860-2878`: MoE 分岐、routing 後の環境変数読み取りと出力ファイル open。
- `src/prefill/prefill.cpp:2878-2885,2886-2921`: hidden-state layer 選択、layer/chunk 位置、dump のデータ形式。
- `src/prefill/prefill.cpp:2888-2903,2923-2927`: 関連する `STRATA_DBG_ROUTE_OVERRIDE` の読み込みと routing 上書き。

`STRATA_DBG_FEAT` を説明する設計資料は `docs/DETAILS.md` および同名参照の検索では見つかりませんでした。上記は調査対象 commit の実装から確認した範囲です。
