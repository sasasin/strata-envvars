# `--mmproj`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision`（独立した画像 encoder CLI。Terminal CLI のサブコマンドではない） |
| オプション | `--mmproj` |
| 別名 | なし |
| 値 | encoder / projector を含む GGUF ファイルのパス。値は必須 |

## 役割

画像 encoder と projector の GGUF ファイルを指定します。`strata-vision` はこのファイルとテキストモデルを使って画像 embedding を作り、常駐中に受け取る画像処理要求へ応答します。画像 token をテキストモデル入力へ配置する処理は engine 側です（`tools/vision/strata_vision.cpp:1-5, 231-235`）。

## 使い方

モデルの先頭 GGUF shard と vision encoder ファイルを指定して起動します。

```sh
strata-vision --mmproj /models/mmproj.gguf --model /models/model-00001-of-00002.gguf
```

`--mmproj` と `--model` はどちらも必須です。画像要求は起動後に標準入力から受け取るため、この例だけでは対話入力・画像処理は始まりません（`tools/vision/strata_vision.cpp:7-8, 125-128, 283-295`）。

## 値と既定値

- 値を取るオプションで、次の argv 要素をそのままパス文字列として保存します。拡張子、ファイル形式、存在、読み取り権限は parser では検査しません（`tools/vision/strata_vision.cpp:93-100`）。
- 省略時は空文字列のままです。`--mmproj` または `--model` が空なら usage を stderr に出して終了コード 2 で終了します（`tools/vision/strata_vision.cpp:88-90, 125-128`）。
- オプションを値なしで末尾に置くと、`--mmproj needs a value` を stderr に出して終了コード 2 で終了します（`tools/vision/strata_vision.cpp:95-97`）。空文字列を値にした場合も必須値チェックにより usage 経路になります。
- 同じオプションを複数回指定すると、後の値が同じ変数を上書きします（`tools/vision/strata_vision.cpp:93-100`）。

## 実行時の動作

`--mmproj` のパスは、`mtmd_init_from_file(mmproj, text, cp)` に渡され、vision 対応 encoder context の初期化に使われます。続いて同じファイルから GGUF metadata の `clip.vision.projection_dim` を読み、encoder 出力幅を得ます（`tools/vision/strata_vision.cpp:231-248`）。

Linux など macOS・Windows 以外の環境では、`STRATA_READ_AHEAD` が未設定または整数として 0 以外の場合、初期化の前にこのパスを読み取り専用で開き、ファイルを 128 KiB 刻みで OS の先読み対象にします。open に失敗した場合はこの先読み処理を飛ばし、後続の encoder 初期化へ進みます（`tools/vision/strata_vision.cpp:195-207`）。この環境変数は先読みの条件だけに関与し、CLI parser の値検証ではありません。

`strata-vision` は起動時に encoder context をロードし、成功すると `READY <embedding幅>` を stdout に出します。その後、標準入力の `ENC <画像パス> <出力パス>` 要求を処理します。`--mmproj` 自体は要求単位で変更されず、終了するまでロード済み encoder が使われます（`tools/vision/strata_vision.cpp:231-238, 283-295`）。

## 適用条件と副作用

- `--mmproj` を使うには、実行ファイルが vision 対応でビルドされている必要があります。CMake の `strata-vision` target は `tools/vision/strata_vision.cpp` をビルドし、HIP / SYCL build では実行ファイル名をそれぞれ `strata-vision-hip` / `strata-vision-sycl` に変えますが、parser は共通です（`tools/vision/CMakeLists.txt:96-116`）。
- parser は値をパスとして検査せず、初期化処理がファイルを読み込みます。encoder をロードできない、または読み込んだ context が vision をサポートしない場合は stdout に `ERR cannot load the vision encoder <path>` を出して終了コード 1 になります（`tools/vision/strata_vision.cpp:231-235`）。
- ロード後に `clip.vision.projection_dim` がない、または 0 以下の場合は stdout に `ERR the vision encoder has no projection_dim` を出して終了コード 1 になります（`tools/vision/strata_vision.cpp:239-248`）。
- 起動時には encoder context とモデルをプロセス内に保持します。GPU build で `--gpu` も指定された場合は、`READY` 前に 2048×2048 の画像で encoder を warm-up します。`--gpu` なしの CPU 経路では warm-up しません（`tools/vision/strata_vision.cpp:249-285`）。
- `strata-vision` は独立した executable で、help option はありません。未知の引数は stderr に `unknown argument <引数>` を出し終了コード 2 です（`tools/vision/strata_vision.cpp:123`）。

## 出力とエラー

必須引数の不足は usage を stderr に出力し終了コード 2、mmproj のロードまたは metadata 検査の失敗は上記 `ERR` を stdout に出力し終了コード 1 です。標準出力は起動時の `READY` と、常駐 protocol の応答に使われます（`tools/vision/strata_vision.cpp:125-128, 231-248, 283-295`）。

mmproj のパス以外の具体的な GGUF 破損・互換性エラー文言は `strata-vision.cpp` 内で規定されていません。初期化時に依存ライブラリが出す詳細や個別の不正ファイルでの表示内容は、このソース確認だけでは特定できません。

## 根拠

- parser、必須値チェック、usage / unknown argument: `tools/vision/strata_vision.cpp:88-128`
- 先読みと mmproj のロード、vision 判定、metadata 読み込み: `tools/vision/strata_vision.cpp:195-248`
- encoder warm-up と常駐 protocol: `tools/vision/strata_vision.cpp:249-343`
- executable target と GPU variant 名: `tools/vision/CMakeLists.txt:96-116`
