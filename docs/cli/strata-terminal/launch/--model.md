# `strata launch --model`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--model` |
| 別名 | なし |
| 値 | `NAME`。モデルカタログのモデルサイズ名。大文字・小文字は区別しない |

## 役割

起動対象のモデルサイズを選びます。`--family` と組み合わせると、そのファミリーが提供するサイズか検証されます。適用された選択は起動設定に入り、既存ファイルがなければ Terminal が `setup.py` にモデルと family を渡して準備します。モデルを省略した場合は、preset に選択があればそれを使い、選択がなければコンピューターに対する推奨モデルを選びます。parser の同じ `--model` は `strata launch connect` にも別用途で定義されていますが、この文書は索引上の `strata launch` 本体のスコープです。

## 使い方

```sh
# モデルサイズを指定して、実行内容だけ確認する
strata launch --model iq3_xxs --plan

# family に同じサイズが複数ある場合、family も指定する
strata launch --model iq3_xxs --family qwen --plan
```

## 値と既定値

- 値は `NAME` で、既知のモデルサイズ名を `--model` に渡します。受理名はカタログと Strata 独自サイズ一覧から組み立てられます。モデル名の照合は大文字・小文字を無視します（`terminal/strata_cli/launch/cmd.py:83`, `terminal/strata_cli/launch/catalog.py:550-559`）。
- `--family` を指定した場合、family 名はカタログに存在し、かつ指定サイズを提供する必要があります。family を省略して同じサイズを提供する family が複数ある場合は `qwen` を優先し、それ以外はカタログ順の最初を選びます（`terminal/strata_cli/launch/cmd.py:84`, `terminal/strata_cli/launch/catalog.py:560-572`）。
- オプション自体に固定の既定サイズはありません。preset の設定を先に読み、明示した `--model` があれば解決した family とモデルで上書きします。`--model-path` だけを指定したときは preset 由来の family/model をクリアし、ファイルからモデルを判定する経路にします。モデルも `--model-path` も選ばれていなければ、コンピューター情報に基づく推奨を適用します（`terminal/strata_cli/launch/cmd.py:215-238`, `terminal/strata_cli/launch/cmd.py:344-356`）。
- 不明なモデル名、存在しない family、またはその family が提供しないサイズは `ValueError` になります。モデル名/family の候補と、可能なら近い候補を含むメッセージを返します。通常の launch 実行ではエラー文を出して終了コード `2` です。モデルカタログが利用できない場合は、モデルを明示した起動は失敗し終了コード `5` になります（`terminal/strata_cli/launch/catalog.py:556-568`, `terminal/strata_cli/launch/cmd.py:838-844`, `terminal/strata_cli/launch/cmd.py:1009-1012`）。

## 実行時の動作

- `--preset NAME` と併用すると、保存済み設定を読み込んだ後、指定した `--model` がそのモデル選択を置き換えます。解決後、`--model-path` が同時指定されていなければ、preset に保存されていたモデルファイルのパスを外し、選択モデルの通常の準備経路を使います（`terminal/strata_cli/launch/cmd.py:215-238`）。
- 選択後、既定の context などを補い、カタログ上の適合性・ディスク容量に関する通知を集めます。`--plan` では選択モデルを含む計画を表示して終了し、「Nothing was changed.」と表示します。plan は署名付き feed の問い合わせを行う場合があります（`terminal/strata_cli/launch/cmd.py:344-380`, `terminal/strata_cli/launch/cmd.py:897-925`）。
- 通常起動では Runner がモデルのインストール状態を確認します。条件に合う既存設定・ファイルを再利用できなければ、選択した family と model を `setup.py --yes --no-start --family ... --model ...` に渡して準備し、セットアップ出力を進捗として表示します。モデルのダウンロード、追加ファイル準備、実行設定の作成が発生することがあります（`terminal/strata_cli/launch/runner.py:1351-1364`, `terminal/strata_cli/launch/runner.py:1679-1710`, `terminal/strata_cli/launch/runner.py:1719-1730`）。
- `--model-path` も指定した場合は、そのフォルダーまたはファイルを使う独自ファイル経路です。明示モデルがファイル内容の判定結果と食い違うと、その差を案内してセットアップが停止する場合があります（`terminal/strata_cli/launch/runner.py:1959-2005`）。
- `--show-key` を併用する管理経路では通常の起動モデル選択は行わず、`--model` は setup が登録したモデル設定の API key を絞り込む名前として使われます。大文字小文字を無視した完全一致または末尾一致で探します（`terminal/strata_cli/launch/cmd.py:798-815`, `terminal/strata_cli/launch/cmd.py:728-750`）。

## 適用条件と副作用

- モデル一覧を含む Terminal install が必要です。薄い Terminal でカタログを読み込めない場合、`--model` を指定した起動はカタログエラーになります（`terminal/strata_cli/launch/cmd.py:838-844`）。
- 選択モデルの準備が必要な場合は、モデルファイルのダウンロードや、data directory へのセットアップ、run config の作成・更新が起こり得ます。`--model-path` がある場合はそのファイルを使い、通常のモデルダウンロードを避ける経路があります（`terminal/strata_cli/launch/runner.py:1708-1730`, `terminal/strata_cli/launch/runner.py:1904-1953`）。
- GPU/backend、モデルファミリー、既存ファイルの状態によって準備方法は異なります。すべてのモデル・backend の個別制約を本オプション単独の parser からは確定できないため、ここでは共通の選択・転送経路に限定しました。

## 出力とエラー

モデル名や family の検証エラーは通常、人向けのエラー行として出力され、終了コード `2` になります。モデル一覧がない場合は終了コード `5` です。モデル準備中には対象名、セットアップ進捗、ダウンロードの案内が表示され、子プロセスが失敗した場合はセットアップの失敗内容を `LaunchError` として返します（`terminal/strata_cli/launch/cmd.py:838-844`, `terminal/strata_cli/launch/cmd.py:1009-1014`, `terminal/strata_cli/launch/runner.py:1708-1710`, `terminal/strata_cli/launch/runner.py:1782-1803`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:73-87` — `strata launch` parser と `--model NAME` の宣言。
- `terminal/strata_cli/launch/cmd.py:215-238` — preset 読み込み、`--model` による解決・上書き、`--model-path` との関係。
- `terminal/strata_cli/launch/catalog.py:550-572` — 大文字小文字を無視するサイズ照合、family/サイズ検証、family 未指定時の選択。
- `terminal/strata_cli/launch/cmd.py:344-380` — 未選択時の推奨と選択モデルに対する通知・context 補完。
- `terminal/strata_cli/launch/cmd.py:897-925` — `--plan` の表示と終了。
- `terminal/strata_cli/launch/runner.py:1351-1364`, `1679-1710`, `1719-1730` — 選択の setup 引数への転送、モデル状態の確認、setup 起動。
- `terminal/strata_cli/launch/runner.py:1959-2005` — `--model-path` のファイル判定とモデル選択との整合。
- `terminal/strata_cli/launch/cmd.py:728-750`, `798-815` — `--show-key` 経路での `--model` による API key 対象選択。
- `terminal/strata_cli/launch/cmd.py:1009-1014` — launch 側の `ValueError` 表示と終了コード。
