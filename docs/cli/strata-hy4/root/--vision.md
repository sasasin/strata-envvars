# `strata-hy4 --vision`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP ルート） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | Vision shard の `.strata` ファイルパスを1つ取る |

## 役割

Hy4-Flash の画像入力に使う Vision shard を指定する。serve モードでは起動時に shard の形式を検査して画像対応可否を通知し、実際の重み読み込みと画像エンコードは画像を含む最初のリクエストまで遅延する。オフライン実行では `--image` と画像 placeholder token を含む `--tokens` と組み合わせる。

## 使い方

```sh
# 画像入力に対応した serve エンジンを起動
strata-hy4 --serve --model SQ64.strata --engram Engram-Q8.strata --vision Hy4-Flash-Vision.strata

# offline 実行で画像を含む token 列を処理
strata-hy4 --model SQ64.strata --engram Engram-Q8.strata --tokens prompt-ids.txt --image photo.jpg --vision Hy4-Flash-Vision.strata --gen 128

# モデル情報と Vision shard の利用可否を調べる（GPU 不要）
strata-hy4 --info SQ64.strata --vision Hy4-Flash-Vision.strata
```

## 値と既定値

- 値は `nxt()` で次の argv 要素からそのまま文字列として読み込み、`vision_path` に格納する。値の形式やファイルの存在確認は parser 時点では行わない。別名はない（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-384,448`）。
- 未指定時は空文字列。明示した値を使う。複数回指定した場合は parser が同じ変数へ順に代入するため最後の値が残る（同 `:347,448`）。
- オプションの直後に値がない場合、`nxt()` は stdout に `ERR --vision needs a value` を出して終了コード 2 で終了する（同 `:377-383,448`）。値の範囲 validation はない。

## 実行時の動作

- **serve**: `--vision` の値は `ServeOpts::vision` に渡される（`engine/src/hy4flash/run/hy4_main.hip.cpp:555-572`）。serve 起動時に `vision_probe()` で shard を確認し、成功時に `INFO ... images=1`、未指定または検査失敗時に `images=0` として `READY` を返す。検査失敗は stderr の `[vision] disabled: ...` で通知するが、serve 自体は画像なしで起動を続ける（`engine/src/hy4flash/run/hy4_serve.hip.h:355-371`）。
- serve で画像を含むリクエストを受けると、画像対応が無効ならプロトコル応答 `ERR image: this engine was started without the Vision shard ...` を返す。対応が有効なら画像を準備し、初回の画像リクエスト時に `venc.load(o.vision, ...)` で shard を読み込んでエンコードする。画像ファイル・placeholder の不整合や読み込み失敗は `ERR image: ...` になる（`engine/src/hy4flash/run/hy4_serve.hip.h:389-413,431-445`）。
- **オフライン実行**: `--image` ごとに画像を準備し、`--tokens` の画像 placeholder を画像領域に展開する。画像を指定したのに `--vision` が空なら stderr に `image: --vision FILE is required with --image` を出して終了コード 1。shard 読み込みまたは encoder setup の失敗も stderr の `images: ...` と終了コード 1 になる（`engine/src/hy4flash/run/hy4_main.hip.cpp:666-685,718-729`）。
- Vision shard が有効な場合、メモリ計画にもその存在を反映する。CUDA/HIP のserveでは、`--vision` のパスが空でないかを `has_vision` として渡し、RAM 予算に Vision 用の追加分を見込む。オフライン経路でも同様に shard パスの空非空を GPU メモリ計画へ渡す。したがって、パスが指定されていれば shard が後で読み込み失敗する場合でも計画上は Vision 使用ありとして扱われる（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-652`; `engine/src/hy4flash/run/hy4_serve.hip.h:270-291`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-438,809-821`）。
- `--info MODEL --vision FILE` では、Vision shard の検査結果を `images=1|0` として出力する。検査失敗時は stderr に `vision shard: ...` を出すが、モデル情報の分岐自体は戻り値 0 で終わる（`engine/src/hy4flash/run/hy4_main.hip.cpp:52-86`）。

## 適用条件と副作用

- 対象は索引上の CUDA/HIP `strata-hy4` ルートである。Metal と SYCL は別 parser scope のため、この文書の範囲外（`docs/cli/README.md:1277-1281,1355-1358`; `docs/cli/000_cli_tools.md:11`）。
- shard 検証は `vision_probe()` が行い、Strata file を開けること、profile が `VisionShard` であること、manifest/config・tensor dtype・必要 tensor 群がサポート範囲内であることを確認する（`engine/src/hy4flash/run/hy4_vision.h:67-124`）。serve では不適合 shard は画像機能を無効にするが、offline の画像実行では encoder load/setup 失敗となる。
- serve は起動時に重み全体を読み込まず、画像リクエスト時に約 1.25 GiB を vision weights と encode scratch 用に空ける処理を行う。GPU 条件や CPU fallback によって、エンコード直後に重みを unload する（`engine/src/hy4flash/run/hy4_serve.hip.h:431-450`）。
- 値が指定されても画像リクエストがなければ、serve では shard の形式 probe のみが行われ、遅延ロードは発生しない。パス指定だけで shard をダウンロード・生成する処理は確認できない。

## 根拠

- `docs/cli/README.md:1277-1281,1355` — ツール区分、コマンド階層、対象リンク。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:347-384,448` — 値の受け取り・既定状態・値省略時の処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:555-572,648-652` — serve 設定への受け渡しとオフラインのメモリ計画。
- `engine/src/hy4flash/run/hy4_serve.hip.h:355-371,389-445` — 起動時 probe、画像要求時の拒否・遅延ロード・エラー応答。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:666-685,718-729` — offline の画像入力条件、展開、Vision encoder 実行と失敗経路。
- `engine/src/hy4flash/run/hy4_vision.h:67-124` — shard の profile、manifest、dtype、tensor 検証。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-438,545-559,805-821` — GPU/RAM メモリ計画への Vision 追加分。

調査開始時の Strata checkout は `## main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。`--help` は実行していません。
