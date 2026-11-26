# `strata drafting plan --config`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--config` |
| 別名 | なし |
| 値 | `FILE`。モデルの run config JSON ファイルのパス |

## 役割

指定した run config を読み、そのモデルでどの drafter が選ばれるか、DFlash2 などの取得が必要かを計画します。`--config` は設定ファイルを読む入力であり、この `plan` コマンド自体はファイルやネットワークを変更しません。モデルや config の drafting 選択を明示的に指定したいときに使います。

## 使い方

```sh
strata drafting plan --config ./strata-model.json
```

JSON 形式で結果を受け取る例:

```sh
strata drafting plan --config ./strata-model.json --output json
```

## 値と既定値

- `--config` 自体は省略できますが、指定する場合は値として `FILE` パスが必要です。parser は拡張子やファイル存在を検証しません。別名はありません（`terminal/strata_cli/drafting_cmd.py:19-29`）。
- `--config` を省略した場合、`--family` / `--model` で指定した情報を使えます。drafting の指定もなければ `drafting.normalize(None)` により `auto` として扱われます（`terminal/strata_cli/drafting_cmd.py:117-125`、`terminal/strata_control/drafting.py:37-39,882-884`）。
- config に `drafting` があればそれが選択の既定値です。`--mode auto|mtp|dflash2|off` を併用すると config の値より優先されます。`--mode` の既定値はありません（`terminal/strata_cli/drafting_cmd.py:29,117-125`）。

## 実行時の動作

`--config` のパスを `Path` として開き、UTF-8 with BOM を許す UTF-8 JSON として読み込みます。読み込んだ `model_name`、`backend`、`args`、`gpu`、`parallel`、`drafting` などを使い、選択候補、対応する drafter、ファイルの有無、必要量を計算して plan を出力します（`terminal/strata_cli/drafting_cmd.py:101-137,240-265`）。

データフォルダは `--data-dir` があればその値を優先します。なければ config の engine 引数中の `--pack` または `--mtp` から推定し、それでも得られない場合は Strata の `Catalog().data_dir()` を使います（`terminal/strata_cli/drafting_cmd.py:110-116`、`terminal/strata_control/drafting.py:1662-1671`）。

config の `drafting` が `auto` 相当で `mtp` が `false` の場合、選択を `off` にします。また、`auto` / `mtp` で `--no-split` がなく、config から split engine が今回の起動を担当すると判定された場合は、plan を split 向け MTP として扱います（`terminal/strata_cli/drafting_cmd.py:120-125`）。`--mode` で `dflash2` を明示した場合などは、この自動 split 判定条件と異なる経路になります。

選択候補はモデル、family、backend、GPU アーキテクチャ等で変わります。`auto` は対象モデルと engine が DFlash2 を実行可能なとき DFlash2 を選び、それ以外は MTP を選びますが、モデル・カード別の既定値も考慮されます。選んだ drafterが利用できない場合の判断も plan に反映されます（`terminal/strata_control/drafting.py:1527-1545,1548-1587`）。

## 適用条件と副作用

- 指定したパスが読み取り可能で有効な JSON なら内容を計画に反映します。ファイルの読み込みで `OSError`、JSON の解析で `ValueError` が発生すると、エラー表示はせず空の config として続行します。この場合、指定ファイルのモデル設定に基づく計画にはなりません（`terminal/strata_cli/drafting_cmd.py:105-109`）。
- config から backend が得られる場合は、その backend の GPU を選択して hardware 情報を調べます。GPU 探索は既存環境への読み取り専用 probe で、失敗時は不明な hardware として扱われます（`terminal/strata_cli/drafting_cmd.py:41-43,117-118`、`terminal/strata_control/drafting.py:160-183,190-197`）。
- `plan` は fetch のネットワーク取得処理を呼びません。config、カタログ、drafter の配置状態などを参照し、人向けテキストまたは `--output json` / `jsonl` の選択に応じた JSON を標準出力へ出します（`terminal/strata_cli/drafting_cmd.py:211-213,247-266`）。

## 出力とエラー

通常の plan は成功時に終了コード `0` で、既定の `human` 出力または JSON を標準出力に書きます。`jsonl` も parser 上は受理されますが、plan の結果は JSON 1行として出力されます（`terminal/strata_cli/drafting_cmd.py:38,247-266`）。

`--config` 自体の読み込み失敗は上記のとおり空設定扱いとなり、CLI エラーや非ゼロ終了にはなりません。必須のサブコマンドを省略するなど parser の引数エラーは argparse の処理となり、終了コード `2` です（`terminal/strata_cli/drafting_cmd.py:20-24`、`terminal/strata_cli/cli.py:40-51`）。

## 根拠

- `terminal/strata_cli/drafting_cmd.py:19-38` — `drafting plan` / `fetch` の parser、`--config` と関連 option の定義。
- `terminal/strata_cli/drafting_cmd.py:101-137` — config の読み込み、値の抽出、data dir / mode / split 判定。
- `terminal/strata_cli/drafting_cmd.py:211-266` — plan 実行、選択計算、出力形式。
- `terminal/strata_control/drafting.py:882-884,1527-1587` — mode の正規化、候補の選択、利用可能性に応じた決定。
- `terminal/strata_control/drafting.py:1662-1671` — config の engine 引数からデータフォルダを推定する処理。
- `terminal/strata_cli/cli.py:198-200,2217-2221` — parser 登録と `drafting` 処理への dispatch。
