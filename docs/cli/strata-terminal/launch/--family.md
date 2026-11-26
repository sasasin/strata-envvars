# `--family`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--family` |
| 別名 | なし |
| 値 | モデルファミリー ID（`NAME`）。文字列として受け取る |

## 役割

同じモデルサイズ名を複数のファミリーが提供するとき、`--model` と組み合わせてファミリーを指定します。ファミリーとサイズの組み合わせはモデルカタログで解決され、保存済み preset の選択値を上書きできます。

## 使い方

```sh
strata launch --family qwen --model q2_0 --plan
```

## 値と既定値

`--family` は `NAME` を1つ取ります。parser では `choices`、型変換、既定値を指定していないため、未指定時は `None` です。ファミリー名の有効性と、指定モデルをそのファミリーが提供するかは、`--model` がある場合にモデルカタログで検証されます。照合はファミリー ID の完全一致で、大文字小文字を正規化しません。一方、モデルサイズ名は大文字小文字を区別せず照合され、カタログ上の表記が選択値として返ります（`terminal/strata_cli/launch/cmd.py:81-86`、`terminal/strata_cli/launch/catalog.py:550-572`）。

## 実行時の動作

- `--model` とともに指定すると、`Catalog.resolve(model, family)` がモデル名を検索します。存在しないモデル、未知のファミリー、またはそのファミリーにないサイズは `ValueError` になります。値が合えば `(family, model)` が起動設定に入り、`setup.py` に `--family` と `--model` として渡されます。またファミリー ID はモデル保存先の解決にも使われます（`terminal/strata_cli/launch/cmd.py:232-239`、`terminal/strata_cli/launch/catalog.py:550-572, 581-604`、`terminal/strata_cli/launch/runner.py:1351-1358`）。
- `--family` を省略してモデルだけを指定した場合は、該当モデルを提供するファミリーから `qwen` を優先し、それ以外は最初の候補が選ばれます（`terminal/strata_cli/launch/catalog.py:564-572`）。
- カタログのファミリー集合は通常のファミリー表に、Strata が認識する独自パス、Hy4、Inkling のファミリーをマージしたものです（`terminal/strata_cli/launch/catalog.py:24-38`）。
- `--preset NAME` と併用して `--model` を省略すると、preset のモデルを保ったまま `--family` の値を設定します。この分岐では `Catalog.resolve` を通らず、ここでファミリー名と preset のモデルの整合性は検証されません（`terminal/strata_cli/launch/cmd.py:215-240`）。その後の実行処理の結果は preset の内容やカタログに依存します。
- preset なしで `--family` だけを指定してもモデルは確定しません。対話画面では画面操作に進みます。非対話で `--plan` を付けた場合は推奨モデルの選択に進みますが、通常の非対話実行では `--family` は選択済みの入力として数えられず、モデル名または preset を指定するようエラーになります。ほかの選択入力がある場合も、モデル未指定かつ `--model-path` もなければ、推奨モデルを選ぶ処理に進むため、指定したファミリーだけでモデルを絞り込む動作ではありません（`terminal/strata_cli/launch/cmd.py:349-356, 849-873`）。
- `--model-path` と `--family` を指定し、`--model` を省略した場合、引数処理は preset の有無にかかわらず `family` と `model` を `None` に戻すため、この分岐では `--family` は残りません。パス内ファイルの識別・検査は後段の別処理です。`--model` も指定した場合はモデルをカタログで解決してからモデルパスを保持します（`terminal/strata_cli/launch/cmd.py:222-239, 879-882`）。

## 適用条件と副作用

このオプション自体によるファイル変更やダウンロードはありません。解決されたモデル選択は起動設定に使われ、通常の `strata launch` は以降の起動フローへ進みます。`--plan` を併用すると起動予定を表示して終了し、モデル等の変更は行いません（`terminal/strata_cli/launch/cmd.py:897-925`）。

## 出力とエラー

`--model` と組み合わせた不正値はカタログ解決時のエラーになります。未知ファミリーでは近い候補と利用可能なファミリーを含む文面、モデル不在では近いモデル候補、ファミリーにサイズがない場合はそのファミリーが提供するサイズが作られます。`strata launch` はこれらの `ValueError` を通常出力では標準エラーに `strata: ...` と表示し終了コード `2` で返します。`--output json` では `ok:false` の JSON を標準出力に出します（`terminal/strata_cli/launch/catalog.py:556-568`、`terminal/strata_cli/launch/cmd.py:759-764, 1009-1012`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:81-86` — `strata launch` parser の登録。値は `NAME`、別名・choices・default の指定なし。
- `terminal/strata_cli/launch/cmd.py:215-240` — preset 読み込み、`--model` との組み合わせ、`--model-path` との分岐。
- `terminal/strata_cli/launch/catalog.py:24-38` — 解決対象ファミリー表の統合。
- `terminal/strata_cli/launch/catalog.py:550-572` — モデル名・ファミリー・サイズの照合と既定ファミリー選択。
- `terminal/strata_cli/launch/cmd.py:349-356, 759-764, 882-925, 1009-1012` — モデル未指定時の推奨選択、失敗出力、plan の終了処理。
