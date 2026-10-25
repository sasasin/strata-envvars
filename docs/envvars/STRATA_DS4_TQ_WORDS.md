# `STRATA_DS4_TQ_WORDS`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata-dsv41` の GPU trellis (TQ) expert カーネルが、重みレコード内のビットストリームを読む幅を切り替えます。未設定時は既定の 16-bit load 経路、環境変数を `atoi` で変換した結果が 0 以外なら 32-bit load 経路を使います。対象はカーネル内部の stream window 読み取りであり、CPU TQ decoder の読み取り幅は変えません。

## 値と判定

値は `std::atoi` で変換し、その結果が 0 以外かで判定します。文字列全体の妥当性は検証しません。

| 環境変数の状態・値 | 判定 |
|---|---|
| 未設定 | OFF（16-bit load） |
| 空文字、数字に変換されない文字列、`0` | OFF |
| `1`、`-1`、`2` | ON（32-bit load） |
| 数字の後ろに文字が続く値（例: `1abc`） | 数字接頭部を `atoi` が変換し、その結果が 0 以外なら ON |

したがって、設定有無だけでは ON にならず、文字列全体の `"1"` 比較でもありません。符号や先頭空白を含む入力の扱いも `atoi` に従います。
コードは数値の範囲を検査しません。`atoi` で表現できない大きさの数値を渡した場合の結果は定義済みの設定値として扱えません。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` で GPU backend を有効にしたビルドに含まれる `strata-dsv41` が対象です。DSV41 は CUDA または HIP の GPU build で追加されますが、`STRATA_HIP_GFX906` の build ではこの executable を追加しません。GPU backend なしでは host-side benchmark のみとなり、この GPU dispatch はありません (`CMakeLists.txt:800-811,2380-2384`)。
- DSV41 の CUDA/HIP trellis GPU 経路が呼ばれた場合に有効です。IQ GPU dispatcher は `is_tq(...)` の型を TQ 専用 `tq` 関数へ渡します (`src/dsv41/ds4_iq.cu:1399-1409,1428-1444,1458-1467`)。
- TQ 型以外の expert はこの切替を使いません。CPU decoder 経路にも `use_words()` の参照はありません。
- CLI、設定ファイル、別環境変数による優先順位や上書きは実装されていません。

## 実行時の詳細

`use_words()` 内の関数ローカル `static const bool` が、最初に TQ GPU dispatch に到達した時点で環境を一度読み、以降の呼び出しで値をキャッシュします。起動後に環境を変更しても、このプロセスでは再評価されません (`src/dsv41/ds4_tq.cu:469-476`)。

ON の場合、TQ gate/up、down、set gate/up、set down、複数行 matrix-vector の各 dispatch が `<..., true>` の kernel specialization を選びます。OFF の場合は同じ演算の `<..., false>` specialization を選びます (`src/dsv41/ds4_tq.cu:484-536`)。`tile_dot` はこのテンプレート値を使って、32-bit 経路では 4-byte aligned `uint32_t` 読み込みから同じビット窓を組み立て、16-bit 経路では `uint16_t` 読み込みから組み立てます (`src/dsv41/ds4_tq.cu:60-80,131-159,164-184`)。カーネル演算やモデル型を選び直す設定ではありません。

この変数自体について専用ログ、警告、エラー出力はありません。通常の TQ dispatch の geometry 不一致などでは別途 `ds4 tq: ...` を stderr に出して `false` を返しますが、これは値の判定結果ではなく dispatch の適用可否です (`src/dsv41/ds4_tq.cu:478-480,484-536`)。

## 根拠

- `src/dsv41/ds4_tq.cu:469-476` — `atoi` による判定、既定値、static cache。
- `src/dsv41/ds4_tq.cu:131-159,164-184` — 32-bit / 16-bit stream window の生成と呼び分け。
- `src/dsv41/ds4_tq.cu:484-536` — 4 種の expert dispatch と mv が切替を使う箇所。
- `src/dsv41/ds4_iq.cu:1399-1409,1428-1444,1458-1467` — 型に応じて TQ dispatcher に到達する呼び出し元。
- `CMakeLists.txt:800-811,2380-2384` — DSV41 GPU executable の build 条件。
- `docs/DEEPSEEK41.md:125-126` — DSV41 が扱う trellis 型の説明。環境変数の既定値・値判定・測定結果について、この資料に別の記載はありません。

実装コメントには Radeon R9700 での比較値 `13.8 vs 14.2 ms a token` と「no gain measured」とありますが、比較順、実行条件、測定方法は記載されていません (`src/dsv41/ds4_tq.cu:472-473`)。そのため、この文書ではどちらの値がどの経路か、また一般的な性能差かを断定しません。
