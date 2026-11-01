# `--model`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。調査時の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | Apple Silicon 用 `metal/setup_mac.py`（通常は `./setup.sh` 経由） |
| オプション | `--model` |
| 別名 | なし |
| 値 | `MAC_MODELS` にあるモデル名を1つ指定。値は必須。 |

## 役割

Apple Silicon の Metal setup で導入・準備するモデルを選びます。省略した場合は Mac の unified memory に応じて候補を推薦し、対話で選択します。明示したモデルはメモリ適合の推奨を上書きして選ばれますが、適合しない場合も拒否されず、SSD streaming などの注意を表示して続行します（`metal/setup_mac.py:389-403`、`strata_control/mac_fit.py:145-176`）。

## 使い方

リポジトリのルートでモデルを指定して setup し、完了後のサーバー起動を省く例です。ダウンロード、engine build、モデル準備、設定ファイル作成は実行されます。

```sh
./setup.sh --model IQ3_XXS --no-start
```

`setup.py` は macOS で `STRATA_CONTROL_INSTALL=1` が設定されていない場合、受け取った引数をそのまま `metal/setup_mac.py` に渡します（`setup.py:9062-9069`、`setup.py:7703-7707`）。

## 値と既定値

- `--model` は `choices=list(MAC_MODELS)` で検証される。調査対象 revision の有効値は `Q2_0`、`IQ3_XXS`、`IQ3_S`、`UD-Q4_K_XL`、`UD-Q5_K_XL`、`UD-Q6_K_XL`、`Gyro-S`、`Gyro-M`（`metal/setup_mac.py:329-333`、`strata_control/mac_fit.py:17-34`）。
- 省略時の parser 既定値は `None`。メモリに基づく推薦モデルが対話候補の初期値となり、`--yes` が指定されている場合はその推薦値が自動選択される（`metal/setup_mac.py:392-401`、`setup.py:930-943`）。通常の候補一覧から `MAC_MODELS` の `missing` 印が付いたモデルは除かれるが、明示値の `choices` は `MAC_MODELS` 全体を使う（`metal/setup_mac.py:332`、`metal/setup_mac.py:395`）。この revision の表には `missing` 印のモデルはない。
- 値の省略、未知の名前、空文字列は parser の必須値／choices 検証で拒否される。`--model` を複数回指定した場合は argparse の通常の `store` 動作で最後の値が残る（`metal/setup_mac.py:332`）。

## 実行時の動作

明示値があれば推薦モデルの代わりにその値を使い、モデル固有の注意を出した後、family、ダウンロード容量、ファイル名、ダウンロード先を決めます（`metal/setup_mac.py:389-422`、`metal/setup_mac.py:66-74`）。その後、選んだモデルの GGUF shard を取得・検証し、必要なモデル pack を準備し、選択モデルを含む起動設定と run script を書きます（`metal/setup_mac.py:450-464`、`metal/setup_mac.py:476-516`、`metal/setup_mac.py:542-570`）。モデル名は `MAC_MODELS` の family/shard 情報に従ってモデルファイル名と処理経路へ反映されます（`strata_control/mac_fit.py:19-34`、`metal/setup_mac.py:66-74`）。

`--family` を併用して値が選択モデルの family と異なる場合、警告を表示してモデル表から求めた family を使用します。つまり `--family` はこの選択結果を強制変更しません（`metal/setup_mac.py:415-419`）。

`--update` と併用すると、選択モデルの既存ファイルと pack を確認して engine の更新経路へ進みます。モデルファイルが存在しない場合もダウンロードせず、「setup で取得する」案内を出して正常終了します（`metal/setup_mac.py:435-448`）。既存の Metal 設定があり、`--model` などの setup を選ぶ引数がないときは通常起動の shortcut に入りますが、`--model` を指定するとその shortcut を避けて選択処理へ進みます（`metal/setup_mac.py:369-372`）。`--check` はモデル選択より前に終了するため、この併用時は `--model` の値は setup 対象の選択には使われません（`metal/setup_mac.py:382-385`）。

## 適用条件と副作用

この option は `setup.py` が Apple Silicon 向け Metal setup に委譲したときの parser に属します。`setup.py` の通常 parser が使われる経路とは別 scope です（`setup.py:9068-9069`、索引 `docs/cli/README.md:1594-1610`）。

明示したモデルが Mac の resident memory に収まらない場合、setup は注意を出し、自動的に expert を SSD から streaming する実行設定にします。ファイルが既知の未対応状態として登録された場合は選択を保持して処理しますが、engine 読み込み時に停止すると注意書きがあります（`strata_control/mac_fit.py:140-176`）。モデル選択後の通常経路は、モデルのダウンロード、pack 準備、必要に応じた vision encoder 準備、`strata-<model>.json` と run script の作成を伴います。`--no-start` を加えると設定作成後の server 起動だけを省略します（`metal/setup_mac.py:450-570`）。

## 出力とエラー

- 有効値以外は argparse が usage と引数エラーを表示して処理を止める。ソースで確認できる拒否条件は `choices` への不一致である（`metal/setup_mac.py:328-333`）。
- メモリに合わないモデルは拒否せず、streaming になる旨を warning として表示する（`strata_control/mac_fit.py:164-176`）。
- `--update` でモデルが未導入なら、モデルをダウンロードしない旨と `./setup.sh --setup` の案内を表示し、`0` を返す（`metal/setup_mac.py:435-448`）。
- setup が `S.fail()` に到達した場合はエラーと再実行案内を表示して終了 status `1` となる。例えば必要なモデル準備中に Strata engine が動作中なら、この経路で停止する（`metal/setup_mac.py:489-492`、`setup.py:904-909`）。ダウンロード、build、ディスク容量など、その他の失敗条件は呼び出し先ごとの処理によるため、ここでは一律の終了コードを記載しない。

## 根拠

- parser とモデル選択・対話: `metal/setup_mac.py:327-405`
- Mac モデル名、family、shard 定義と推薦・適合判定: `strata_control/mac_fit.py:17-37`、`strata_control/mac_fit.py:140-176`
- モデルの shard 名、ダウンロード、pack、設定生成: `metal/setup_mac.py:66-74`、`metal/setup_mac.py:450-570`
- `setup.py` から Mac parser への委譲: `setup.py:7703-7707`、`setup.py:9062-9069`
- 索引上の scope と予定リンク: `docs/cli/README.md:1594-1610`
