# `strata-hy4-metal --vision`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--vision` |
| 別名 | なし |
| 値 | Vision shard のファイルパスを 1 つ取る。parser 上の形式・存在確認はない |

## 役割

HY4-Flash の画像入力に使う Vision shard（`.strata`）のパスを指定する。通常実行では `--image` で渡した画像をエンコードするために使い、`--serve` では起動時の画像対応可否確認と、画像を含むリクエストのエンコードに使う。`--vision` 自体は画像入力を発生させず、通常実行で `--image` がなければ shard のロードも行わない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1498-1500,1600-1602,1682-1699,1773-1782`）。

## 使い方

```sh
# オフライン実行で画像1枚を画像 placeholder に対応させる
strata-hy4-metal --model model.strata --engram engram.strata --tokens ids.txt \
  --vision Hy4-Flash-Vision.strata --image picture.jpg

# server を画像 shard 付きで起動し、画像リクエストを受け付ける
strata-hy4-metal --model model.strata --engram engram.strata --serve \
  --vision Hy4-Flash-Vision.strata
```

オフライン例では `ids.txt` に画像 token を含む prompt が必要で、画像ファイル数と画像 placeholder 数を一致させる。server 例ではクライアントのリクエストに画像ファイルが含まれる場合に Vision shard を使う（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1682-1699`、`engine/src/hy4flash/metal/hy4_metal_serve.h:320-347`）。

## 値と既定値

値は `argv[++i]` から文字列として読み、後続の `--vision` があれば値を置き換える。数値変換、空文字の拒否、パスの事前検証は parser にはない。省略時の値は空文字列で、別の既定パスへの補完もない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1498,1504-1506,1600`）。

## 実行時の動作

- **オフライン実行:** `--image` がある場合、まず画像を読み込み・デコード・リサイズし、token 列の各画像 token を画像サイズに応じた token run に展開する。このとき `--vision` が空なら `image: --vision FILE is required with --image` を stderr に出して終了コード `1` になる。画像数と placeholder 数の不一致も同じ `image:` エラー経路で終了する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1682-1699`、`engine/src/hy4flash/run/hy4_vision.h:259-287,290-310`）。画像がある場合に限り、runner 初期化後に Vision shard を検査・マップし、Metal Vision kernel をコンパイルして画像を encode する。失敗時は `images: <理由>` を stderr に出して終了コード `1`（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1782`、`engine/src/hy4flash/metal/hy4_metal_vision.h:91-126`）。
- **server (`--serve`):** 値は `ServeOpts.vision` に渡される。server 起動時に空でないパスを `vision_probe` し、成功なら `INFO ... images=1`、失敗なら stderr に `[vision] disabled: <理由>` を出し、server 自体は画像無効で起動する。画像を含む要求は無効状態なら `ERR image: this engine was started without the Vision shard (--vision Hy4-Flash-Vision.strata)` で拒否される。probe が成功しても shard の実ロードと kernel compile は最初の画像要求時で、そこで失敗した要求には `ERR image: <理由>` を返す（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1642,1674`、`engine/src/hy4flash/metal/hy4_metal_serve.h:292-304,320-374`）。
- **`--load-only` との併用:** モデルロード後に通常終了するため、先に解析済みの `--vision` は検査・ロードされない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1623,1630-1636`）。

## 適用条件と副作用

対象は Metal runner `strata-hy4-metal` であり、索引上の CUDA/HIP runner や SYCL runner の `--vision` とは別スコープである（`docs/cli/README.md:1358-1361`、`docs/cli/000_cli_tools.md:11`）。Vision shard の probe は profile が `VisionShard` であること、対応する vision config と tensor dtype、必要 tensor 群などを検査する。通常実行で画像を扱うときはその shard を read-only mmap し、カーネルを compile して Metal バッファとして wrap する（`engine/src/hy4flash/run/hy4_vision.h:67-124`、`engine/src/hy4flash/metal/hy4_metal_vision.h:91-125`）。

画像サイズの上限は `--vision` ではなく別 option `--image-max-pixels` で指定され、既定値は 4,194,304 pixels。server でも通常実行でも画像前処理に渡される（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1498-1502,1600-1602,1640-1642,1687-1690`）。Vision shard のパス自体に対する parser 側の canonicalize、相対パス基準の固定、書き込みは確認できない。読み込み先や kernel ファイル探索を含む実行環境依存の詳細は、指定パスと実行時の file system による。

## 出力とエラー

通常実行では画像準備失敗は `image: ...`、Vision shard の probe・kernel compile・mmap・encoder setup 失敗は `images: ...` を stderr に出し、いずれも終了コード `1`。`--vision` の値が不正でも画像がない場合はこの実行経路で検査されない。server では不正 shard の検出だけでは起動を中止せず、画像要求時にプロトコル上の `ERR image: ...` として表面化する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1687-1697,1776-1780`、`engine/src/hy4flash/metal/hy4_metal_serve.h:296-303,327-344,366-372`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1498-1506,1600-1608` — 値の格納、parser、未知引数経路。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1674` — `--load-only` の早期終了と server 設定への転送。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1682-1699,1773-1782` — オフライン画像準備、必須条件、Vision shard encode と失敗経路。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:292-304,320-374` — server の起動時 probe、画像要求時の判定・ロード。
- `engine/src/hy4flash/run/hy4_vision.h:67-124,258-310` — shard 検査と画像ファイル処理、placeholder 展開。
- `engine/src/hy4flash/metal/hy4_metal_vision.h:91-126` — shard map、kernel compile、Metal buffer 化。
- `docs/cli/README.md:1358-1361`、`docs/cli/000_cli_tools.md:11` — tool ID、Metal command path、parser の所在とスコープ。
