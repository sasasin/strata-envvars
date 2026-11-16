# `--model`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--model` |
| 別名 | なし |
| 値 | モデルのサイズ名、または `qwen3.8-flash-next-` で始まる完全なモデル名。parser 上は任意の文字列。 |

## 役割

モデルの識別情報を fetch の計画と実行へ渡し、そのモデルで使う drafter を決めます。サイズ名を使う場合は `--family` と組み合わせて対象 family を指定できます。モデルが特定されると、DFlash2 の対象判定や、該当する場合に専用 tuned drafter を選ぶ判断へ使われます。

## 使い方

```sh
# Qwen family のモデルサイズを指定して、そのモデル用 drafter を取得する
strata drafting fetch --family qwen --model IQ3_S

# 完全なモデル名を指定する
strata drafting fetch --model qwen3.8-flash-next-iq3_s
```

## 値と既定値

`--model` は値を1つ取ります。`argparse` では `metavar="NAME"` のみを指定しており、choices、型変換、必須指定、既定値はありません（`strata_cli/drafting_cmd.py:24-29`）。したがって、値の構文検査は parser では行われません。

完全名が `qwen3.8-flash-next-` で始まる場合はそのままモデル名として扱います。それ以外は `Catalog.resolve()` でサイズ名を検索し、結果の family とサイズから設定形式のモデル名を組み立てます。family を省略したサイズ名が複数 family にある場合は、qwen が候補なら qwen、そうでなければ最初の候補が選ばれます（`strata_cli/drafting_cmd.py:64-77`、`strata_cli/launch/catalog.py:393-421`）。

サイズ名または family の解決に失敗しても、この処理は例外を握りつぶしてモデル名を `None` とします。そのため未知の値は `--model` 自体の parser error にはならず、モデルを識別できない状態で後続の判定へ進みます（`strata_cli/drafting_cmd.py:71-77`）。

## 実行時の動作

`--model` は `plan` と `fetch` の両 parser に共通で登録されています。fetch では、設定ファイルが指定されていればその `model_name` が優先され、設定にモデル名がない場合に `--model` からの解決結果が使われます（`strata_cli/drafting_cmd.py:22-29, 117-120`）。

モデル名は DFlash2 のモデル適合判定、選択判断、既存 drafter の確認、tuned variant の選択に渡されます。DFlash2 が選ばれ、モデル・backend 等が tuned 条件を満たす場合は、その tuned drafter を取得しようとし、利用できなければ通常 drafter へフォールバックします（`strata_cli/drafting_cmd.py:159-165, 199-201`、`strata_control/drafting.py:463-467, 1449-1460`、`strata_control/drafting_fetch.py:305-329`）。たとえば tuned variant の選択は backend とモデル名に対応する表を参照します（`strata_control/drafting.py:370-384`）。

モデルを識別できる値にするには、サイズ名なら `--family` の併記を推奨します。特に同じサイズが複数 family に存在するとき、family を省略した場合の選択規則は上記のとおりです。`--config` と併用した場合は設定内の `model_name` がモデル名として使われます。選択モードは `--mode`（省略時は設定の `drafting`）にも左右されるため、モデル名だけで取得が常に発生するわけではありません（`strata_cli/drafting_cmd.py:117-125, 162-165`）。

## 適用条件と副作用

`--model` 自体はモデルファイルを読み込んだり、モデルの存在を fetch 前に検証したりしません。認識されたモデル名は drafter の適合性・variant 判定に使われ、最終的な fetch は `--mode`、backend、hardware support、ファイルの有無などの条件で決まります（`strata_control/drafting.py:463-467, 1364-1385`）。このオプションで fetch が実行されると、指定または既定の data directory に drafter を準備します。通常 drafter はネットワーク取得、検査、engine 用 pack の作成を行い、取得元ファイルを削除します（`strata_control/drafting_fetch.py:332-390`）。

## 出力とエラー

モデル名の解決失敗はこのオプション単独では終了エラーにならず、モデル名なしとして処理が続きます。複数の DFlash2 対応モデルがインストール済みで、`--model`、`--config`、`--family` のいずれも指定しない fetch は、対象選択を求めて終了コード `2` になります。この分岐では人向け出力は stderr、JSON/JSONL 出力は `which_model` エラーです（`strata_cli/drafting_cmd.py:80-99, 150-158`）。

fetch による取得・検査・pack の失敗は、人向けには `strata:` 付きのエラーを stderr に出し、終了コード `5` を返します。`json` / `jsonl` では `drafting_failed` エラーを出力します（`strata_cli/drafting_cmd.py:210-215`）。

## 根拠

- `strata_cli/drafting_cmd.py:22-29` — `plan` / `fetch` における parser 登録と値の説明。
- `strata_cli/drafting_cmd.py:64-77, 101-125` — サイズ名・完全名の変換、config と引数のモデル名の選択、mode 判定。
- `strata_cli/launch/catalog.py:393-421` — サイズ名・family の検証、曖昧な候補の選択、完全な `model_name` の生成。
- `strata_control/drafting.py:370-384, 463-467, 1364-1385, 1449-1460` — tuned variant、対応モデル、drafter 選択と必要性の判定。
- `strata_cli/drafting_cmd.py:150-219`、`strata_control/drafting_fetch.py:305-390` — fetch の実行、出力・失敗経路、取得と pack の副作用。
