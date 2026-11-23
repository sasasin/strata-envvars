# `--vision`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | Mac 用 `setup_mac.py`（`setup.py` が Apple Silicon で委譲） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | `yes`、`no`、`gpu`、`cpu` |

## 役割

Mac 用セットアップで、モデルに画像を読ませる画像エンコーダーを有効にするか、Metal GPU と CPU のどちらで実行するかを指定します。これは `source-setup/root/--vision.md` の同名オプションとは別スコープで、Mac 用 parser の値と処理を記載しています。

## 使い方

```sh
# 画像読み取りを有効にし、GPU を使う
./setup.sh --setup --vision gpu

# 画像読み取りを無効にする
./setup.sh --setup --vision no

# 画像読み取りを有効にし、CPU を使う
./setup.sh --setup --vision cpu
```

`setup.py` は Apple Silicon の Mac で `engine/metal/setup_mac.py` に引数を渡します。`--setup` を付けず、既存の設定があり、モデル指定・確認・更新・再 build などの操作もない場合は既存モデルを起動する早期経路に入り、`--vision` の値はその設定に反映されません。

## 値と既定値

- parser は `yes`、`no`、`gpu`、`cpu` 以外を拒否します。省略時の parser 値は `None` です。
- セットアップがモデル選択後まで進むと、未指定の場合は「画像を読み取るか」の質問が出ます。質問の既定回答は yes です。`--yes` も指定されている場合、この既定回答が選ばれます。
- `yes` と `gpu` は画像読み取りを有効にし、GPU 使用として設定します。`cpu` は有効にし、CPU 使用として設定します。`no` は無効にします。
- 値は `argparse` の `choices` で検証されます。整数範囲などの追加検証はありません。

## 実行時の動作

選択結果はセットアップ内で `no` または有効状態の `yes` に正規化され、`cpu` の場合だけ GPU フラグが false になります。有効時はモデルの画像 encoder projector（mmproj）が未取得ならダウンロードされ、Metal 版 `strata-vision` が既存かつソース stamp が現行でなければビルドされます。生成するモデル設定にはエンジン引数 `--vision` と、reader の実行ファイル・mmproj・モデル・GPU 使用有無・最大 token 数 1024 を記録します。`gpu` は `yes` と同じ GPU 設定です。

無効時は mmproj の取得・画像 reader の build を行わず、生成設定にも vision セクションを追加しません。設定を書いた後、通常はサーバー起動へ進みますが、`--no-start` なら起動せず終了します。

## 適用条件と副作用

- この parser は Apple Silicon / Metal 用です。共通 `setup.py` は通常の macOS 経路を `setup_mac.py` に委譲し、Mac 実装が Apple Silicon の環境確認を行います。
- `--vision` だけを指定しても既存設定がある場合は早期の起動経路になり得るため、設定変更を意図する場合は `--setup` などセットアップ経路を明示してください。
- 有効時にはネットワークから mmproj を取得する場合があり、画像 reader の build では `build-vision/` 配下に生成物、`build-vision.log`、`BUILD.json` が作られます。セットアップはモデル設定ファイルと起動スクリプトも生成・更新します。
- `cpu` は同じ Metal 対応 `strata-vision` を GPU 指定なしで使う設定です。ソース内の注記は Mac の CPU 読み取りを GPU 読み取りより大幅に遅いものとして説明し、CPU 選択時に警告を出します。
- `--update` 経路では通常のモデル取得・設定生成より前に終了します。画像 encoder が既にない場合は警告して `--setup` を案内します。

## 出力とエラー

- `cpu` を選ぶと CPU reader の速度に関する警告を表示します。
- 無効な値は `argparse` が usage とエラーを表示して拒否します。
- reader の build に失敗すると、ログ `engine/metal/build-vision.log` を案内するエラーで停止します。mmproj の取得・検証失敗も共通 downloader / SHA 検証の失敗経路になります。
- Mac の事前確認に失敗した場合は最初の問題をエラーとして停止します。これは `--vision` 固有の validation ではありません。

## 根拠

- `engine/metal/setup_mac.py:1-16` — Mac 向け CLI の役割、共通処理を `setup.py` に委ねる範囲。
- `terminal/setup.py:9205-9210` — Mac 用スクリプトへの引数付き委譲。
- `terminal/setup.py:11216-11220` — macOS で Mac 実装へ振り分ける条件（Control / Hy4 / Inkling 経路を除く）。
- `engine/metal/setup_mac.py:375-405` — parser 定義、許容値、未知引数の警告。
- `engine/metal/setup_mac.py:416-418` — 既存設定時に通常起動へ進む早期経路。
- `engine/metal/setup_mac.py:429-432` — `--check` の早期終了と Mac 要件エラー。
- `engine/metal/setup_mac.py:451-457` — 省略時の質問と既定回答、値の正規化、CPU/GPU 選択。
- `engine/metal/setup_mac.py:515-524` — 有効時の mmproj 取得、検証、encoder build。
- `engine/metal/setup_mac.py:593-621` — 設定への反映、ファイル生成、`--no-start` と通常起動。
- `engine/metal/setup_mac.py:169-193` — Metal 版 reader の既存 build 判定、build log、失敗処理。
- `terminal/strata_control/vision_reader.py:102-113` — Mac reader の GPU/CPU 実行モードと CPU 時の注記。
