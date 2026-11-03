# `DS4_SKIP_UNPICKED_ROWS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DS4 の GPU chunk 実行で、指定した行数以下の chunk は、その layer の routing で少なくとも 1 行が選んだ streamed expert だけを処理し、GPU にコピーします。既定のしきい値は 0 で、すべての chunk について streamed expert を従来どおり扱います。対象は `run_dev_chunks()` の batch streamer です。flow 経路では expert の読み込みが `flow_layer()` に分岐し、この batch streamer を使わないため、この設定の skip 判定はコピー動作に適用されません（`src/dsv41/ds4_model.cu:744-750,11783-11790,12035-12095`）。

## 値と判定

対象変数は `std::getenv` で読み、値が設定されていれば `std::atoi` で整数に変換し、負値は `std::max(0, ...)` で 0 にします。`atoi` のため文字列全体の妥当性検査はなく、数値として読める先頭部分が変換されます。

| 状態 | しきい値への扱い |
|---|---|
| unset | 0。全 chunk で skip しない |
| 空文字 | `atoi("")` が 0 となり skip しない |
| 数値 0、または数値に変換できない文字列 | 0 となり skip しない |
| 正の整数 | その値以下の行数の chunk だけ skip 対象 |
| 負の整数 | 0 に丸められ、skip しない |
| 数字の後ろに文字が続く文字列 | `atoi` が読める先頭の整数部分で判定（例: `12rows` は 12） |

上限 clamp はありません。`atoi` の整数範囲を超える入力の結果は、この実装では検査・保証されません。別変数 `DS4_SKIP_UNPICKED` が設定され、かつ `atoi(value) != 0` なら、この変数の値より優先してしきい値を `INT_MAX` にします。その変数が unset、空、数値変換結果 0 の場合は `DS4_SKIP_UNPICKED_ROWS` が評価されます。したがって、たとえば `DS4_SKIP_UNPICKED=1` は全 chunk を対象にし、`DS4_SKIP_UNPICKED=0` は対象変数を無効化せず、対象変数の判定へ進みます（`src/dsv41/ds4_model.cu:4432-4442`）。

## 有効になる条件

- DS4 のこの GPU 実装で、`run_dev_chunks()` が batch streamer を使い、対象 chunk/layer に streamed expert の batch があること。
- chunk の行数 `run.T[k]` が変換後のしきい値以下であること。判定は `<=` です。しきい値 0 では正の行数を持つ chunk は対象になりません。
- その layer の routing が完了し、expert ごとの row bound が利用可能になること。選択判定は streamed expert の bound の終端が始端より大きいか（`routed_bounds[v + 1] > routed_bounds[v]`）です。

有効な chunk では、コピー側は該当 layer/chunk の routing 情報が届くまで batch を進めず、routing 後に選ばれた expert だけを同じ batch slot へコピーします。ファイル上の expert は選ばれたものだけを読み込み、選ばれなかった expert は読み込み・コピーを飛ばします。`read_ahead()` も skip 対象 batch ではファイル領域の先読みを発行せず、batch の進行だけを記録します（`src/dsv41/ds4_model.cu:4464-4482,4485-4498,4511-4546`）。

## 実行時の詳細

設定は `skip_unpicked_rows()` の関数内 static 値として初回評価時に一度だけ読み取られます。その後の環境変更は同一プロセス内で再評価されません。`run_dev_chunks()` はこの値を使って各 `run.T[k] <= threshold` のフラグを `Streamer::skip_k` に設定し、flag が立った chunk の batch を routing 完了まで待たせます（`src/dsv41/ds4_model.cu:4434-4442,12035-12040,12082-12095`）。

各 layer の routing bound が得られると、それを streamer に渡して `copy_ahead()` を再開します。選ばれない expert は（ファイルにある場合）読み込み時にスキップされ、DMA コピー時にも除外されます。明示的な不正値エラーや fallback ログはありません。読み込みに失敗した場合は `reading layer <番号>'s experts from the model's files failed` をエラーとして返し、GPU の batch slot がない場合は `no slots to stream experts into on CUDA<device>` を返します。worker のエラーは呼び出し側の run に伝播します（`src/dsv41/ds4_model.cu:4490-4524,11791-11813,12096-12113,13009-13047`）。

この機能が skip 対象として処理した streamed expert 数は、プロセス終了時に少なくとも 1 件の集計がある場合、stderr に `ds4 skip unpicked: %zu streamed experts copied, %zu left out (%.1f%%)` の形式で出力されます。ここで copied / left out は skip 対象 batch で数えた expert 数です（`src/dsv41/ds4_model.cu:826-835,4527-4536`）。

## 根拠

- `src/dsv41/ds4_model.cu:4432-4442` — 既定値、`DS4_SKIP_UNPICKED` との優先順位、`atoi` と負値 clamp、static cache。
- `src/dsv41/ds4_model.cu:744-750,11783-11790` — batch streamer と flow 経路の違い。
- `src/dsv41/ds4_model.cu:12035-12113` — chunk 行数によるフラグ設定と batch の準備。
- `src/dsv41/ds4_model.cu:4490-4524,4527-4546,11791-11813` — routing 待ち、選択 expert の読み込み・コピー、失敗経路。
- `src/dsv41/ds4_model.cu:826-835,13009-13047` — 終了時 stderr 集計と worker エラーの伝播。
- Strata の `docs/` にはこの変数名の説明は見つかりませんでした。候補索引 `docs/envvars/000_envvers.md` には掲載されていますが、実装根拠は上記ソースです。
