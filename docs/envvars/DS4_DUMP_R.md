# `DS4_DUMP_R`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DS4 V4.1 の chunked prompt 経路で、MoE routing の中間データを指定ファイルへバイナリ出力する診断用フックです。レコードには、各 chunk・各 layer の expert pick、仮想 slot と row の対応、router logits と bias が含まれます。通常の window 経路や decode の routing を記録するものではありません。

## 値と判定

この変数は数値や真偽値として parse されず、値全体がそのまま出力ファイル名として `std::fopen(path, "wb")` に渡されます。値を読むのは `Impl` のメンバー初期化時です。

| 状態 | 動作 |
|---|---|
| unset | `dump_r` は null となり、routing dump を行わない |
| 設定あり | 値をファイル名として書き込み binary mode で開く。`wb` のため、開けた既存ファイルは切り詰められる |
| 空文字 | 設定ありとして `fopen("", "wb")` を試みる。開けず null になれば dump は行われない |
| 開けないパス | `fopen` が null を返し、dump は行われない。ここに対応する明示的な警告・エラー出力はない |

文字列比較、数値変換、空白除去、大小文字変換、範囲制限はありません。モデル `Impl` の生成時に値を読み、そのインスタンスの存続中は `dump_r` を使います。実行中に環境変数を変更しても、既に生成済みの `Impl` には反映されません。

## 有効になる条件

- Strata の DS4 V4.1 実装が使われること。
- 入力処理が chunked prompt 経路を通ること。`feed()` は `chunk > 0` かつ入力長が `chunk_min` 以上の場合にその候補とし、実際には path 選択によって window 経路へ進むこともあります。
- chunked prompt 経路自体は `--tp` / `--threads`、`--prefill-chunk`、ビルド時既定値、`DS4_WINDOWS` などで設定されます。`DS4_CHUNK` が設定されると prompt-parallel が有効な場合に chunk 長を上書きします。chunk 長が正でなければ chunked 経路は使われません。
- 出力ファイルが開けていること。
- `layer_chunk()` が MoE routing まで実行すること。長い prompt の skip (`DS4_YOCO`) で `kv_only` として処理される部分は、routing 前に戻るためレコードを作りません。

したがって、変数が設定されてファイルを開けても、decode、windowed prompt、または別の実行経路ではレコードは書かれません。複数メンバーの層では `mi == 0` のメンバーだけが記録し、同じ層を複数回書く重複を避けます。

## 実行時の詳細

`layer_chunk()` が attention と router 計算を行い、`moe_sort()` により routing row を並べ、CUDA stream を同期した後、`dump_r != nullptr && mi == 0` の場合にデバイス上の pick、sorted row-token、gate logits と gate bias をホストへコピーして書き出します。1レコードの順序は次の通りです。

1. `int64` 8個のヘッダー: `[layer, p0, T, k, n_exp, n_vs, n_slots, kPicks]`。
2. `int32` の expert picks `[T, kPicks]`。
3. `int32` の expert ごとの virtual slot `[n_exp]`。
4. `int32` の slot ごとの row 範囲 `[n_vs + 1]`。
5. `int32` の sorted rows の token index `[T, k]`。
6. `float32` の router logits `[T, n_exp]`。
7. `float32` の gate bias `[n_exp]`。

ヘッダーの `p0` はその `layer_chunk()` 呼び出しの開始位置、`T` はその呼び出しで処理する token 数です（長い prompt の部分処理では元 chunk 全体とは異なる場合があります）。`k` は layer の expert 数/ token、`n_exp` は expert 数です。`kPicks` 幅の picks 配列は、下流ツールで先頭 `k` 個に切り詰めて扱われます。データは `fwrite` でホスト表現のまま出力され、各レコード後に `fflush` されます。`fwrite` と `fflush` の戻り値は検査されず、書き込み失敗を通知する専用ログもありません。出力のために GPU から CPU へのコピーとファイル I/O が追加されます。

同梱の `tools/dsv41/dumpcmp.py` はこのレコード順で `DS4_DUMP_R` を読み、routing/pick の確認に利用します。`docs/DETAILS.md` にこの変数の説明や測定値は見当たりません。

## 根拠

- 値の読み取り、`wb` での open、コメントに記された record layout: `src/dsv41/ds4_model.cu:1131-1135`。
- chunked prompt の有効条件と chunk 長の設定: `src/dsv41/ds4_model.cu:1925-1931,1990-2000`。
- `feed()` から chunked/windowed 経路を選ぶ条件: `src/dsv41/ds4_model.cu:9356-9367`。
- chunk 呼び出しと `kv_only` / 部分 chunk の経路: `src/dsv41/ds4_model.cu:7467-7489,8187-8190`。
- `kv_only` 時は attention/indexer の後、MoE routing 前に return: `src/dsv41/ds4_model.cu:7222-7224`。
- routing の生成、同期、メンバー条件、各配列のコピーと書き込み: `src/dsv41/ds4_model.cu:7271-7285,7303-7323`。
- 同梱 reader が使うヘッダーと配列のサイズ・型: `tools/dsv41/dumpcmp.py:40-55`。
- `Impl` destructor に `dump_r` の明示的な `fclose` はない: `src/dsv41/ds4_model.cu:1243-1286`。
