# `DS4_FLOW_PUMP_WAIT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DS4 の expert flow 経路で、GPU stream がまだ実行中の間にも host 側の `flow_pump()` を呼び、次の expert の読み込みと転送を進めるかを制御します。既定は有効です。`0` を指定するとこの待機中の先行 pump を止め、GPU stream の完了後に bounds を受け取る従来の待ち方になります。この変数は flow 経路そのものや `flow_pump()` の全呼び出しを無効にはしません。

## 値と判定

値は `std::atoi()` で整数変換し、結果が 0 以外なら有効とします。文字列全体の検証はありません。

| 環境変数の状態・値 | 判定 |
|---|---|
| unset | 有効（既定） |
| 空文字 | 無効（`atoi("") == 0`） |
| 数値変換結果が 0 | 無効。例: `0`, `0tail`, `false`, `no` |
| 数値変換結果が 0 以外 | 有効。例: `1`, `2`, `-1`, `1tail`, ` 1` |

`atoi()` は先頭空白と符号を許し、数値として読める接頭部分を変換します。数値の後ろの文字列は無視され、先頭が数値として読めない値は 0 になります。整数型の範囲を超える値を `atoi()` に渡した場合の結果は規格上定義されません。

判定結果は関数内の `static const bool` に保存されます。最初にこのコードへ到達した時点で unset なら既定の `true`、設定済みなら `atoi()` の結果で初期化され、以後の環境変更は反映されません。

## 有効になる条件

値が有効でも、DS4 実行時に対象 device の `Chunk` が `c.flow == true` でなければ、この変数による待機ループは動きません。初期化コードでは、flow は `DS4_FLOW` が有効で、device 上の対象層が MXFP4 形式である場合に設定されます。tensor-parallel group では `DS4_FLOW_TP` が非ゼロであることと、down matrix の block alignment 条件も必要です。ring のない chunk は flow 初期化の対象になりません。

この変数は flow 経路の非 MTP expert layer 処理で参照されます。CLI、設定ファイル、別変数からこの判定結果を上書きする処理は確認できません。GPU/CUDA API の内部動作は対象外です。

## 実行時の詳細

expert routing と shared-expert GPU 計算を enqueue した後、コードは `cudaStreamQuery(s)` が `cudaErrorNotReady` を返す間、`DS4_FLOW_PUMP_WAIT` が有効であれば `flow_pump(c, err)` を実行し、thread を yield します。`flow_pump()` は、空き staging slot や ring slot 等の条件が整う範囲で、expert の読み込みと DMA 転送を進めます。stream が完了すると同期し、routing bounds を host 側で処理して `flow_layer()` に進みます。

値を無効にすると、この stream-query 中の pump ループを丸ごと通らず、stream 同期後に進みます。後続の `flow_layer()` は引き続き `flow_pump()` を呼び、expert flow と転送を続けます。実装にこの変数専用のログ出力やエラー文言はありません。

## 根拠

- `src/dsv41/ds4_model.cu:7293-7304` — GPU stream 待機中の static 判定、`flow_pump()` 呼び出し、同期、bounds の取得。
- `src/dsv41/ds4_model.cu:2704-2737` — `DS4_FLOW`、MXFP4、`DS4_FLOW_TP`、ring の条件と `Chunk::flow` の設定。
- `src/dsv41/ds4_model.cu:3432-3533` — `flow_pump()` が読み込み、staging、ring への転送を進める処理。
- `src/dsv41/ds4_model.cu:3535-3584` — `flow_layer()` 内の継続的な pump と streamed expert の処理。
- `src/dsv41/ds4_model.cu:7381-7387` — flow chunk が `flow_layer()` を呼ぶ経路。

`docs/DETAILS.md` とリポジトリ内の文書では、この変数の直接的な説明は見つかりませんでした。挙動の説明は上記 commit の実装に基づきます。
