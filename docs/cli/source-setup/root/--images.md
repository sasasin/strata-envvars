# `--images`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`update.sh` 等から委譲） |
| オプション | `--images` |
| 別名 | なし |
| 値 | `qwen-image` または `no` |
| 既定値 | 未指定（`None`）。未指定時は画像生成の setup 処理を呼ばない |

## 役割

ソース checkout の setup で、Qwen-Image-2.1-Turbo による画像**生成**機能をモデルの実行設定へ追加するか、設定から外すかを指定します。これはチャットで画像を読み取る `--vision` とは別の機能です（`setup.py:9090-9098`; [`docs/IMAGES.md`](https://github.com/Niko1221/Strata/blob/c62d5e3a15b40ea51c96aae9e8d36928965f53ab/docs/IMAGES.md)）。

## 使い方

```sh
./setup.sh --setup --images qwen-image
```

画像生成を設定から外す場合:

```sh
./setup.sh --setup --images no
```

`setup.sh` は引数を `setup.py` に渡し、`update.sh` も `--update` を加えて `setup.sh` を実行します（`setup.sh:9-13`; `update.sh:62`）。Windows の `START-HERE.bat` も setup.py に委譲します（`START-HERE.bat:48-53`）。

## 値と既定値

- `argparse` の `choices` は `qwen-image` と `no` です。値の省略やそれ以外の値は parser の引数エラーになります（`setup.py:9096-9098`）。
- この parser に明示的な `default` はなく、未指定では `a.images` は未設定値です。通常 setup は `a.images` が truthy の場合だけ `setup_images()` を呼びます（`setup.py:9097-9098,10434-10435`）。
- `qwen-image` では denoiser の量子化や backend は別 option が未指定なら GPU と VRAM 等から選ばれます。関連する `--image-quant`、`--image-backend`、`--image-gpu-policy`、`--image-native` は同じ parser に定義されています（`setup.py:9099-9106,5065-5077`）。

## 実行時の動作

- `--images qwen-image` は、選ばれた backend と量子化を表示し、モデルファイルをダウンロードして画像生成を設定するか確認します。確認に「いいえ」と答えると設定生成を中止し、`None` を返します。`--yes` を付けたときの確認応答は `ask()` の共通動作に従います（`setup.py:5080-5091`）。
- 承諾すると models directory を作成し、必要容量（3ファイルの合計 + 5 GB）に満たない空き容量なら警告します。その後 stable-diffusion.cpp の `sd-cli` を backend 向けにビルドし、選んだ denoiser、VAE、Qwen3-VL text encoder を取得して SHA-256 を検証します（`setup.py:5092-5104,5004-5061`; `tools/image/qimage.py:24-55,107-114`）。
- 成功すると実行設定の `images` セクションに、実行ファイル、backend、quant、各モデルのパス、GPU policy 等を記録します。サーバーはこれを画像生成 API で使います（`tools/image/qimage.py:190-203`; `setup.py:10434-10435,10453,10474-10475`）。実装文書では API を `POST /v1/images/generations` としています（`docs/IMAGES.md:3-5,29-40`）。
- `--images no` は `setup_images()` が `None` を返し、設定書き込み直前に `images` キーを削除します。既存設定が変更される場合、setup は旧ファイルを `.bak` にコピーしてから新しい設定を書きます（`setup.py:5080-5084,6666-6676`）。
- `--images` を省略した場合は `setup_images()` を呼びません。再 setup 時は `images` が setup 管理キーに含まれないため、既存設定にある同キーは引き継がれます。初回 setup では引き継ぎ元がないため生成されません（`setup.py:6502-6503,6513-6524,10434-10435`）。

## 適用条件と副作用

- `--images` は「画像を読む」設定ではありません。画像読み取りは `--vision` 側の設定です（`setup.py:9090-9098`; `docs/IMAGES.md:3-5`）。
- `qwen-image` は安定拡散系エンジンのコンパイル、ネットワークからのソース／モデル取得、ファイル作成を伴います。CUDA backend には CUDA Toolkit の `nvcc` が必要で、Vulkan では環境によって Vulkan SDK が必要です（`setup.py:4937-4956,4963-4990,5021-5058`）。
- モデルは Qwen Research License の対象です。setup はライセンス確認を促す文言を表示します。商用利用前にライセンスを確認してください（`setup.py:5085-5089`; `tools/image/qimage.py:58-60`）。
- macOS の通常 source setup は argparse より前に `metal/setup_mac.py` に委譲し、macOS Control setup も別関数で終了するため、これらの経路では `setup_images()` を通りません（`setup.py:9068-9069,7703-7707,9220-9223,8859-8865,9030`）。委譲先 `metal/setup_mac.py` がこの引数をどう扱うかは本調査では追っていません。

## 出力と失敗

- backend / モデル量子化、ライセンス案内、確認プロンプト、完了時の API URL を表示します。`--images no` または確認を断った場合は `images` セクションを設定に残しません（`setup.py:5086-5104,6666-6667,10474-10475`）。
- 要求された backend の前提を満たさない場合、例えば CUDA 用 `nvcc` が見つからない場合や Windows で必要な Vulkan SDK がない場合は `fail()` 経路に入ります。ビルド後に `sd-cli` が存在しない場合もエラーになります（`setup.py:5021-5026,5038-5049,5052-5059`）。
- ダウンロードに失敗する場合や、取得ファイルが期待するサイズ・SHA-256 と一致しない場合は処理が失敗します（`setup.py:5095-5100`; `tools/image/qimage.py:43-55`）。エラーごとの終了コードや stderr 文言は、このオプションの呼び出し経路から一律には特定できないため記載していません。

## 根拠

- parser、非表示の help 設定、候補値: `setup.py:9096-9106`
- setup 本体からの呼び出しと設定への反映: `setup.py:10434-10435,10453,10474-10475`
- setup 処理、確認、ビルド・ダウンロード・検証: `setup.py:5004-5061,5065-5104`
- 設定の引き継ぎ・削除・backup: `setup.py:6502-6503,6513-6524,6648-6676`
- 生成モデル、保存パス、backend / quant の規則、ライセンス: `tools/image/qimage.py:1-15,37-71,88-114,190-203`
- wrapper の委譲: `setup.sh:9-13`, `update.sh:62`, `START-HERE.bat:48-53`
- platform 分岐: `setup.py:7703-7707,8859-8865,9030,9068-9069,9220-9225`
