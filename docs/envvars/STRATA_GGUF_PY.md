# `STRATA_GGUF_PY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 所有ソースを対象とし、外部ライブラリ側の挙動は含めない。

## 役割

同梱 Python 準備ツールが llama.cpp の `gguf-py` を探すとき、候補ディレクトリを最優先で指定します。見つかったディレクトリは `sys.path` の先頭に追加され、ツールが `gguf` モジュールを import できるようになります。これは Strata engine の実行時設定ではなく、GGUF の準備・変換などを行う Python ツールの依存モジュール検索です。

## 値と判定

`tools/_paths.py:34-40` は `os.environ.get("STRATA_GGUF_PY")` を候補リストの先頭に入れ、候補の `gguf` サブディレクトリが存在するか調べます。値は文字列として parse、trim、expanduser、絶対パス化されません。

| 状態 | 扱い |
|---|---|
| 未設定 | `None` となり、以降の既定候補を順に調べる |
| 空文字 | falsey な候補として無視され、以降の候補を調べる |
| 非空文字列で `<値>/gguf` がディレクトリ | 最優先で採用し、その値を文字列で返す |
| 非空文字列だが `<値>/gguf` がない | その候補を飛ばし、次の候補を調べる |
| 空白を含む文字列など | 加工せずパスとして検査する。存在要件を満たさなければ次候補へ進む |

指定先が無効でも直ちにエラーにはならず、後続候補が使われます。全候補で `gguf` パッケージを見つけられない場合は `sys.exit(...)` でエラーメッセージを出して終了します（`tools/_paths.py:41-44`）。CLI 引数による上書き処理はこの helper にはありません。

## 有効になる条件

この変数を読むのは `tools/_paths.py` の `gguf_py()` だけです。実際に影響するのは、この helper を使って `gguf-py` を読み込む同梱 Python ツールの経路です。C++ engine、OS/backend、GPU、ビルド macro、サーバーモードの条件はありません。

候補の探索順は次のとおりです（`tools/_paths.py:34-40`）。

1. `STRATA_GGUF_PY` の値
2. engine ルートの `third_party/llama.cpp/gguf-py`
3. 開発ツリー内の `.ref/llama.cpp/gguf-py`
4. `_install_dirs()` が返す各 install directory の `third_party/llama.cpp/gguf-py`

install 候補では `STRATA_INSTALL_DIR` があれば先に含め、その後 `strata_control.discovery` から install 先を得ようとします。discovery の import・探索中の例外は握りつぶされます（`tools/_paths.py:17-31`）。各候補はその下に `gguf` ディレクトリがある場合だけ有効です。

実利用箇所には `mtp_pack.py` と `mtp_rt.py` の起動時、`q8_dense_gguf.py` の起動時、`embd_bf16_pack.py` の `from_gguf()`、`nvfp4_local_pack.py` の slim / expert 変換経路、`iq_pack.py` の量子化値の dequantize / BF16 変換経路があります（各ファイルの `add_gguf_py()` 呼び出し）。特に `iq_pack.py` は F32/F16/BF16 を処理するだけの経路では helper を呼ばず、gguf-py を使う型の変換時に呼びます（`tools/iq_pack.py:104-126`）。

## 実行時の詳細

環境値は `gguf_py()` が呼ばれるたびに `os.environ.get()` で読み取られ、結果を static/global cache しません。したがって、同一プロセス内でも次の呼び出し時の環境値が探索候補に反映されます。選択結果は `add_gguf_py()` が `sys.path` の先頭に挿入します（`tools/_paths.py:47-50`）。既に同じ文字列が `sys.path` にあれば重複挿入しません。

Strata の setup は複数の準備経路で `dict(os.environ, STRATA_GGUF_PY=str(llama / "gguf-py"))` を作り、子 Python ツールへ渡します。この指定は setup を起動した親プロセスの値を上書きします。確認できる例は tokenizer 準備（`setup.py:8051-8056`）、モデル pack 準備（`setup.py:8980-8985`, `10022-10033`）、および Metal setup（`metal/setup_mac.py:476-480`）です。これらの子ツールは、渡されたパスに `gguf` ディレクトリがある場合に採用します。

選択先が見つからない場合の Strata 側の観測可能な失敗は、`llama.cpp's gguf-py was not found. Set STRATA_GGUF_PY ...` を含む `SystemExit` です。環境値自体に警告・ログを出す分岐はありません（`tools/_paths.py:38-50`）。依存モジュールの import 後に起きる処理や外部ライブラリ側の挙動は、この変数の Strata 側の効果には含めません。

## 根拠

- `tools/_paths.py:17-31,34-50` — install 候補、優先順、存在確認、失敗、`sys.path` への追加。
- `tools/iq_pack.py:104-126` — 型変換経路での遅延呼び出し。
- `tools/mtp_pack.py:32-36`, `tools/mtp_rt.py:22-25`, `tools/q8_dense_gguf.py:38-44`, `tools/embd_bf16_pack.py:55-63`, `tools/nvfp4_local_pack.py:451-458,517-522` — helper を使うツール経路。
- `setup.py:8051-8056,8980-8985,10022-10033`, `metal/setup_mac.py:476-480` — setup が子プロセス用環境にパスを設定する例。
