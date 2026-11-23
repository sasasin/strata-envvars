# `strata-inkling --vision`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | Vision shard または vision 重みを含む Hugging Face safetensors のファイルパス／ディレクトリ |

## 役割

画像入力を使う Inkling-2-Mini の `--serve` 実行で、vision encoder の重みの場所を指定する。parser は指定文字列を `ServeConfig::vision_path` と `BackendOpts::vision_path` に保存する。`--info` では同じパスを検査し、画像対応の有無を表示する。画像要求のない通常の token 生成に画像を追加するオプションではない。

## 使い方

```sh
# serve を起動し、画像要求に使う vision shard を指定する
strata-inkling --serve --native /models/Inkling-2-Mini.strata --vision /models/Inkling-2-Mini-Vision.strata

# モデルと vision ファイルを検査し、info 出力の images フィールドを確認する
strata-inkling --info /models/Inkling-2-Mini.strata --vision /models/Inkling-2-Mini-Vision.strata
```

## 値と既定値

`--vision` の直後に 1 個の argv 値を取る。CLI 側では拡張子、空文字列、ファイルの存在を parse 時に検証せず、文字列をそのまま保持する。値を省略すると `missing value after --vision` を stderr に出して終了コード `2` で終了する。オプションを複数回指定した場合、引数走査中に同じフィールドへ代入するため最後の値が残る（`engine/src/inkling2/ink_main.cpp:379-384,406-408`）。

省略時の値は空文字列。空文字列を明示しても同じ扱いとなり、serve の画像対応検査を行わない。値の実質的な受理条件は `vision_probe` が判定する。ソース上では `.strata` の VisionShard と、`.safetensors` ファイル、Hugging Face の safetensors ディレクトリまたは index を検査する経路がある（`engine/src/inkling2/ink_vision.h:100-110,141-148,210-215`）。

## 実行時の動作

- `--info` と併用すると、通常のモデル情報を開いた後に vision パスを `vision_probe` へ渡す。検査に成功すれば `images=1`、失敗すればエラー理由を stderr に `vision shard: ...` と出し、`images=0` を含むモデル情報を表示する。vision 検査失敗だけではこの `--info` 経路は失敗終了しない。なお、`--info` の対象ファイル自体が VisionShard と判定される場合は、その shard 情報を出して先に戻るため、別途指定した `--vision` は検査されない（`engine/src/inkling2/ink_main.cpp:59-98,544`）。
- `--serve` では起動時にパスが空でなければ `vision_probe` を実行し、失敗時は `[inkling2-vision] disabled: ...` を stderr に出す。probe は shard のメタデータを検査するもので、重みを RAM/VRAM にロードせず、`INFO` 行の `images` 値へ検査結果を反映する（`engine/src/inkling2/ink_serve.h:448-456,479-485`; `engine/src/inkling2/ink_vision.h:100-101`）。
- serve 中に画像付き要求を受けると、probe が失敗またはパス未指定の場合は要求を拒否する。成功していれば画像を準備し、backend の `encode_image` を試す。backend が画像を符号化できない場合は CPU ViT encoder を指定パスからロードして再試行する。従って重みのロードは画像要求の処理時まで遅延される（`engine/src/inkling2/ink_serve.h:545-570`; `engine/src/inkling2/ink_backend.h:121-125`; `engine/src/inkling2/ink_vision.h:424-479`）。HIP backend には指定パスから GPU vision shard をロードする実装がある（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2299-2303,3036-3042`）。
- `--info`／`--serve` 以外のモードでも parser は値を保存するが、確認した直接生成経路は token ID を使っており、この引数から画像要求を組み立てない（`engine/src/inkling2/ink_main.cpp:544-549,575-613`）。この調査では build 構成ごとの GPU encoder 実装差を実行して確認していない。

## 適用条件と副作用

画像推論への適用は `--serve` で画像付き要求を処理するときに限られる。vision shard の probe が失敗しても serve 自体は続行し、画像要求のみを利用不可にする。画像要求がある場合は画像ファイルの読込・前処理が行われ、GPU encoder が対応しない／失敗する場合には CPU encoder が重みをロードする。probe 後に画像要求がなければ encoder の重みロードは発生しない（`engine/src/inkling2/ink_serve.h:452-456,545-570`; `engine/src/inkling2/ink_vision.h:424-479`）。

## 出力とエラー

- 値の欠落: stderr に `missing value after --vision`、終了コード `2`（`engine/src/inkling2/ink_main.cpp:381-384`）。
- `--info` の probe 失敗: stderr に `vision shard: <理由>`、標準出力のモデル情報では `images=0`（通常モデル情報の出力後に終了コード `0`）（`engine/src/inkling2/ink_main.cpp:87-98`）。
- `--serve` の probe 失敗: stderr に `[inkling2-vision] disabled: <理由>` を出して起動を続け、serve の `INFO` 行に `images=0` を出す（`engine/src/inkling2/ink_serve.h:452-456,479-485`）。後続の画像要求は `image: engine started without --vision Inkling-2-Mini-Vision.strata` としてプロトコルの `ERR` 応答になる（`engine/src/inkling2/ink_serve.h:545-549,678-704`）。
- probe 後の画像前処理または GPU/CPU encoder の失敗も要求単位で `ERR <理由>` として返される。`prepare_req` が失敗理由を返し、要求処理側がその文字列をプロトコルへ出す（`engine/src/inkling2/ink_serve.h:551-568,678-704`）。
- `--info` 自体のモデルファイルを開けない場合は stderr に `open: <理由>`、終了コード `1`（`engine/src/inkling2/ink_main.cpp:62-66`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-384,406-408` — 値の取得、欠落値エラー、両設定先への代入。
- `engine/src/inkling2/ink_main.cpp:59-98,544` — `--info` の probe、出力、終了経路。
- `engine/src/inkling2/ink_vision.h:100-110,141-148,210-268` — safetensors / VisionShard の検査と不正時の理由設定。
- `engine/src/inkling2/ink_serve.h:448-485,545-570,678-704` — 起動時の遅延 probe、画像要求の可否、encoder fallback、要求エラー応答。
- `engine/src/inkling2/ink_backend.h:121-125` — backend の任意 GPU encoder 契約と CPU fallback 条件。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2299-2303,3036-3042` — HIP backend の vision path 利用と GPU load。
