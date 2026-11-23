# `strata-vision --mmproj`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision` / `strata-vision-hip` / `strata-vision-sycl` |
| オプション | `--mmproj` |
| 別名 | なし |
| 値 | vision encoder と projector を含む GGUF ファイルのパス。1 個の引数を取る |

## 役割

画像 encoder プロセスが読む mmproj GGUF のパスを指定します。指定ファイルから vision tower の構造を読み取り、CPU または選択された GPU reader を初期化します。通常は server が設定内の `mmproj` パスをこのオプションに渡して reader を起動します。

## 使い方

```sh
strata-vision --mmproj /models/mmproj-F16.gguf
```

server が reader を起動するときは、設定の `mmproj` 値を絶対パス化して `--mmproj` に渡し、続けて `--model` などを指定します。`--model` は現行 own reader では値を読み捨て、mmproj とテキストモデルの対応確認には使いません。

## 値と既定値

- `--mmproj` の直後の引数をパス文字列として受け取ります。正規化や存在確認は parser では行わず、GGUF reader がファイルを開く段階で検査します。
- 省略時、または空文字列を指定した場合、usage を stderr に出して終了コード `2` で終了します。オプションの値自体が欠けている場合は `--mmproj needs a value` を stderr に出して終了コード `2` です。
- 同じオプションを複数回指定した場合は、後の値で上書きされます。
- 別名と既定パスはありません。

## 実行時の動作

parser は値を `OwnReaderOptions.mmproj` に格納し、起動後に `Gguf::open` へ渡します。ファイルを開けない場合、GGUF magic や version が不正な場合、vision encoder の必須 metadata がない場合、または必要な tensor の形状が reader の期待と合わない場合は初期化失敗になります。geometry の読み取りでは `general.architecture` が `clip` であること、`clip.has_vision_encoder` と projector 情報などを確認します。

初期化に成功すると stdout に `READY <出力次元> own` を出し、stdin から画像 encode 要求を受け付けます。server 経由の起動では設定の `mmproj` がこの引数に渡されます。reader は mmproj から得た vision embedding を作る役割で、画像 embedding のモデル側への配置は engine 側です。

## 適用条件と副作用

- `strata-vision`、`strata-vision-hip`、`strata-vision-sycl` は同じ `terminal/tools/vision/strata_vision.cpp` の parser を使います。実行バイナリの build/backend と `--gpu` の組み合わせにより、reader 初期化時に利用できる GPU 経路は異なります。
- `--model` は受理されても現行 parser では値を読み捨てます。そのため、このプロセス自身は指定モデルとの組み合わせを検証しません。
- `--gpu` がない場合、CUDA/HIP device visibility を無効にする環境変数をプロセス内で設定してから reader を起動します。POSIX の Windows/macOS 以外では、`STRATA_READ_AHEAD` が未設定または数値 0 以外のとき、mmproj ファイルに対して OS の先読み advisory を行います。ファイルを変更する処理ではありません。
- 起動に成功すると reader は常駐します。後続の `ENC` 要求に応じて画像を読み込み、指定された出力パスにバイナリ embedding を書き込みます。これは `--mmproj` 単独のファイル副作用ではなく、reader protocol の動作です。

## 出力とエラー

- mmproj を指定しない・値を欠く場合は stderr に usage または値不足を出し、終了コード `2` です。
- ファイルを開けない、GGUF でない、対応外 version、または reader が要求する encoder metadata / tensor 構造を満たさない場合、stdout に `ERR cannot load the vision encoder <path> (<理由>)` を出し、終了コード `1` で終了します。
- 正常に初期化した場合は stdout に `READY <次元> own`、初期化の詳細（tower、ロード時間、CPU/GPU 等）は stderr に出します。
- server は起動時の stdout `ERR` を reader の開始失敗として扱い、ログと終了状態を使ってエラーを報告します。

## 根拠

- `terminal/tools/vision/strata_vision.cpp:36-36` — 共通 CLI entry point。
- `terminal/tools/vision/strata_vision.cpp:61-95` — `--mmproj` parser、値不足、必須指定の判定。
- `terminal/tools/vision/strata_vision.cpp:97-107` — `--gpu` 省略時の device visibility 設定。
- `terminal/tools/vision/strata_vision.cpp:127-140` — 条件付き read-ahead と mmproj を reader に渡す処理。
- `terminal/tools/vision/own/own_reader.h:14-20` — `mmproj` の格納先と reader option の既定値。
- `terminal/tools/vision/own/own_reader.cpp:42-59` — GGUF の読込と、失敗時の stdout `ERR`・終了コード。
- `terminal/tools/vision/own/gguf_lite.cpp:107-130` — ファイル open、最小サイズ、magic、version 等の検査。
- `terminal/tools/vision/own/vit_geometry.cpp:37-48` — CLIP architecture、vision encoder、projector、必須 geometry metadata の検査。
- `terminal/tools/vision/own/own_reader.cpp:80-94,120-121` — CPU reader の初期化・詳細ログ・成功時 `READY`。
- `terminal/serve/server.py:3016-3029` — server が設定の mmproj を絶対パス化して `--mmproj` に渡す箇所。
- `terminal/serve/server.py:3156-3174` — server が reader の stdout `READY` / `ERR` を開始応答として扱う箇所。
