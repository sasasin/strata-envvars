# `--vision`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（全カード分割 engine） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

画像を含む `GENI` / `BGENI` 要求を engine が受理できるようにする起動時フラグです。画像エンコーダーを起動したり画像ファイルを直接読む設定ではありません。画像埋め込みを含む要求を処理するには、このフラグに加えて、フロントエンドが `sfnx-vision` 形式の埋め込みを要求プロトコルで渡す必要があります（`src/split/tools/sfnx.cpp:69,107-108,974-990`）。

## 使い方

```sh
strata-split-N --serve --native MODEL.gguf --mtp MTP_DIR --vision
```

`N` はビルドされたカード数に対応します。`--native` と `--mtp` は起動に必要な別の引数です。通常は利用者が直接起動するのでなく、Strata の Terminal が engine を選択して起動します（`docs/SPLIT_ENGINE.md:1-5`）。

## 値と既定値

値や引数は不要です。未指定時の `Args::vision` は `false` で、指定すると `true` になります。同じフラグを複数回指定しても真のままです。`--vision=false` のような値付き形式は受理されず、後続の `false` が未知の引数として扱われます（`src/split/tools/sfnx.cpp:65-70,72-98`）。

## 実行時の動作

engine は `GENI` / `BGENI` を画像要求として判定します。`--vision` が有効なら `parse_gen` が要求行から埋め込みファイルのパスを受け取り、`attach_images` がそのファイルを読み込んで画像埋め込みを要求に結び付けます。ファイルには `sfnx-vision` のレコードが必要で、各レコードには `SVE1` 識別値、行数・グリッド寸法・埋め込み幅、および埋め込み float データが含まれます。`img_keys` は任意で、指定された場合は画像数とキー数も照合します（`src/split/tools/sfnx.cpp:107-108,138-189,222-250,298`）。

このフラグが無効でも通常の `GEN` / `BGEN` テキスト要求は引き続き受理されます。`BGENI` を使う場合はさらに `--batch` が 2 以上である必要があります（`src/split/tools/sfnx.cpp:89,974-990`）。

## 適用条件と副作用

フラグ自体には backend や環境変数による条件分岐はなく、engine 起動時に boolean として保持されます。画像要求が届いたときだけ有効性を確認し、画像の埋め込みファイルを開いて読み込みます。このため `--vision` の指定だけでは画像要求は送信されず、画像データも準備されません（`src/split/tools/sfnx.cpp:65-70,141-165,979-990`）。

## 出力とエラー

フラグなしで `GENI` / `BGENI` を送ると、engine は `ERR this engine was started without --vision` を stdout に返し、その要求を処理せず次の入力へ進みます。`--vision` 有効時の画像埋め込みファイルを開けない、形式・幅が不正、途中で読み込みが終わる、プロンプト中の画像 pad token 数とレコード数が合わない場合も、該当する `ERR GENI: ...` / `ERR BGENI: ...` を stdout に返して要求を拒否します（`src/split/tools/sfnx.cpp:147-188,974-995`）。

## 根拠

- parser と既定値: `src/split/tools/sfnx.cpp:65-70,72-104`
- `GENI` / `BGENI` の判定、フラグ未指定時の拒否、要求処理: `src/split/tools/sfnx.cpp:974-998`
- 埋め込みファイルの読み込み・形式検証・要求への結合: `src/split/tools/sfnx.cpp:138-189,222-250,298`
- engine の役割と自動起動の説明: `docs/SPLIT_ENGINE.md:1-5`
