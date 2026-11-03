# `--draft-fallback`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` エンジン引数（`root/`） |
| オプション | `--draft-fallback` |
| 別名 | なし |
| 値 | CUDA/HIP/Metal 系は `mtp` または `none`。SYCL build は `none` のみ |

## 役割

`--draft dflash2` 使用時に、DFlash2 drafter が起動できない場合の MTP drafter fallback を選びます。`mtp` は MTP 層を DFlash2 とともにロードして fallback として残し、`none` は MTP 層をロードせず DFlash2 だけで実行します。指定を省略したときの `--draft dflash2` は `none` と同じ扱いです（`src/program/generate.cpp:987-993,1157-1161,5319-5355`）。

## 使い方

```sh
strata --pack target.gguf --mtp /models/mtp --draft dflash2 --draft-model drafter.pack --draft-fallback mtp --spec 6
```

MTP の語彙ファイルだけを使い、MTP 層をロードしない例:

```sh
strata --pack target.gguf --mtp /models/mtp --draft dflash2 --draft-model drafter.pack --draft-fallback none --spec 6
```

## 値と既定値

- CUDA/HIP/Metal 系 parser は `mtp` と `none` だけを受理します。それ以外は標準エラーに `strata generate: --draft-fallback takes mtp or none` を出して終了コード `2` で終了します（`src/program/generate.cpp:3583-3588`）。
- 値を省略すると `next()` が `--draft-fallback needs a value` を標準エラーに出して終了コード `2` で終了します（`src/program/generate.cpp:3293-3298`）。
- `Options` の初期値は空文字列ですが、`--draft dflash2` かつ `--draft auto` でない場合、値が `mtp` でなければ `none` 扱いになります。したがって実効上の既定値は `none` です（`src/program/generate.cpp:990-993,5330-5332`）。
- 同じ引数を複数回指定すると、引数列を順に読む parser が同じ field を更新するため、最後の値が残ります（`src/program/generate.cpp:3293-3298,3583-3588`）。
- SYCL の別 parser は既定値を `none` とし、明示値も `none` だけを受理します。`mtp` を指定すると標準エラーに「only none is supported on this build」と出し、終了コード `2` で終了します（`sycl/src/program/generate.cpp:751-755,2032-2037`）。

## 実行時の動作

`--draft-fallback none` では、DFlash2 の語彙を解決した後に `--mtp` を空にし、MTP 層をロードしない状態にします。語彙の指定には `--mtp DIR`（`DIR/draft_vocab.bin`）または `--mtp-draft-vocab FILE` を使えます。`none` でも `--mtp DIR` を指定した場合、そのディレクトリは語彙の場所として参照されますが、MTP 層はロードされません（`src/program/generate.cpp:5319-5325,5330-5355,6742-6764`）。

この solo モードには `--draft-model PACK`、`--spec` 2 以上、および `--mtp DIR` か `--mtp-draft-vocab FILE` が必要です。不足時は標準エラーに必要条件を表示して終了コード `2` で戻ります。DFlash2 がロード・bind・prepare できない場合も MTP fallback がないため、開始または実行を終了コード `1` で中止します（`src/program/generate.cpp:5330-5333,6765-6772,6802-6815,19703-19722`）。

`--draft-fallback mtp` では `--mtp DIR` の MTP 層をロードしたままにし、DFlash2 の初期化に失敗した場合は標準エラーに理由を出して MTP に切り替えます。DFlash2 側にだけ指定された広い `--spec` を使っていた場合、`--draft-mtp-spec` が明示されていれば fallback 後の窓幅をその値に縮めます（`src/program/generate.cpp:6742-6764,6806-6818`）。

`--draft auto` は両方の drafter を保持するモードなので、`--draft-fallback none` との組み合わせは矛盾として標準エラーに理由を表示し、終了コード `2` で戻ります。`--draft auto` では両方をロードする動作が優先されます（`src/program/generate.cpp:990-993,1159-1164,5326-5329`）。

## 適用条件と副作用

- このオプションの fallback 選択が実際に参照されるのは `--draft dflash2` の経路です。DFlash2 の実行には `--draft-model` などの前提があり、solo と fallback ありで不足時の結果が異なります（`src/program/generate.cpp:5330-5333,6765-6772`）。
- `none` は MTP 層の GPU メモリ負荷をなくしますが、DFlash2 を代替する drafter もなくなります。起動時に DFlash2 の準備に失敗すると処理は継続しません（`src/program/generate.cpp:990-992,6802-6815,19720-19722`）。
- `mtp` は MTP 層もロードするため、その層が使用するメモリが必要です。ソースの usage は約 0.9 GiB と記していますが、実量はモデル・環境に依存し得る値として扱ってください（`src/program/generate.cpp:1159-1161`）。
- MTP の layer split による pipeline windows は、DFlash2 を solo で使う場合には有効になりません。条件判定で自動的に off とされ、その理由を標準エラーに出します（`src/program/generate.cpp:5398-5407,5417-5419`）。
- `src/program/generate.cpp` の共通 parser は CUDA/HIP/Metal 系のビルドで使われ、Metal 用の語彙 fallback も条件付きで実装されています（`src/program/generate.cpp:5335-5343`、`metal/CMakeLists.txt:117`）。SYCL は独立 parser・実装です。実機・特定 Release artifact での動作確認はしていません。

## 出力とエラー

値不正・値欠落・solo の必須条件不足・`auto` との矛盾は標準エラーに診断を出し、終了コード `2` になります（`src/program/generate.cpp:3295-3297,3583-3588,5326-5333`）。solo で DFlash2 の初期化に失敗、または使用不可の場合は MTP へ切り替えず標準エラーに失敗理由を出して終了コード `1` になります。fallback が `mtp` の場合は診断後に MTP を使って処理を続けます（`src/program/generate.cpp:6802-6815,11160-11168,19703-19722`）。

## 根拠

- parser、既定値、値検査: `src/program/generate.cpp:987-993,1157-1161,3293-3298,3583-3588`
- solo 条件、語彙解決、MTP 層の抑止: `src/program/generate.cpp:5319-5355,6742-6764`
- DFlash2 の失敗時の fallback / 終了経路: `src/program/generate.cpp:6765-6818,11160-11168,19703-19722`
- pipeline windows との相互作用: `src/program/generate.cpp:5398-5407,5417-5419`
- SYCL の受理値制限: `sycl/src/program/generate.cpp:751-755,2032-2037`
- Metal build の DFlash2 compile definition: `metal/CMakeLists.txt:117`

調査範囲は上記 checkout のソースです。CUDA/HIP/Metal/SYCL の実機実行、各 Release artifact の照合、および性能測定は行っていません。
