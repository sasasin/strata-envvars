# `VISION`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Docker コンテナの初回セットアップ時に、画像入力用エンコーダーを使うか、そのエンコーダーを GPU と CPU のどちらで実行するかを選ぶ環境変数。Strata が環境変数 `VISION` を直接読むのは `docker-entrypoint.sh` であり、通常の `setup.py` は環境変数ではなく `--vision` 引数を処理する。entrypoint が値を `setup.py --setup --yes` に渡し、セットアップ結果を `/data/config/strata-<family>-<model>.json` に保存する（`docker-entrypoint.sh:19-35,65-88`）。

## 値と判定

entrypoint はシェルの `${VISION:-no}` を使うため、環境変数が未設定または空文字なら `no` に置き換える。大文字小文字の変換や trim は行わず、それ以外の値はそのまま `--vision` に渡す。`setup.py` の argparse は `yes`, `no`, `none`, `gpu`, `cpu` のみ受け付ける。したがって `YES`、空白付きの値、その他の文字列はセットアップ時に無効な選択肢となる（`docker-entrypoint.sh:23,76-78`; `setup.py:4842-4843`）。

| 値 | NVIDIA / 通常経路 | AMD HIP 経路 |
| --- | --- | --- |
| 未設定、空文字、`no`、`none` | 画像を無効化 | 画像を無効化 |
| `yes`、`gpu` | GPU エンコーダーを選択（`yes` は `gpu` に正規化） | GPU 用画像エンコーダー未対応の警告を出し、画像を無効化 |
| `cpu` | CPU エンコーダーを選択 | Linux では CPU エンコーダーを選択。Windows では未対応の警告を出して無効化 |
| 上記以外 | argparse が選択肢エラー | argparse が選択肢エラー |

通常経路で `--vision` が省略されると対話プロンプトになるが、Docker entrypoint は常に値を渡すため、この環境変数を通す場合は省略時の対話選択にはならない（`setup.py:5362-5375`）。

## 有効になる条件

- 値がセットアップに渡るのは、モデル用設定がまだない場合か、`REINSTALL=1` の場合だけ。既存設定を再利用するときは entrypoint が `setup.py` を呼ばず、現在の `VISION` 値は無視される。`CONFIG` が設定されている場合も既存の指定ファイルをリンクしてセットアップを行わない（`docker-entrypoint.sh:57-70,89-94`）。画像設定を既存モデルで変更するには `REINSTALL=1` が必要（`docker-entrypoint.sh:46-48`; `docs/INSTALL.md:103-110`）。
- モデル定義が `vision: false` の場合は選択値にかかわらず `none` になり、`no` / `none` 以外なら `images are not available with <model> yet: off` の警告が出る（`setup.py:5362-5365`）。
- HIP の `yes` / `gpu` は GPU エンコーダーを有効にしない。`the AMD backend has no GPU image encoder yet: images off` と警告し、Linux では CPU を使う方法を案内する。`cpu` は Linux のみ対応し、Windows では `images on the CPU with an AMD card are Linux-only for now ...: images off` と警告する（`setup.py:2688-2698`）。
- 選択した GPU 用エンジンに画像エンコーダー実行ファイルがない場合、setup は警告してビルド経路へ進む（`setup.py:5496-5504`）。CUDA 用は選択が `gpu` か `cpu` かに応じて `STRATA_VISION_CUDA` を `ON` / `OFF` にして画像ツールをビルドする。HIP で CPU を選んだ場合は CUDA 無効で `tools/vision` をビルドする（`setup.py:2701-2711,3434-3446`）。
- `BUILD_VISION` は Docker イメージのビルド時に使う別の build arg であり、実行時の `VISION` と同じ設定ではない。Dockerfile は `BUILD_VISION=1` の場合 GPU 用画像ツールをビルドし、`0` なら vision を `none` としてビルドする（`Dockerfile:58-60,77-87`）。

## 実行時の詳細

有効な画像モードでは、setup は画像エンコーダーのモデルファイルを確認し、なければダウンロードする。GPU モードは設定の `args` に `--vision` と VRAM 予約量を加える。生成する設定の `vision` ブロックにはエンコーダー実行ファイル、画像モデル、対象モデル、GPU 実行かどうか、画像トークン上限が入り、CPU モードではスレッド数も記録される。無効モードではこのブロックを作らず、`images: off` と表示する。画像を有効にした場合は `images: on` または `images: on (encoder on the CPU)` と表示される（`setup.py:5375,5552-5563,5695-5707,5792-5800`）。

その設定を使ったサーバー起動時、`serve/server.py` は `vision` ブロックがある場合に画像エンコーダーを作成し、`loading the vision encoder ...` と表示する。したがって、この環境変数は各リクエストで読み直される実行時トグルではなく、セットアップで保存されたモデル設定を通して画像機能に反映される（`serve/server.py:6375-6393`）。

Docker entrypoint では初回セットアップ後、または再インストール後に作られた設定を起動に使う。後続起動で設定を再利用する場合、`VISION` を変更しても保存済みの設定内容は変化しない（`docker-entrypoint.sh:65-106`）。

## 根拠

- 環境変数の既定値と `--vision` への転送: `docker-entrypoint.sh:19-35,65-88`
- 再セットアップ条件と既存設定の再利用: `docker-entrypoint.sh:46-70,89-106`
- CLI 値、モデル可否、backend 別の解釈: `setup.py:2688-2698,4842-4843,5362-5378`
- エンコーダーの取得、ビルド、実行設定への保存: `setup.py:2701-2711,3434-3446,5496-5504,5552-5563,5695-5707,5792-5800`
- 保存された設定からのエンコーダー起動: `serve/server.py:6375-6393`
- 実行時設定の概要と `BUILD_VISION` の区別: `docs/INSTALL.md:99-110`, `Dockerfile:58-60,77-87`
