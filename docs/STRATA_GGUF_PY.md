# `STRATA_GGUF_PY`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの内部動作は対象外。

## 役割

llama.cpp 同梱の `gguf-py` パッケージがあるディレクトリを、Strata の Python 補助ツールに指定します。対象は主に GGUF のパック作成と MTP データ変換です。通常の Strata エンジン実行時の設定ではなく、C++/CUDA/HIP/SYCL エンジンからこの変数を読む箇所はありません。

直接読むのは `tools/_paths.py` の `gguf_py()` です。同関数を使う `tools/iq_pack.py`、`tools/mtp_pack.py`、`tools/mtp_rt.py` が選ばれたディレクトリを Python の import 検索パスへ追加します。

## 値と判定

値はパス文字列として扱われ、真偽値や数値への変換はありません。未設定または空文字なら最初の候補を飛ばします。空白の trim、`~` の展開、絶対パス化、環境変数展開は行いません。相対パスは Python プロセスのカレントディレクトリ基準で `Path` に渡されます。

候補は次の順で検査され、`<候補>/gguf` がディレクトリである最初の候補を採用します。

1. `STRATA_GGUF_PY` の値
2. Strata リポジトリ内の `third_party/llama.cpp/gguf-py`
3. 開発ツリー用の `.ref/llama.cpp/gguf-py`

変数に指定したパス自体が存在しない、またはその直下に `gguf/` がない場合、その候補は不採用となり、後続候補を試します。したがって無効な指定値だけで直ちに失敗するわけではありません。全候補に `gguf/` がなければ `SystemExit` となり、stderr に次の文言が出て終了コード 1 になります。

```text
llama.cpp's gguf-py was not found: run setup.py (it clones llama.cpp into third_party/), or set STRATA_GGUF_PY
```

## 有効になる条件

- 手動で `tools/iq_pack.py` を使う場合、量子化 tensor の dequantize または BF16 変換で `add_gguf_py()` が呼ばれます。入力が `F32`、`F16`、`BF16` の場合、`dequantize()` はその分岐内で `gguf-py` を使わず返るため、その呼び出しでは変数が評価されないことがあります。
- `tools/mtp_pack.py` と `tools/mtp_rt.py` は起動時に `add_gguf_py()` を呼びます。
- `tools/test_iq_pack.py` も import 時に同じ helper を使いますが、これはテスト専用コードであり、通常利用時の機能根拠にはしていません。
- セットアップのモデル準備段階では `setup.py` が `third_party/llama.cpp` を取得または再利用した後、子プロセス用環境を `dict(os.environ, STRATA_GGUF_PY=str(llama / "gguf-py"))` で作ります。このため、呼び出し元が設定した値はこの子プロセスではセットアップが選んだ pinned llama.cpp のパスに上書きされます。既存 pack の状態などにより変換コマンドを起動しない場合は、その実行ではこの変数による探索も起こりません。
- `setup.py` の `run()` は `subprocess.run(..., env=env)` に環境辞書を渡します。環境辞書は元の `os.environ` を複製してこの変数を上書きしたものなので、他の環境変数は継承されます。MTP の検証、pack 作成、tokenizer 作成、MTP pack/runtime 作成にも同じパスを渡します。

## 実行時の詳細

`gguf_py()` は呼び出しごとに環境変数と候補ディレクトリを調べます。プロセス内で結果をキャッシュしません。`add_gguf_py()` は選んだパスがまだ `sys.path` に含まれない場合に限り、先頭へ挿入します。これにより続く `import gguf` がその場所から探索します。変数をプロセス稼働中に変更した場合、次回の `gguf_py()` 呼び出しでは再評価されますが、既に import 済みの Python モジュールを切り替える処理はありません。

この変数が直接選ぶのはパッケージの探索先だけです。選択後に `import gguf` やその API が失敗した場合の fallback は `_paths.py` にありません。ツール本体または Python が通常の import エラーを出します。

## 文書との照合

`docs/ORCA.md`、`docs/ORCA_Q4_K_S.md`、`docs/UNSLOTH_Q4.md` は、手動 pack 作成時に `STRATA_GGUF_PY` で llama.cpp の `gguf-py` ディレクトリを指定できると案内しています。この記述は `_paths.py` の探索処理と一致します。一方、通常のセットアップ処理では同変数を外部から選ばせず、取得した pinned llama.cpp の場所を子プロセスに設定します。

## 根拠

- `tools/_paths.py:12-28` — 候補順、`gguf/` ディレクトリの存在確認、見つからない場合の終了、`sys.path` への追加。
- `tools/iq_pack.py:104-126` — 量子化値の変換時に helper を呼ぶ箇所と、浮動小数点形式の早期 return。
- `tools/mtp_pack.py:32-36`、`tools/mtp_rt.py:20-25` — ツール起動時の探索と `gguf` import。
- `setup.py:374-383` — 子プロセス実行時に指定された環境辞書を使う処理。
- `setup.py:1715-1753` — pinned llama.cpp のディレクトリを再利用または展開して返す処理。
- `setup.py:5517-5555` — セットアップが子プロセス環境に `STRATA_GGUF_PY` を設定し、pack / MTP ツールへ渡す処理。
- `docs/ORCA.md:21-22`、`docs/ORCA_Q4_K_S.md:17`、`docs/UNSLOTH_Q4.md:81-87` — 手動 pack 時の案内。
