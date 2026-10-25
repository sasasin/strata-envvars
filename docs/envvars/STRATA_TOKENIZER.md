# `STRATA_TOKENIZER`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

この変数は、Strata の通常実行時の設定ではありません。リポジトリ内の tokenizer / detokenizer テストが、テスト用の実 tokenizer として読む `tokenizer/` ディレクトリのパスです。対象の探索で値を読む実装は `tools/test_strata_tokenizer.py` と `serve/test_detok.py` だけでした。製品の実行ファイル、通常のサーバー起動コード、セットアップ処理には読み取り箇所がありません。

## 値と判定

| 呼び出し箇所 | 未設定・空文字 | 有効なパス | 無効なパス / 不足ファイル |
|---|---|---|---|
| `tools/test_strata_tokenizer.py:load_tokenizer()` | 環境変数を使わず、後述の llama.cpp GGUF 語彙へ fallback | 値が空でなく、`<値>/vocab.json` が通常ファイルならそのディレクトリを使う | `vocab.json` が通常ファイルでなければ GGUF 語彙へ fallback。`vocab.json` があっても `merges.txt` / `token_type.json` がなければ読み込み時に失敗する |
| `serve/test_detok.py:find_tokenizer()` | 候補を空文字として扱い、pack ディレクトリ等の候補を探す | `<値>/vocab.json` が存在すればそのディレクトリを最初の候補として使う | `vocab.json` がなければ次の候補を探す。ディレクトリが選ばれても `merges.txt` / `token_type.json` が欠けていれば tokenizer 構築時に失敗する |

どちらも値の数値変換、trim、大小文字変換は行いません。パス文字列として扱います。相対パスはテストプロセスの現在の作業ディレクトリを基準に `Path` で評価されます。空白だけの値は空文字ではないためパス候補として検査されます。

`tools/test_strata_tokenizer.py` の GGUF fallback は `STRATA_GGUF_PY` の候補の隣にある `models/ggml-vocab-qwen35.gguf`、リポジトリ内 `third_party/llama.cpp/gguf-py` の隣、`/opt/llama.cpp/gguf-py` の隣の順で探します。見つからなければ `load_tokenizer()` は `None` を返し、tokenizer を必要とするテストクラスは `SkipTest` になります。GGUF 用の oracle テストは別経路で、`STRATA_TOKENIZER` を使わず GGUF の `.inp` / `.out` を使います。

## 有効になる条件

- `tools/test_strata_tokenizer.py` または `serve/test_detok.py` を実行したときだけ参照されます。テストの説明にある実行例は `python -m unittest tools.test_strata_tokenizer -v` と `python -m unittest serve.test_detok` です。
- `tools/test_strata_tokenizer.py` では環境変数の tokenizer が存在しない場合でも、GGUF tokenizer が利用可能ならそちらで一部テストを実行します。
- `serve/test_detok.py` では環境変数の候補が使えない場合、リポジトリ内の `packs/*/tokenizer`、`pack/*/tokenizer`、コード中の固定 Windows パスの順に探します。いずれも見つからなければテストクラス全体が skip されます。
- Strata 本体が `STRATA_TOKENIZER` の値をサーバーや子プロセスに転送する処理は確認できません。

## 実行時の詳細

`tools/test_strata_tokenizer.py` は `load_tokenizer()` の呼び出しごとに `os.environ.get("STRATA_TOKENIZER")` を評価します。`Marks` と `Prompts` の `setUpClass()` がそれぞれこの関数を呼び、選んだ tokenizer をクラス属性に保持します。環境変数を設定しただけでは `Oracle.test_llama_cpp_vectors` の参照 tokenizer は変わりません。

`serve/test_detok.py` は `find_tokenizer()` の都度環境変数を読むため、import 時の `skipIf` 判定と `setUpClass()` の間で環境が変われば、二つの探索結果は異なる可能性があります。別の `real_tokenizer()` helper は最初の呼び出し結果をモジュール内の `_REAL` にキャッシュします。

環境変数によるログ出力、警告、外部プロセス起動はありません。パス上のファイル読込や JSON 解析に失敗した場合は通常の Python 例外になります。

## 根拠

- `tools/test_strata_tokenizer.py:1-10` — テスト専用であること、用途、GGUF fallback の説明。
- `tools/test_strata_tokenizer.py:30-49,142-166,178-187` — GGUF 候補探索、環境変数の判定、必要テストの skip。
- `tools/test_strata_tokenizer.py:145-150` — oracle テストが `STRATA_TOKENIZER` を使わず GGUF tokenizer を使うこと。
- `serve/test_detok.py:1-5,20-27,45-57,106-125` — detokenizer テスト専用の探索候補、skip、tokenizer のロードとキャッシュ。
- `serve/test_detok.py:255,278` — キャッシュする `real_tokenizer()` の呼び出し箇所。
