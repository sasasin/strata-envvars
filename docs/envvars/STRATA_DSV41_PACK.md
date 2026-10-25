# `STRATA_DSV41_PACK`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

確認できた用途は DeepSeek-V4.1 関連テストへの pack ディレクトリ指定です。通常の Strata 実行コード（`src/`、`include/`、サーバー実装）でこの変数を読む箇所は見つかりませんでした。したがって、この変数が本番エンジンやサーバーの動作を変えるとは確認できません。

## 値と判定

| 用途 | 判定 | 動作 |
|---|---|---|
| `serve.test_dsv41` の実 tokenizer テスト | モジュール定義時に `os.environ.get("STRATA_DSV41_PACK")` が truthy か | unset または空文字ならテストを skip。空でない値ならテストを実行し、その値を `Path` に渡す |
| `tools/dsv41/test_prompt_skip.py` | モジュール読み込み時に取得した `PACK` が truthy か。ほかに `STRATA_DSV41_BIN` と `STRATA_DSV41_IDS` も truthy であることが必要 | 3つすべてが空でなければテストを実行し、`PACK` の値を実行ファイルの `--pack` 引数に渡す。どれかが unset または空文字ならテストを skip |

どちらも値の形式やパスの存在を事前検証しません。空白だけの文字列を含め、空文字でない値は有効扱いです。`serve.test_dsv41` では skip 判定はモジュール定義時、辞書参照と `Path` 化はテスト実行時です。その間に環境が変更されると、判定時と使用時の値が異なり得ます。`tools/dsv41/test_prompt_skip.py` はモジュール読み込み時の値を保持します。

## 有効になる条件

これはテスト専用です。`serve/test_dsv41.py` では fake engine を使う通常のテスト群に、実 tokenizer と golden token ID の照合を追加する条件になります。`tools/dsv41/test_prompt_skip.py` では GPU と DeepSeek-V4.1 pack を使う長文 prompt の比較テストを有効にするための入力です。後者では `STRATA_DSV41_PACK` のほか、エンジン実行ファイルと golden ID ファイルの指定も必要です。

## 実行時の詳細

`serve/test_dsv41.py` は指定ディレクトリから `vocab.json`、`tokenizer.json`、`merges.txt`、`token_type.json` を読み、実装内 tokenizer を組み立てて golden ケースの token ID と照合します。ファイル欠落や内容不正時の専用 fallback はなく、読み込み・解析・照合の例外または失敗がテスト結果になります。

`tools/dsv41/test_prompt_skip.py` は値を `strata-dsv41` の `--pack` 引数として渡します。値を環境変数としてエンジンに渡すことで pack を選ぶ実装ではありません。このテストは同じ pack と score ID を使い、`STRATA_DS4_PROMPT_SKIP` を `0` と `1` にして実行結果を比較します。

## 根拠

- `serve/test_dsv41.py:1-7,126-137`: 変数の用途説明、skip 条件、ディレクトリ内の tokenizer ファイル読み込みと golden ID 照合。
- `tools/dsv41/test_prompt_skip.py:5-6,23-25,38-47`: テスト起動例、環境変数値の取得と skip 条件、値を `--pack` 引数に渡す箇所。
- 調査対象の `src/`、`include/`、サーバー実装には、この変数を読む参照がありません。テストコード上の用途を本番実行時の挙動へ一般化していません。
