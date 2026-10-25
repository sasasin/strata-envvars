# `--vision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、`update.sh`、`UPDATE.bat` が委譲） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | `yes`、`no`、`none`、`gpu`、`cpu`（値必須）。macOS の Metal 用 parser は `none` を受理せず、`yes`、`no`、`gpu`、`cpu`。 |

## 役割

モデル設定時に画像入力を有効化するか、画像 encoder を GPU と CPU のどちらで動かすかを選びます。通常の PC 向け parser は `setup.py` の `argparse` にあり、初期設定または `--setup` による設定変更で使います（`setup.py:8439-8441`、`setup.py:8418-8420`）。

既存モデルをただ起動する場合、`--vision` だけでは設定変更になりません。既存設定があると通常起動経路になり、`--vision` はその条件判定に含まれないためです。設定を変える例は `./setup.sh --setup --vision cpu`、Windows では `START-HERE.bat --setup --vision gpu` です（`setup.py:8602-8607`、`setup.py:8617-8620`）。`--update` は既存設定や engine の更新処理へ早期に進み、`--vision` を使った設定変更は行いません（`setup.py:8617-8619`、`setup.py:6682-6709`）。

## 値と既定値

- `yes`: その backend の推奨 reader を選びます。NVIDIA 系の通常経路では VRAM が 23.5 GiB 未満なら CPU、23.5 GiB 以上または VRAM 不明なら GPU です（`setup.py:3131-3147`）。AMD は `strata_control.vision_reader.wanted()` に選択を委ねます（`setup.py:4568-4574`、`strata_control/vision_reader.py:36-63`）。
- `gpu` / `cpu`: 指定した reader を選びます。NVIDIA 系では小容量 VRAM でも `gpu` は保持され、VRAM を expert 用に使えなくなる旨を警告します（`setup.py:3136-3147`）。AMD は engine に reader があるかを後段で照合し、利用できる reader に決めます（`setup.py:4592-4597`）。
- `no` / `none`: 画像を無効にします。通常 PC の共通 parser は両方を受理します。Intel SYCL の委譲先でも両方が無効値として扱われます（`setup.py:8439-8441`、`strata_control/vision_reader.py:56-63`、`sycl/setup_intel.py:161-170`）。
- 省略時: 通常の対応モデルでは対話質問を表示し、Enter の既定回答は画像対応モデルで「有効」です。`--yes` を付けるとこの推奨回答を採用します。対応しないモデルでは既定が「無効」です（`setup.py:3120-3128`、`setup.py:9130-9133`、`setup.py:850-865`）。

通常 PC の parser は選択肢以外の値を拒否します。`--vision` 自体に数値範囲などの追加 validation はありません（`setup.py:8439-8441`、`setup.py:8553-8568`）。

## 実行時の動作

画像対応が選ばれると、setup は encoder ファイル（`mmproj`）を所定のモデルディレクトリから探し、なければダウンロードします。checksum が定義された family では取得後に検証します。GPU reader の通常設定は画像 token 上限 1024・VRAM reserve 700 MiB、CPU reader は上限 300・reserve 0 MiB です（`setup.py:796-799`、`setup.py:9325-9339`）。GPU encoder を選んだときは engine 引数へ `--vision` と必要な reserve 値を追加し、run config の `vision` セクションに reader、encoder、モデル、GPU/CPU の別を保存します（`setup.py:9521-9535`、`setup.py:9697-9707`）。CPU モードでは thread 数も config に書かれます（同 `setup.py:9703-9707`）。

