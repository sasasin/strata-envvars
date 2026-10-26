# `TQH_DEBUG`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

`tools/trellis/tqenc_hip.cpp` の standalone HIP trellis encoder `tqh_encode()` 内で、探索途中の GPU 状態を stderr に出す診断スイッチです。Strata の通常のエンジンやサーバーの動作を制御する参照は見つかりませんでした。このファイルは `tools/trellis/build.sh hip` で専用テスト実行ファイルと HIP encoder ライブラリに組み込まれます。

## 値と判定

| 環境の状態 | 判定 |
|---|---|
| 未設定 | 診断しない |
| 設定済み（空文字を含む） | 診断する |

値の内容は比較・数値変換されません。`getenv("TQH_DEBUG")` が null かどうかだけを見るため、`0`、`false`、その他どの文字列でも、設定されていれば有効です。

## 有効になる条件

- `tqh_encode()` が有効な型（`type_kbits(type)` が 4〜7）で呼ばれ、エンコードの chunk ループ内の反復処理まで到達すること。無効な型は先に `-1.0` を返し、chunk がない場合（`nblocks <= 0`）は診断箇所に到達しません。
- HIP 版 trellis encoder をビルドして実行すること。リポジトリ内の呼び出し元は `tools/trellis/tqenc_hip_test.cpp` です。通常の Strata engine からの参照はありません。

## 実行時の詳細

環境変数は `tqh_encode()` の各探索反復（scale try と iteration の組み合わせ）で毎回読み直され、static cache されません。設定されていると、その反復で `hipDeviceSynchronize()` を行い、GPU から候補、候補コスト、最良誤差、現在の scale、active flag の先頭部分を host にコピーし、block index 0〜3 の診断行を stderr に出します。行の形式は `[dbg try %d it %d] block %d: c %d cost %g best_err %g dcur %g active %d` です。

この分岐は kernel の候補選択や出力バッファを書き換えず、同期と読み取り、ログ出力を追加します。同期・コピーに失敗すると `HCHECK` が `HIP error ...` を stderr に出して `abort()` します。計測時間 `timing[0]` はループ開始から pack kernel の同期までを測るため、この診断による同期とコピー時間も含まれます。

診断コードは各配列から固定サイズで最大4要素をコピーしますが、呼び出し側の `nblocks` が4未満でも縮小しません。その場合、コピー範囲が当該 chunk 用の配列長を超える可能性があります。ソース上で小さい chunk に対するガードは確認できませんでした。

## 根拠

- `tools/trellis/tqenc_hip.cpp:462-476`: `tqh_encode()` と無効型の早期 return。
- `tools/trellis/tqenc_hip.cpp:484-509`: chunk / try / iteration のループ構造。
- `tools/trellis/tqenc_hip.cpp:524-543`: kernel 後の診断分岐、同期・host copy・stderr 出力、計測範囲。
- `tools/trellis/build.sh:13-21`: HIP encoder とテスト実行ファイル／共有ライブラリの standalone build。
- `tools/trellis/tqenc_hip_test.cpp:14-15,43,82,100`: リポジトリ内で確認できた `tqh_encode()` 呼び出し元。
- `tools/trellis/README.md:1,12-25`: Trellis encoder が研究用 standalone ツールとして記載され、HIP build と専用テストの使い方が示されている。
