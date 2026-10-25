# `strata launch --vision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| option | `--vision` |
| 主な実装 | `strata_cli/launch/cmd.py`、`strata_cli/launch/runner.py`、`strata_control/vision_reader.py` |

## 概要

モデルの画像入力を有効にするか、画像 reader を CPU / GPU のどちらで動かすかを指定します。値は `off`、`on`、`gpu`、`cpu` です。たとえば `strata launch --model iq3_xxs --vision cpu --no-tui` は画像 reader に CPU を指定して起動します。

このオプションは `strata launch` 専用です。同じ `--vision` でも setup CLI やネイティブ engine の同名引数とは値と作用が異なります。

## 値、既定値、validation

| 値 | 意味 |
| --- | --- |
| `off` | 画像を無効にする。launch が setup に渡す値は `no`。 |
| `on` | 画像を有効にし、Strata の選択規則で reader を選ぶ。setup に渡す値は `yes`。 |
| `gpu` | GPU reader を指定する。 |
| `cpu` | CPU reader を指定する。 |

parser の `metavar` は `off|on|gpu|cpu`、選択肢は `settings.VISION_MODES = ("off", "on", "gpu", "cpu")` です。値は前後の空白を除去して小文字化してから照合するため、大文字でも受理されます。その他の値は `argparse.ArgumentTypeError` となり、候補一覧（近い候補があれば提案も含む）をエラーに表示します。別名はありません。`strata_cli/launch/cmd.py:37-45,96-99`、`strata_cli/launch/settings.py:23-28`

`--vision` 自体の既定値は未指定（`None`）です。対象モデルが画像対応で、engine に画像 reader がある場合に画像を有効化し、環境に応じた reader を選びます。画像非対応モデルや、reader がないと判明している engine では既定で `off` です。`strata_cli/launch/settings.py:77-92`、`strata_cli/launch/catalog.py:433-459`

`on` の選択規則は通常、VRAM 24 GB 未満なら CPU、24 GB 以上なら GPU です。ただし Intel GPU は現行設定で GPU reader が既定選択されず CPU になり、Apple Silicon Mac は統合メモリー上の Metal reader（GPU）が選ばれます。使用可能な GPU がない場合は CPU が選ばれます。この閾値と例外は `strata_control/vision_reader.py` の実装に基づきます。`strata_control/vision_reader.py:33-53`、`strata_cli/launch/catalog.py:448-459`

## 実行時の動作

コマンドラインで指定した値は、preset から読み込んだ設定より優先して今回の起動設定に反映されます。フラグがなければ preset の設定を引き継ぎ、preset もなければ動的既定値を使います。`strata_cli/launch/cmd.py:197-229`

通常のモデルでは、指定した画像設定に基づいて launch が model の準備状態を評価します。必要な画像 reader ファイル（`mmproj`）がまだなければ、準備計画に含め、setup を通じてモデルとともに取得します。`--plan` は計画を表示して終了し、画像設定と必要な download も表示します。`strata_cli/launch/modelstate.py:105-125,144-155,167-172`、`strata_cli/launch/runner.py:1704-1727,1772-1775`

model の再準備が必要なとき、launch は `--vision off` を setup の `--vision no` に、`on` を `yes` に変換し、`gpu` / `cpu` はそのまま渡します。設定済みの run config では、`off` は engine 引数から `--vision` を除き、reader 用の `vision` 設定も削除します。オンの場合は engine 引数に `--vision` がなければ追加し、reader の詳細設定は server 側が `vision` 設定から付加します。`strata_cli/launch/runner.py:264-293,695-710,727-735`

GPU reader がない場合、または対象 GPU のアーキテクチャを GPU reader がサポートしない場合、画像 reader 選択処理は CPU reader があれば CPU にフォールバックします。該当する CPU reader もなければ reader は `none` になります。GPU reader が起動時に失敗した場合に CPU reader を使う設定もあります。`strata_control/vision_reader.py:104-138,141-159`

## 適用条件と相互作用

- カタログ上で画像非対応のモデルに `on`、`gpu`、`cpu` を指定すると警告を出し、設定を `off` に補正します。明示的な `off` はそのままです。`strata_cli/launch/cmd.py:315-332`
- DeepSeek-V4.1-Flash（`multi_family`）はこの Strata revision で画像非対応です。画像を有効にする値を指定した場合は警告を出し、`off` にします。`strata_cli/launch/cmd.py:333-339`
- この option は `--model`、`--family`、`--model-path`、`--preset` の選択内容に応じて対象モデルや保存済み設定へ適用されます。対応モデルや reader が見つからず画像を有効化できない場合、起動後に「画像を有効にできずテキストのみで回答する」旨の警告を出す経路があります。`strata_cli/launch/cmd.py:205-229,315-339`、`strata_cli/launch/runner.py:712-725`
- 画像を有効にすると `mmproj` の取得が必要になる場合があります。ダウンロードサイズや、特定の実行環境で reader が使用可能かはモデル・engine package・GPU に依存します。`strata_cli/launch/modelstate.py:114-124,144-155,167-172`

## 出力と失敗経路

通常の出力では、`--plan` の人間向け表示に `pictures ...` が含まれます。JSON 出力の場合は計画オブジェクトと警告一覧に反映されます。指定値の不正は parser の段階で拒否されます。`strata_cli/launch/cmd.py:733-750`

画像非対応や reader 不在は、通常は警告と `off` への補正、またはテキストのみで続行する案内として処理され、`--vision` の値だけを理由に launch 全体を拒否する実装は確認できません。一方、モデル・engine の取得や起動自体に失敗する場合の終了コードと診断はその失敗経路に従い、この調査では画像 reader に固有の全失敗終了コードまでは確認していません。

## 関連文書

- [`strata launch` コマンド概要](README.md)
- [CLI オプション索引](../../README.md) — `strata-terminal` と `strata-engine` の同名オプションを区別

## 調査範囲

ソース checkout と同一 revision の `bin/strata launch --help` を照合しました。help は parser の選択肢・説明と一致しています。Release 済み binary の全 OS / GPU backend での挙動、reader package の実ファイル構成、実機起動時の警告文・終了コードは網羅していません。

## 根拠

- `strata_cli/launch/cmd.py:37-45,96-99` — parser、許容値、help。
- `strata_cli/launch/cmd.py:197-229,302-339` — CLI 値の設定反映、モデル適用条件、警告と補正。
- `strata_cli/launch/runner.py:264-293,695-735` — engine 設定反映、setup への値転送。
- `strata_cli/launch/catalog.py:433-459`、`strata_control/vision_reader.py:33-53,104-159` — 既定 reader、GPU / CPU 選択と fallback。
- `strata_cli/launch/modelstate.py:105-125,144-155,167-172`、`strata_cli/launch/runner.py:1704-1727,1772-1775` — reader ファイルの準備・download 計画。
- `strata_cli/launch/runner.py:712-725` — 設定後に画像を有効にできない場合の通知。
