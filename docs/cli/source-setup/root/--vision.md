# `setup.py` / `setup.sh` / `START-HERE.bat` `--vision`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（source setup） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | `yes`、`no`、`none`、`gpu`、`cpu` のいずれか。値が必須 |

## 役割

モデルセットアップ時に画像入力を有効にするか、画像 encoder を GPU または CPU のどちらで使うかを選ぶ。画像対応モデルで有効にすると、必要な Vision/mmproj ファイルを取得または既存ファイルから解決し、生成する設定に画像 reader の情報と `--vision` を反映する。実際の reader 選択・「画像 shard を含める」だけの扱いはモデル系統や OS/backend によって異なる。

## 使い方

```sh
# 画像を有効にし、カード容量に応じた reader を選ぶ
./setup.sh --setup --family qwen --model IQ3_S --vision yes

# GPU に余裕が少なくても、GPU reader を明示して使う
./setup.sh --setup --family qwen --model IQ3_S --vision gpu

# 画像入力を無効にしてモデルをセットアップする
./setup.sh --setup --family qwen --model IQ3_S --vision no
```

Windows では `START-HERE.bat` に同じ引数を渡す。値は `terminal/setup.py` の parser が処理する（`setup.sh` は `setup.py` に引数を転送する）。既存モデルの設定を変える場合は `--setup` と対象モデルを指定する。通常起動時に `--vision` だけ渡しても保存済み設定は変わらず、セットアップ時だけ適用される旨が警告される。

## 値と既定値

- `--vision` を省略した場合、画像対応モデルでは対話質問が出る。通常の Flash-Next 系では画像を既定で有効にし、`--yes` の非対話実行もその既定回答を使う。画像非対応モデルでは有効化されない。Qwen3.6 の own-path では既定回答は yes（`--yes` も yes）である。 ( `terminal/setup.py:4077-4082`, `terminal/setup.py:9634-9655`, `terminal/setup.py:11997-12010` )
- `yes` はカードに応じた reader を選ぶ。通常の NVIDIA/Flash-Next 系および Qwen3.6 own-path は、有効 VRAM が 23.5 GB 未満なら CPU、それ以上なら GPU を選ぶ。AMD では同じ方針で希望 reader を決めた後、利用可能な HIP/CPU reader に照合する。 ( `terminal/setup.py:4088-4105`, `terminal/setup.py:9656-9663`, `terminal/setup.py:5632-5638`, `terminal/setup.py:5655-5663` )
- `gpu` と `cpu` は reader を明示する。GPU 指定が小容量カードの VRAM を使う場合も値は維持され、警告が出る。AMD で HIP reader が使えない場合は CPU reader へ解決され得る。Mac では GPU が Metal reader に対応し、`cpu` は遅くなる注意を出すが選択は維持される。 ( `terminal/setup.py:4093-4105`, `terminal/setup.py:5655-5663`, `terminal/setup.py:10791-10807` )
- `no` と `none` は画像入力を無効にする。値の妥当性は `argparse` の choices で検査され、別の値は parser error になる。 ( `terminal/setup.py:11245-11247` )

## 実行時の動作

- 通常の対応モデルでは reader の選択後、必要な mmproj/Vision ファイルを既存の配置から解決し、見つからなければダウンロードする。ファイル検証対象のモデルではサイズ・SHA-256 も検査される。画像が有効なら生成設定に `--vision` と vision 設定（encoder executable、mmproj、モデル、GPU/CPU、token 上限）を記録し、CPU reader の場合は thread 数も記録する。 ( `terminal/setup.py:12200-12214`, `terminal/strata_control/setup_config.py:561-573` )
- 通常系で GPU reader を選ぶと、設定の engine 引数に encoder 用の VRAM reserve が加わる。明示した `--vram-reserve-mib` はこれを上書きできるが、encoder の必要量より小さければ警告される。12.5 GB 以下の GPU では reserve 指定がない場合に tip を表示する。 ( `terminal/strata_control/setup_config.py:350-368` )
- Qwen3.6 own-path は画像を既定で有効にし、`no`/`none` なら無効化する。画像非対応モデルで有効値を指定しても警告して無効化する。 ( `terminal/setup.py:9634-9663`, `terminal/setup.py:9920-9929` )
- Hy4-Flash と Inkling-2-Mini では、parser が受理する `yes`/`gpu`/`cpu` はいずれも「画像を含める」扱いになり、`no`/`none` だけが無効になる。Hy4 は Vision shard をダウンロード対象に含め、start config の engine 引数へ shard path を渡す。Inkling は Vision shard を取得またはローカルファイルから探し、見つからなければ警告して text-only にする。これらの経路で `gpu` と `cpu` が reader 実行場所を選ぶとは確認できない。 ( `terminal/setup.py:10196-10200`, `terminal/setup.py:10226-10229`, `terminal/setup.py:10269-10273`, `terminal/setup.py:10572-10575`, `terminal/setup.py:10603-10615`, `terminal/setup.py:10620-10623`, `terminal/setup.py:10651-10656`, `terminal/setup.py:10682-10684` )
- セットアップ設定の適用対象は、新規セットアップまたは `--setup` による再設定。既存モデルをセットアップせず通常起動する場合、`--vision` は保存済み設定を変えず、セットアップ時のみ適用されると警告する。 ( `terminal/setup.py:11474-11490`, `terminal/setup.py:11513-11518` )

