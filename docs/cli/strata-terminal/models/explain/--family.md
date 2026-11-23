# `strata models explain --family`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models explain` |
| オプション | `--family` |
| 別名 | なし |
| 値 | モデルファミリー名（文字列）。既定値は未指定（`None`） |

## 役割

`NAME` がモデルサイズだけの場合に、そのサイズをどのモデルファミリーとして調べるか指定します。同じサイズを複数のファミリーが提供している場合の選択に使います。`NAME` に `family/size` を指定した場合は、`--family` を省略してファミリーを名前の中で指定できます（`terminal/strata_cli/cli.py:178-180`、`terminal/strata_cli/models_explain.py:16-20`）。

## 使い方

```sh
# モデルサイズを qwen ファミリーとして調べる
strata models explain IQ3_S --family qwen

# NAME にファミリーを含めて指定する（この場合 --family は省略）
strata models explain qwen/IQ3_S
```

## 値と既定値

値はファミリー名で、parser では型や選択肢を制限していません。既定値は未指定です。parser の後でモデルカタログに照合され、名前が存在しないファミリーや、そのファミリーが提供していないサイズはエラーになります。照合時にファミリー名の小文字化や空白除去は行われません。一方、モデルサイズは大文字・小文字を区別せず照合されます（`terminal/strata_cli/cli.py:180`、`terminal/strata_cli/launch/catalog.py:550-572`）。

`NAME` に `/` があり `--family` が省略されている場合は、先頭をファミリー名、後半をサイズとして分割し、それぞれ前後の空白を除きます。`--family` を指定するとこの分割は行われず、`NAME` 全体がサイズとして照合されます（`terminal/strata_cli/models_explain.py:16-20`）。

## 実行時の動作

parser が受け取った値は `models_explain.explain()` に渡され、`Catalog.resolve()` がファミリーとサイズの組み合わせを確定します。ファミリー未指定でサイズが複数のファミリーにある場合は `qwen` が候補にあればそれを選び、なければカタログ上の最初の候補を選びます。`--family` を指定した場合は、そのファミリーがサイズを提供していることを検証してから使います（`terminal/strata_cli/cli.py:581-589`、`terminal/strata_cli/launch/catalog.py:550-572`）。

確定した組み合わせからインストール済み run config が見つかれば、その設定に記録された data folder を使います。見つからない場合は Strata の共通 data folder を使います。`--data-dir` が同時に指定されていれば、こちらが優先されます（`terminal/strata_cli/models_explain.py:23-37`、`terminal/strata_cli/launch/catalog.py:762-774`）。その data folder 内でモデルフォルダーを調べます。通常のファミリーでは setup の表記、run-config tag の小文字表記、名前の大文字・小文字だけが異なる既存フォルダーの順に探し、どれもなければ setup の表記をダウンロード先候補として返します。Hy4-Flash と Inkling-2-Mini は `models/<family>` を調べます（`terminal/strata_cli/launch/catalog.py:592-621`）。

## 適用条件と副作用

このオプションは `strata models explain` 専用です。モデルファミリー名は、現在のカタログに登録されている名前と一致する必要があります。説明処理はモデルフォルダーの存在確認、`.gguf` ファイル名とサイズの読み取り、fallback 時の `models/` 直下のフォルダー列挙を行います。説明処理自体は読み取り専用で、ファイルのダウンロード・移動・書き込みは行いません（`terminal/strata_cli/models_explain.py:1-5,37-61`）。

ファイルへのアクセスに失敗した場合、通常のフォルダー探索では一部の `OSError` を「存在しないものとして扱う」か、追加フォルダー一覧を空にして続行します。モデルカタログの読み込みなどで `OSError` が上位へ伝播した場合は、CLI がエラーとして処理します（`terminal/strata_cli/launch/catalog.py:607-620`、`terminal/strata_cli/cli.py:2258-2265`）。

## 出力とエラー

既定の `--output human` は、解決したファミリー・モデル、data folder、探索したパスと結果を標準出力に表示します。`--output json` を指定すると、成功時は `schema_version: 1` と `ok: true` を含む JSON を標準出力に出します（`terminal/strata_cli/cli.py:178-182,566-573,583-589`、`terminal/strata_cli/models_explain.py:64-84`）。

不明なモデル名、カタログにないファミリー名、またはそのファミリーが提供しないサイズでは、近い候補を含む `ValueError` メッセージを返して終了コード `2` になります。通常出力では `strata: ...` を標準エラーに出し、JSON 出力では `ok: false` とエラー情報を標準出力に出します（`terminal/strata_cli/launch/catalog.py:555-568`、`terminal/strata_cli/cli.py:558-563,583-589`）。

## 根拠

- `terminal/strata_cli/cli.py:178-182` — `strata models explain` の引数定義、`--family` の値と出力形式の既定値。
- `terminal/strata_cli/cli.py:581-589` — 引数を説明処理へ渡す経路と、`ValueError` の終了コード・成功出力。
- `terminal/strata_cli/models_explain.py:16-37` — `NAME` の分割、ファミリー解決、data folder の選択。
- `terminal/strata_cli/models_explain.py:37-61,64-84` — フォルダーと GGUF の読み取り、human 表示。
- `terminal/strata_cli/launch/catalog.py:550-572` — モデル・ファミリーの照合と未指定時の選択。
- `terminal/strata_cli/launch/catalog.py:592-621,762-774` — モデルフォルダー探索と data folder の決定。
