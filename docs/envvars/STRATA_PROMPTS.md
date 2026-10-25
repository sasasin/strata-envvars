# `STRATA_PROMPTS`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

この名前を読む箇所は `metal/tests/serve_probe.py` だけで、Metal の serve 回帰プローブが入力 prompt token ID ファイルを探すディレクトリを指定します。Strata の実行エンジンや通常の server / setup 経路が読む実装は確認できません。そのため、これは製品実行時の設定としては確認できず、同梱プローブ用の指定です。

## 値と判定

| 状態 | プローブで使うディレクトリ |
|---|---|
| 未設定 | `~/owner-t9/bundle/prompts`（`Path.home` ではなく `os.path.expanduser` で展開） |
| 設定あり | 環境変数の値をそのまま `Path` に渡す |
| 空文字で設定 | デフォルトに戻らず空パスとなり、相対パスとして現在の作業ディレクトリを基点にする |

値の trim、正規化、ディレクトリ存在確認、別値への fallback はこの読み取り箇所にはありません。ファイルを開く段階で失敗した場合の専用処理もなく、通常の Python 例外になります。

## 有効になる条件

`metal/tests/serve_probe.py` を直接実行し、prompt ID ファイルを読む分岐に入る場合に限ります。位置引数 `NAME` のコロンより前の部分がすべて数字なら `N[:src]` 形式として扱い、`src` を省略すると `agent` を使います。この場合は `<STRATA_PROMPTS>/<src>.prompt.ids` を読み、JSON 配列として読めなければカンマ・空白区切りの整数として解釈します。それ以外は `<STRATA_PROMPTS>/<NAME>.prompt.ids` を読み、同様に JSON 配列または区切りテキストとして解釈します。

数値形式では、JSON 配列・整数列の先頭 `N` 個を使います。読み取った ID は tokenizer を通じて serve engine への入力 prompt となります。`STRATA_PROMPTS` 自体は子プロセス環境を設定する値ではなく、プローブ Python プロセスがファイル選択に使います。

## 実行時の詳細

環境変数はスクリプト実行中、prompt ファイルを選ぶ各分岐で `os.environ.get` により読み取られます。両分岐とも同じ未設定時既定ディレクトリを使います。パスに付けるファイル名は上記の `src` または `NAME` から作り、拡張子は `.prompt.ids` です。

ファイルを開いた後、JSON decode の例外が発生した場合に限って区切り整数形式へ fallback します。ファイル未検出などの `read_text()` 例外はその前に発生するため、この fallback では処理されません。プローブの実行例では環境変数でディレクトリを渡していますが、ソース内には標準出力ログ等の `STRATA_PROMPTS` 専用メッセージはありません。

## 根拠

- `metal/tests/serve_probe.py:2-8`: このスクリプトが Metal serve regression probe であること、環境変数を指定する実行例、および通常の unit test ではない旨。
- `metal/tests/serve_probe.py:33-47`: `NAME` の分岐、既定ディレクトリ、ファイル名、JSON / 区切り整数の読み取り。
- `metal/tests/serve_probe.py:48-55`: 読み込んだ prompt ID を engine の `generate` に渡す流れ。
- 対象リポジトリ全体の `STRATA_PROMPTS` 完全一致検索では、上記ファイル以外に参照はありません。テスト専用コードは製品挙動の実装根拠にしないという調査基準に従い、製品側の挙動は未確認としています。
