# `--vision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（通常エンジン parser） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

常駐サーバー (`--serve`) で画像入力を受け付ける GENI リクエスト経路を有効にします。画像自体をこのフラグで読み込むのではなく、`strata-vision` が作成した画像埋め込みファイルと画像位置情報を GENI リクエストでエンジンへ渡します。ヘルプ文字列も `--serve` と GENI、`strata-vision` の埋め込みを説明しています（`src/program/generate.cpp:890`）。

## 使い方

```sh
strata generate --pack <pack-dir> --serve --vision --spec <T> --prefill <CHUNK> --expert-cache <N>
```

これは起動引数の形を示す例です。`--serve` 自体に `--spec` と `--prefill` が必要で、使用するモデル・expert cache に応じた設定も必要です（`src/program/generate.cpp:8354-8359`）。起動後は標準入力へ `GENI <max_new> <embeddings-file> <token-id,id,...>` を送り、画像範囲には画像用 token ID `248056` (`<|image_pad|>`) を並べます。リクエスト形式の parser は `src/program/generate.cpp:12287-12295`、画像 token と埋め込みの対応処理は `src/program/generate.cpp:12391-12454` にあります。

## 値と既定値

値は不要です。parser は `--vision` を見つけると `o.vision = true` にし、値の変換や値域検証は行いません（`src/program/generate.cpp:2637-2639`）。既定値は `false` です（`src/program/generate.cpp:720-723`）。同じフラグを繰り返しても有効状態のままです。値を後置すると、その文字列は別引数として扱われ、未認識なら `unknown argument` で終了コード 2 になります（`src/program/generate.cpp:2787-2792`）。

## 実行時の動作

有効時、起動時に `--max-context + 64` 個分の三軸 M-RoPE 位置テーブルをホストメモリと CUDA デバイスに確保し、全軸を位置番号で初期化します。確保または転送に失敗すると `cannot allocate the image position table` を標準エラーへ出し、終了コード 1 で終了します（`src/program/generate.cpp:3942-3958`）。複数 GPU の layer split を使う場合は各 stage のデバイスにもテーブルを確保・転送し、失敗時は `the image position table failed` を出して終了します（`src/program/generate.cpp:4373-4383`）。このため `--serve` を付けない起動でもテーブル確保は発生しますが、画像を受ける GENI 要求処理は serve の要求ループにあります。

serve の要求ループでは `GENI` を `GEN` と区別し、`--vision` なしのエンジンに届いた `GENI` は `ERR this engine was started without --vision` を標準出力に返して、その要求を続行しません（`src/program/generate.cpp:12287-12290`, `12391-12392`）。有効な GENI では埋め込みファイルを読み、`SVE1` ヘッダー、画像グリッド寸法、モデルの埋め込み幅と各画像の float データを検査します。画像行は prompt 内の `<|image_pad|>` token に対応付け、各画像の格子に応じた M-RoPE 座標を作り、CUDA と layer split 各デバイスへ転送します（`src/program/generate.cpp:12394-12423`, `12426-12472`）。通常の `GEN` はテキスト位置の恒等テーブルを使用します（`src/program/generate.cpp:12402-12404`）。

`--vision` は session 構成 fingerprint にも含まれます（`src/program/generate.cpp:9448-9462`）。そのため vision 設定が異なる構成は同じ session 構成として扱われません。

Qwen3.6 family へ振り分けられた場合は別 parser となり、そちらの `--vision` は [Qwen3.6 用文書](../qwen36/--vision.md)を参照してください。索引も通常 engine と Qwen3.6 の scope を分けています（[`CLI 索引`](../../README.md)）。

## 適用条件と副作用

- 画像入力には `--serve` と GENI プロトコルを使います。エンジン側は埋め込みファイルを開いて読むだけで、画像ファイルの decode や埋め込み生成は `strata-vision` 側の役割です（ヘルプ: `src/program/generate.cpp:890`、要求処理: `src/program/generate.cpp:12408-12423`）。
- `--vision` はモデルの vision 対応有無を事前検査しません。文書化されたこの経路では埋め込み幅がモデルの `n_embd` と一致するか要求ごとに検査されます（`src/program/generate.cpp:12414-12418`）。
- 起動時に追加のホスト・GPU メモリを使います。必要量の式はソース上で分かりますが、実際のバイト数や各 backend での負荷はここでは測定していません。
- 画像埋め込みファイルが開けない、形式・幅が不正、画像数と prompt の画像 token 数が合わない、画像 token 範囲が不足または末尾にある場合は `ERR ...` を返し、その要求を拒否します。位置テーブル更新に失敗した場合はテーブルを恒等位置へ戻してから要求を拒否します（`src/program/generate.cpp:12408-12425`, `12428-12455`, `12472-12480`）。
- prompt と生成長が `--max-context` を超える場合も要求は `ERR` になります（`src/program/generate.cpp:12484-12488`）。

## 出力とエラー

- `--vision` なしでの GENI: 標準出力に `ERR this engine was started without --vision`。要求単位のエラーです（`src/program/generate.cpp:12391`）。
- 埋め込みファイルの open、形式、短いデータ、画像数・token 数の不整合、位置テーブル転送の失敗: 標準出力に `ERR <理由>` を出し、位置テーブルを恒等状態に戻して要求ループを継続します（`src/program/generate.cpp:12408-12425`, `12428-12455`, `12472-12480`）。
- 起動時の位置テーブル確保失敗は標準エラーに診断を出し、終了コード 1 です（`src/program/generate.cpp:3951-3955`）。layer split 側の確保失敗も終了コード 1 です（`src/program/generate.cpp:4375-4380`）。

## 根拠

- parser の既定値: `src/program/generate.cpp:720-723`
- help と parser: `src/program/generate.cpp:890`, `2637-2639`
- 起動時 M-RoPE table の確保: `src/program/generate.cpp:3942-3958`, `4373-4383`
- session fingerprint: `src/program/generate.cpp:9448-9462`
- GENI 判定、埋め込み読み込み・検証・位置テーブル更新: `src/program/generate.cpp:12287-12392`, `12394-12425`, `12426-12480`
- serve 起動条件: `src/program/generate.cpp:8354-8359`