- モデルが画像非対応として定義されている場合は強制的に無効化し、`yes` / `gpu` / `cpu` など有効化指定があれば警告します（`setup.py:9108-9111`）。
- Qwen3.6 の preview family はまだ起動設定を作りません。`--vision yes|gpu|cpu` の場合は encoder もダウンロードしますが、モデルファイルを取得した後「この版では実行できない」と表示して終了します（`setup.py:8161-8164`、`setup.py:8183-8199`、`setup.py:8200-8204`）。
- DeepSeek-V4.1 の専用 setup は `--vision` を config に反映しません。専用分岐では `args` と一般設定を作成して保存するだけで、`vision` の読出し箇所がありません（`setup.py:8127-8148`、`setup.py:8932-8937`）。この family で指定しても画像を有効化する効果は確認できません。
- Intel Arc の `--backend sycl` は `sycl/setup_intel.py` へ引数を渡します。既定 reader は CPU、`--vision gpu` は SYCL reader のビルドを試み、使えない場合は CPU reader を残す経路です（`setup.py:8561-8564`、`setup.py:7318-7330`、`sycl/setup_intel.py:14-18`、`sycl/setup_intel.py:161-170`、`sycl/setup_intel.py:218-224`）。
- macOS の標準経路は共通 parser を通らず Metal 用 setup に委譲します。そこで `yes` は Metal GPU reader、`cpu` は CPU reader（大幅に遅い旨を警告）、省略時は質問して既定で有効にします（`setup.py:8418-8419`、`metal/setup_mac.py:353-362`、`metal/setup_mac.py:404-410`）。

## 適用条件と副作用

画像を有効にした通常 setup は encoder の取得に伴う通信・ディスク使用を生じ、engine と config を画像対応にします。既存 config を再生成する場合、変更前 config を `.bak` に保存しようとします。保存に失敗すれば警告して続行します（`setup.py:9329-9335`、`setup.py:6312-6340`）。無効指定なら新しい config に vision 設定を含めません。`--vision-tokens` だけ指定されて画像が無効なら、その値は使われないと警告されます（`setup.py:9708-9709`）。

GPU reader は画像 encoder 用に VRAM を使い、GPU が 12.5 GiB 以下で reserve を明示していない場合は追加 reserve の案内を表示します。小容量 GPU でも `--vision gpu` は拒否されず、VRAM 不足の可能性を警告するだけです（`setup.py:9521-9535`）。AMD では engine フォルダ内の HIP reader、または CPU reader の有無・対応状況により画像が無効化されることがあります（`setup.py:4568-4597`）。

## 出力とエラー

- 値の省略または選択肢外の値は `argparse` の使用法エラーになります。通常 parser の `--vision` に独自の失敗メッセージや独自 validation はありません（`setup.py:8439-8441`、`setup.py:8553-8554`）。
- `--vision` で画像対応にしたとき encoder の取得・検証に失敗すれば setup は通常のダウンロード／検証失敗経路で停止します。`--gguf-dir` を指定した own-path family で encoder が無い場合は、不足ファイル名と配置先を示して停止します（`setup.py:9329-9335`、`setup.py:7650-7658`）。
- encoder を持たない engine では警告後に画像を無効化します。通常 family では「再度 `--build` で compile」と案内し、Control mode では component に encoder がない旨を表示します（`setup.py:7630-7634`、`setup.py:7375-7380`）。
- setup は状態メッセージを `say()` / `warn()` で表示します。明示的な `fail()` は setup 停止メッセージを出して終了コード 1 を使い、parser の usage error は `argparse` が処理します（`setup.py:817-829`）。

## 根拠

- parser と platform 委譲: `setup.py:8412-8445`、`setup.py:8553-8568`、`metal/setup_mac.py:353-362`。
- 既存モデル起動・update 分岐: `setup.py:8602-8620`、`setup.py:6682-6709`。
- reader 選択とモデル適用: `setup.py:3120-3147`、`setup.py:9108-9133`、`setup.py:9521-9535`、`setup.py:9697-9709`。
- encoder の取得と保存: `setup.py:9325-9339`、`setup.py:6312-6347`。
- family 固有経路: `setup.py:7442-7468`、`setup.py:8161-8204`、`setup.py:8127-8148`、`sycl/setup_intel.py:14-18`、`sycl/setup_intel.py:161-170`、`sycl/setup_intel.py:218-224`。

同一 revision の CLI `--help` は実行していません。`setup.py` の `main()` は argument parse より先にユーザーファイル引継ぎ処理を呼ぶため、help 起動も状態変更の可能性を避けてソース調査に限定しました（`setup.py:8412-8420`）。
