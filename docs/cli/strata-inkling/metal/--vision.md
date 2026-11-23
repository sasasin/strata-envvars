# `--vision`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal`（Metal backend） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | Vision モデルのファイルパス。別個の型変換・形式検証は parser にない |

## 役割

Inkling-2-Mini の画像入力に使う Vision shard のパスを指定する。通常実行ではパスを runner に渡して保留し、`--image` で画像を処理するときに Vision shard を読み込む。Metal backend を利用するサーバー経路でも、backend options の `vision_path` として渡された値を画像要求時に使う。

## 使い方

```sh
# Metal でテキストモデルと Vision shard を指定して画像をエンコードする
strata-inkling-metal --model model.strata --vision vision.strata --image picture.png

# モデル情報に Vision shard の指定を付けて表示する
strata-inkling-metal --info model.strata --vision vision.strata
```

`--info` は Vision shard の内容を検証せず、パスが指定されたかどうかを `images=1` として表示する。

## 値と既定値

値は `argv` の次要素をそのまま文字列として受け取る。未指定時は空文字列で、Vision の設定なしとして扱われる。空文字列を明示した場合も設定なしと同じになる。値の存在確認、拡張子確認、重複指定時の拒否は parser にない。通常の引数走査では複数回指定すると最後の値が残る。値を省略すると `missing value for --vision` を stderr に出して終了コード 2 で終了する（`engine/src/inkling2/metal/ink_metal_main.cpp:432-437,445`）。

## 実行時の動作

通常モードでは、パーサーが設定した `vision_path` を `runner.init` に渡し、runner は `pending_vision_path` に保持するだけで初期化時には Vision shard をロードしない（`engine/src/inkling2/metal/ink_metal_main.cpp:445,489-493`; `engine/src/inkling2/metal/ink_metal_runner.h:230-232,617-618`）。ログは設定なしを `vision=off`、パスがあるがまだ未ロードなら `vision=lazy` と表示する（`engine/src/inkling2/metal/ink_metal_runner.h:758-764`）。

`--image` が指定された場合は、runner が Vision を必要時にロードして画像ファイルをエンコードする。成功時はトークン数・埋め込み次元などを stdout に `[VISION] OK: ...` と表示する（`engine/src/inkling2/metal/ink_metal_main.cpp:496-508`; `engine/src/inkling2/metal/ink_metal_runner.h:768-775`）。`--info FILE --vision VISION` の経路では、`--info` の後ろにある `--vision` の値を探して `images=1` を表示するが、Vision ファイル自体は開かない（`engine/src/inkling2/metal/ink_metal_main.cpp:439-443,91-115`）。

サーバーで Metal backend がこの値を受け取る場合も、Metal backend は options の `vision_path` を runner に渡す（`engine/src/inkling2/metal/ink_metal_backend.mm:92-108`）。画像要求時に `encode_image` から遅延ロードし、失敗時には共通サーバー経路が CPU Vision encoder への fallback を試みる（`engine/src/inkling2/metal/ink_metal_backend.mm:437-442`; `engine/src/inkling2/ink_serve.h:561-568`）。このソースの `strata-inkling-metal` 単体 parser は `--serve` を認識せず未知の引数として終了するため、上記サーバー動作は単体コマンド例の実行モードではない（parser の引数分岐と未知引数処理: `engine/src/inkling2/metal/ink_metal_main.cpp:432-467`）。

## 適用条件と副作用

- Metal runner の Vision ロードは画像処理時まで遅延する。Vision を指定してテキストだけ実行する場合、Vision shard の mmap は行われない（遅延保持: `engine/src/inkling2/metal/ink_metal_runner.h:617-618,768-775`）。
- ロード時は指定ファイルを読み取り専用で開き、サイズと先頭ヘッダーを確認し、manifest を読み、ファイルを `mmap` して Metal buffer として包む（`engine/src/inkling2/metal/ink_metal_vision.h:75-121`）。
- Vision shader ライブラリのコンパイルは `--vision` の有無にかかわらず runner 初期化で行われる。これは当該オプション自体による条件付き副作用ではない（コンパイル関数: `engine/src/inkling2/metal/ink_metal_main.cpp:32-75`; 初期化からの呼び出し: `engine/src/inkling2/metal/ink_metal_runner.h:230-243`）。

## 出力とエラー

- 通常モードで `--model` がない場合は usage を stderr に出して終了コード 2（`engine/src/inkling2/metal/ink_metal_main.cpp:470-473`）。
- `--image` と Vision パスのどちらかが使えず画像処理に失敗すると、`[ERROR] vision: ...` を stderr に出して終了コード 1（`engine/src/inkling2/metal/ink_metal_main.cpp:496-503`）。Vision パス未設定時のエラーは `metal vision path not configured`（`engine/src/inkling2/metal/ink_metal_runner.h:768-774`）。
- ファイルを開けない、サイズ不正、短いヘッダー、manifest 読み込み失敗、mmap 失敗はそれぞれエラー理由を返す（`engine/src/inkling2/metal/ink_metal_vision.h:75-119`）。画像ファイルをデコードできない場合は `stbi_load failed: <path>`（`engine/src/inkling2/metal/ink_metal_vision.h:148-153`）。
- 不明な引数は `unknown arg: ...` を stderr に出して終了コード 2（`engine/src/inkling2/metal/ink_metal_main.cpp:464-467`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:432-467` — 引数解析、値の取得、省略値エラー、`--info` の特別処理、未知引数の失敗。
- `engine/src/inkling2/metal/ink_metal_main.cpp:489-508` — Vision パスを runner に渡す箇所と `--image` の処理・出力。
- `engine/src/inkling2/metal/ink_metal_runner.h:617-618,758-775` — パスの遅延保持、状態ログ、必要時ロード。
- `engine/src/inkling2/metal/ink_metal_vision.h:75-121,148-153` — Vision shard の読み込みと画像デコードの失敗経路。
- `engine/src/inkling2/metal/ink_metal_backend.mm:92-108,437-442`、`engine/src/inkling2/ink_serve.h:561-568` — Metal backend へのパス転送と、画像要求時の CPU fallback 経路。