## 適用条件と副作用

- 画像対応モデル・reader の有無に依存する。モデルが画像非対応なら無効扱いになる。Mac は `setup.py` から Metal 用セットアップへ分岐し、SYCL backend は別の setup 経路へ分岐するため、上記の通常系と同じ実装が全 platform/backend で共通とは限らない。 ( `terminal/setup.py:11407-11417`, `terminal/setup.py:10791-10817` )
- 有効時は encoder/Vision ファイルをダウンロードすることがあり、CPU/GPU reader の build または利用可能性確認もセットアップ処理に含まれ得る。GPU reader は VRAM を使用し、CPU 指定は画像処理が遅くなる旨をコードが案内する。 ( `terminal/setup.py:12203-12214`, `terminal/setup.py:5587-5593`, `terminal/setup.py:5666-5678`, `terminal/setup.py:10791-10807` )
- `--vision-tokens` は画像無効時に使われない旨が警告される。 ( `terminal/strata_control/setup_config.py:572-573`, `terminal/setup.py:9929-9930` )

## 出力とエラー

- 未対応値は `argparse` choices のエラーになる。`--vision-tokens` との組合せでは、画像が無効なモデルに対し同オプションを使わない旨の警告を出す。 ( `terminal/setup.py:11245-11247`, `terminal/setup.py:9929-9930` )
- 小容量 GPU への明示的な `gpu` 指定は拒否されず、VRAM 使用に関する警告を出して選択を維持する。AMD の reader 選択や Mac の engine reader が使えない場合は、警告して CPU reader または画像無効へ切り替わる場合がある。 ( `terminal/setup.py:4098-4105`, `terminal/setup.py:5655-5663`, `terminal/setup.py:10810-10817` )
- 画像ファイルの取得失敗、reader build の個々の終了コード・stderr の全経路はこの文書の調査範囲では網羅していない。

## 根拠

- `terminal/setup.py:11245-11247` — parser の受理値と help。
- `terminal/setup.py:4077-4105` — 省略時の画像既定値、VRAM 閾値、`yes` の reader 選択、`gpu` 指定時の警告。
- `terminal/setup.py:9634-9663` — Qwen3.6 own-path の有効化・reader 選択。
- `terminal/setup.py:11985-12013` — 通常系の非対応モデル、AMD、明示値・省略時の分岐。
- `terminal/setup.py:12200-12214` — encoder file 解決・download と CPU 指定時の案内。
- `terminal/strata_control/setup_config.py:350-368`, `terminal/strata_control/setup_config.py:561-573` — engine 引数の VRAM reserve と設定への vision セクション記録。
- `terminal/setup.py:10196-10229`, `terminal/setup.py:10269-10273`, `terminal/setup.py:10572-10623`, `terminal/setup.py:10682-10684` — Hy4/Inkling の画像 shard の扱い。
- `terminal/setup.py:11474-11490`, `terminal/setup.py:11513-11518` — セットアップ時のみ適用される条件と通常起動時の警告。
- `terminal/setup.py:11407-11417`, `terminal/setup.py:10791-10817`, `terminal/setup.py:5587-5593`, `terminal/setup.py:5655-5678` — platform/backend 分岐、Mac reader、AMD reader/build の条件。
