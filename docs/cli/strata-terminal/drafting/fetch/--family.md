# `--family`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--family` |
| 別名 | なし |
| 値 | モデルファミリー名（文字列、`NAME`）。parser に選択肢や形式 validation はない |

## 役割

run config がまだない場合に、`--model` の解決対象ファミリーを指定します。ファミリーとモデル名から実際のモデル名を解決し、そのモデルの drafting 選択や対応状況に基づいて fetch の対象を判断するために使われます。`--family` 単独ではモデル名を特定せず、既存 config がある場合の設定選択にも使われません。

## 使い方

```sh
# config がない状態で、qwen ファミリーのモデルの drafting pack を必要に応じて取得
strata drafting fetch --family qwen --model IQ3_S --if-needed
```

## 値と既定値

- 値を1つ取ります。parser は `metavar="NAME"` だけを指定し、既定値、許容値一覧、空文字や未知名に対する独自 validation は定義していません（`strata_cli/drafting_cmd.py:24-29`）。
- `--model` が与えられ、値が既知の完全なモデル名の prefix で始まらないとき、`Catalog.resolve(model, family)` に渡されます。解決に失敗した例外は捕捉され、モデル名は未確定 (`None`) として扱われます（`strata_cli/drafting_cmd.py:64-77`）。
- `--family` を省略した場合、catalog 側がモデル名を解決します。特定の既定ファミリーが CLI によって補われるとは確認できません。

## 実行時の動作

`--config` が指定されると、その JSON run config からモデル名、drafting モード、引数などを読み、CLI の `--family` はモデル名解決には使われません。`--config` を省略し、`--model` と `--family` を指定した場合は `Catalog.resolve` の後に catalog の正規モデル名へ変換し、drafting の必要性を判定します。設定を読めない場合は空 config として処理が続きます（`strata_cli/drafting_cmd.py:64-77, 101-120`）。

`--family` がない bare な `strata drafting fetch` は別経路です。インストール済みの対象モデルが1つならその config を採用し、複数ならモデル指定を促して終了します。`--family` を指定するとこの bare-fetch 自動選択経路から外れます（`strata_cli/drafting_cmd.py:80-98`）。実際の取得は解決後のモデル名、drafting mode、hardware 条件で `needs_pack` / `needs_tuned` を判定し、必要に応じて `ensure_for` に渡します（`strata_cli/drafting_cmd.py:150-165, 199-201`）。

## 適用条件と副作用

- `--family` は `drafting plan` と `drafting fetch` の両方に共通登録されていますが、この文書の対象である fetch では、特に `--model` がある config 未指定時のモデル解決情報です（`strata_cli/drafting_cmd.py:22-29`）。
- `--config` がある場合、その config がモデル情報の入力元です。`--family` と `--config` の競合を拒否する validation はありません。
- `--family` 自身はネットワークアクセスやファイル変更を起こしません。取得処理は `fetch` の通常動作によるもので、`--if-needed` を付けると drafting が不要な場合は取得を省略します（`strata_cli/drafting_cmd.py:34-37, 186-201`）。
- 文字列を catalog が認識できない場合の正確なエラーや最終モデルの選択は、この引数の parser では保証されません。モデル解決例外は `None` に丸められ、以降の汎用判定へ進みます（`strata_cli/drafting_cmd.py:71-77`）。

## 出力とエラー

`--family` 値自体に対する専用のエラー出力は定義されていません。引数値の欠落など構文エラーは argparse が処理します。fetch の出力・終了コードは後続の取得結果によって決まり、`--family` 固有の終了コードはありません（`strata_cli/drafting_cmd.py:19-39, 186-219`）。

## 根拠

- `strata_cli/drafting_cmd.py:19-39` — `plan` / `fetch` 共通 parser 登録と値定義、fetch 専用オプション。
- `strata_cli/drafting_cmd.py:64-77` — `--model` と `--family` を使うモデル名解決。失敗時は未確定扱い。
- `strata_cli/drafting_cmd.py:80-98` — family 未指定の bare fetch におけるインストール済み config 自動選択。
- `strata_cli/drafting_cmd.py:101-120` — config、data directory、モデル情報の組み立て。
- `strata_cli/drafting_cmd.py:150-165, 186-219` — fetch 要否判定、`--if-needed`、取得呼び出し、出力と終了コード。
