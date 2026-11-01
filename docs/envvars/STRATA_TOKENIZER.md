# `STRATA_TOKENIZER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はなかった。

## 役割

この名前を読むのは tokenizer のユニットテストだけで、通常の Strata 実行やサーバー起動の環境変数設定ではありません。テスト時に pack の `tokenizer/` ディレクトリを指定し、テスト用 tokenizer を読み込むために使われます。

完全一致検索で確認できた読み取りは `tools/test_strata_tokenizer.py:39` と `serve/test_detok.py:21` の二箇所です。`serve/test_server.py:2142-2148` もテストとして `load_tokenizer()` を呼びますが、環境変数はその helper 内で読み取られます。サーバー本体は `--tokenizer` 引数と設定ファイルの `tokenizer` を使います（`serve/server.py:9004-9005,9148-9167`）。調査対象ソースには `STRATA_TOKENIZER` を使う本番サーバー経路は見つかりませんでした。

## 値と判定

| 読み取り箇所 | 未設定・空文字 | 設定値が使われる条件 | 条件を満たさない場合 |
|---|---|---|---|
| `tools/test_strata_tokenizer.py:38-49` | `os.environ.get()` は `None` または `""` を返し、どちらも `if pack` が偽になる | 値が空でなく、そのパスに `vocab.json` が通常ファイルとして存在する | `STRATA_GGUF_PY`、同梱 `third_party/llama.cpp/gguf-py`、`/opt/llama.cpp/gguf-py` の順で GGUF tokenizer を探す（同ファイル `:30-35,48-49`） |
| `serve/test_detok.py:20-27` | 候補リスト先頭は `""`。空候補は `if c` で無視される | 候補パスに `vocab.json` が存在する（`.exists()`） | リポジトリ内の `packs/*/tokenizer`、`pack/*/tokenizer`、コード内の固定 Windows パスを順に確認する |

値の trim、正規化、文字列 parse、数値変換はありません。値はパス文字列として扱われます。複数候補が有効なら先に見つかったものを使うため、テスト helper では `STRATA_TOKENIZER` が既定候補より優先されます。存在確認は `vocab.json` だけです。これが見つかった後に `merges.txt` や `token_type.json` が欠けている、読めない、または `vocab.json` の JSON が不正な場合、読み込み例外は helper 内で捕捉されずテスト呼び出し元へ伝播します。

## 有効になる条件

適用先は `python -m unittest tools.test_strata_tokenizer` などの tokenizer テストと `python -m unittest serve.test_detok` の detokenizer テストです。値が有効でも、通常の Strata engine や HTTP server がこの環境変数で tokenizer を選ぶことはありません。

`tools/test_strata_tokenizer.py` では `Marks` と `Prompts` の `setUpClass()` が `load_tokenizer()` を呼びます。pack tokenizer も GGUF tokenizer も見つからなければ、同ファイル `:164-166,183-185` の `unittest.SkipTest` により当該クラスのテストが skip されます。`serve/test_detok.py` はモジュール読み込み時に `find_tokenizer()` を実行する `skipIf` を複数箇所に持ち、見つからなければ該当テストを `no pack tokenizer here` で skip します（同ファイル `:45-46,253-255,276-278`）。

CLI の `--tokenizer` は既定で `pack/full/tokenizer` を指し、設定ファイルに `tokenizer` があれば起動処理中にそちらで上書きされます（`serve/server.py:9004-9005,9148-9154`）。これは `STRATA_TOKENIZER` とは独立した経路です。

## 実行時の詳細

環境値は各 helper が呼ばれた時に `os.environ.get()` で評価し、環境から取得した文字列そのものを保持する共有キャッシュはありません。`tools/test_strata_tokenizer.py` はテストクラスの `setUpClass()` で tokenizer オブジェクトをクラス属性に置くため、そのクラスのテスト中は同じオブジェクトを使います。`serve/test_detok.py` の `find_tokenizer()` は呼ぶたびに候補を調べますが、`real_tokenizer()` は最初の結果（tokenizer または `None`）を `_REAL` に保持します（同ファイル `:107-125`）。また `skipIf` の判定はモジュール読み込み時に行われるので、その後に環境を変更しても既に決まった skip 判定は再評価されません。

Strata 本体のサーバーでは `--tokenizer` / 設定ファイルから選ばれたパスについて、Strata engine で `vocab.json` がなければ `argparse` のエラーとして停止します（`serve/server.py:9152-9155`）。この失敗経路は `STRATA_TOKENIZER` の読み取り結果によるものではありません。調査したテスト helper は読み込みエラーを独自の警告へ変換せず、上記のファイル読み込み・JSON 解析例外を伝播させます。

## 根拠

- `tools/test_strata_tokenizer.py:1-10,30-49,161-186`: テスト専用であること、環境値から pack tokenizer を選ぶ規則、GGUF fallback、tokenizer がなければ skip する条件。
- `serve/test_detok.py:1-5,20-27,45-57,107-125,253-278`: detokenizer テスト専用であること、候補順、読み込み、キャッシュ、skip 条件。
- `serve/test_server.py:2139-2148`: tokenizer テスト helper を使うテスト呼び出し。
- `serve/server.py:9004-9005,9148-9167`: 本番サーバー側の `--tokenizer` と設定ファイルの経路、および tokenizer ファイルの読み込み。
- 候補名は `docs/envvars/000_envvers.md:1580` にある。候補一覧に載る一方で、本番実行用の環境変数ではなく、同梱テスト用コードの入力として読まれている。
