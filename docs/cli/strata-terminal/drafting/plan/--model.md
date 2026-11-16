# `strata drafting plan --model`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--model` |
| 別名 | なし |
| 値 | `NAME`（モデルサイズ名、または `qwen3.8-flash-next-` で始まる完全なモデル名）。parser 上の型・候補制約なし |

## 役割

run config を指定しない計画で、想定するモデルを DFlash2 の対象判定や出力内容に反映する。通常は `--family` と組み合わせてサイズ名を渡す。config ファイルが読め、その `model_name` が空でなければ、その値が `--model` より優先される。`strata drafting plan` は取得内容を表示するだけで、ダウンロードは `fetch` 側の処理で行う（`strata_cli/drafting_cmd.py:19-38, 101-120, 166-185`）。

## 使い方

```sh
# config 未作成の Qwen サイズについて計画する
strata drafting plan --family qwen --model IQ3_S

# 既存 config のモデルを使って計画する（config の model_name が優先）
strata drafting plan --config /path/to/run.json --model IQ3_S

# 人が読みやすい形式が既定。機械処理向け JSON も選べる
strata drafting plan --family qwen --model IQ3_S --output json
```

## 値と既定値

- 値を1つ取る。`argparse` では `metavar="NAME"` のみを指定し、`type`、`choices`、既定値は設定していないため、省略時は `None`（`strata_cli/drafting_cmd.py:24-29`）。
- 値が `qwen3.8-flash-next-` で始まる場合（大文字小文字を区別せず判定）、その文字列を完全なモデル名としてそのまま使う（`strata_cli/drafting_cmd.py:64-70`）。
- それ以外はモデルカタログのサイズ名として `Catalog.resolve(NAME, --family の値)` に渡す。サイズ名の照合は大文字小文字を区別せず、`--family` を付けたときはその family に該当サイズがあるかも照合する（`strata_cli/drafting_cmd.py:71-75`、`strata_cli/launch/catalog.py:393-414`）。
- parser 段階で空文字・未知名・family との不一致を拒否する検証はない。名前解決中の例外は握りつぶされ、モデル名は不明 (`None`) として扱われる（`strata_cli/drafting_cmd.py:71-77`）。

## 実行時の動作

1. `--config` があれば UTF-8（BOM 付きも許容）で読み、読み込み不能または JSON 不正なら空の config として続行する（`strata_cli/drafting_cmd.py:101-109`）。
2. モデル名は config の `model_name`、それがなければ `--model` から導出する。したがって、config にモデル名がある場合、`--model` は計画対象を上書きしない（`strata_cli/drafting_cmd.py:117-120`）。
3. `--model` から得た名前と `--family` は drafter の選択・対象モデル判定に渡る。名前が解決できなくても、指定済み family は判定に使われる。DFlash2 の対象かどうかは family が指定されていれば `qwen`、`gyro`、`unsloth` を対象とし、family がなければモデル名パターンで判定する（`strata_control/drafting.py:453-467`）。実際に選ばれる drafter は `--mode`、backend、ハードウェア等にも依存する（`strata_control/drafting.py:1364-1387`）。
4. plan はモデル名を使って必要な drafter、準備状況、対応可否、表示文を組み立てる。明示的にモデルを尋ねたのにダウンロード不要なら、見積もりサイズを `0.0` にし、準備不要のときは「Nothing to download.」を返す（`strata_cli/drafting_cmd.py:159-185`）。

config に `model_name` がない場合に `--model` から名前を作るには `Catalog` を利用するため、モデルカタログが利用できないと名前解決は汎用計画に戻る。`Catalog` 初期化では install root を作成する処理もあるため、環境によっては計画時にそのディレクトリが作られる（`strata_cli/drafting_cmd.py:71-77, 115-120`、`strata_cli/launch/catalog.py:246-260`）。

## 適用条件と副作用

- 既存 run config のモデル名が利用できる場合は `--model` の指定は採用されない。config 自体を読めない場合は空 config 扱いとなり、`--model` による補完へ進む（`strata_cli/drafting_cmd.py:101-120`）。
- `--model` 自体はファイルやネットワークを操作しない。対象コマンド `plan` は計画結果を出力して終了する。なお、カタログを使う経路では install root のディレクトリ作成が起こり得る（`strata_cli/drafting_cmd.py:166-185`、`strata_cli/launch/catalog.py:251-260`）。
- DFlash2 の可否や必要性は `--model` だけでは決まらず、family、選択モード、backend / GPU、config 内の engine 引数、ローカルの drafter / MTP 状態も影響する（`strata_cli/drafting_cmd.py:117-134, 159-173`、`strata_control/drafting.py:1364-1387, 1390-1425`）。

## 出力とエラー

plan は人向け形式では計画文または概要行を stdout に出し、`--output json` / `jsonl` では `ok: true` と計画内容の JSON を出す（`strata_cli/drafting_cmd.py:181-185`）。未知のサイズ名や `--family` との不一致は `_planned_model_name` 内で捕捉されるため、それだけで CLI エラーや非ゼロ終了にはならず、モデル名不明として計画が続く（`strata_cli/drafting_cmd.py:71-77`）。

## 根拠

- `strata_cli/drafting_cmd.py:19-38` — `plan` / `fetch` に共通する `--model NAME` parser 定義。
- `strata_cli/drafting_cmd.py:64-77` — 完全名の扱い、カタログ解決、解決例外の処理。
- `strata_cli/drafting_cmd.py:101-134` — config 読み込み、モデル名の優先順位、family や環境情報との組み立て。
- `strata_cli/drafting_cmd.py:150-185` — plan の判定・出力経路。
- `strata_cli/launch/catalog.py:393-421, 246-260` — サイズと family の照合、モデル名生成、Catalog 初期化時の install root 処理。
- `strata_control/drafting.py:453-467, 1364-1387, 1390-1425` — DFlash2 対象判定、選択条件、利用可否と fallback。
