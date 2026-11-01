# `GGUF_PY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

同梱の DeepSeek V4.1 参照スクリプト `tools/dsv41/ref_gguf.py` が、Python パッケージ `gguf` の import に失敗したとき、llama.cpp checkout 内の `gguf-py` ディレクトリを追加検索するために読みます。Strata の通常エンジン、サーバー、CLI が読む変数ではありません。参照スクリプトのデータ型の変換で `gguf-py` の dequantizer が必要になった場合に限られます（`tools/dsv41/ref_gguf.py:67-92,95-110,148-150,195-207`）。

## 値と判定

| 状態 | 処理 |
|---|---|
| `gguf` を最初の import で読み込める | `GGUF_PY` は読みません。 |
| import に失敗し、変数が未設定または空文字 | 空の候補として無視し、`~/llama.cpp/gguf-py` だけを検索候補にします。 |
| import に失敗し、変数が空でない | 値をそのままディレクトリ候補として使い、そのパスがディレクトリなら `sys.path` の先頭へ挿入します。存在しないパスやディレクトリでない値は無視します。 |

文字列を数値や真偽値へ変換せず、空文字かどうかと `os.path.isdir` の結果だけで判定します。`~` の展開や相対パスの補正はこの値には行いません。環境変数候補の後にもホーム配下の既定候補を検査します。候補ごとに `sys.path.insert(0, ...)` するため両方が有効ならホーム候補が先に検索されます（`tools/dsv41/ref_gguf.py:98-109`）。

## 有効になる条件

`RefGguf` の forward が、組み込み変換を持たない量子化型を変換するとき `dequant()` から `gq_values()` が呼ばれます。`Q6_K` の engram 行も `q6k_rows()` 経由で同じ helper を使います。F32、F16、BF16、Q8_0、MXFP4、MXFP8 は `dequant()` 内の別処理に入るため、これらの型の変換では `GGUF_PY` に到達しません（`tools/dsv41/ref_gguf.py:67-92,95-110,148-150,195-207`）。

このスクリプトは `python tools/dsv41/ref_gguf.py --pack ... --ids ...` として起動する参照・診断用ツールです。CLI に `GGUF_PY` の上書き引数はありません。デバイス指定 `--dev`（既定 `cuda:0`）は別の引数で、パス選択には関与しません（`tools/dsv41/ref_gguf.py:3-10,266-274,302-303`）。

## 実行時の詳細

各 `gq_values()` 呼び出しでまず `import gguf` を試し、失敗した場合だけ環境変数とホーム配下の候補を調べてから再度 import します。成功したパッケージは Python の import 機構により以後の呼び出しで再利用されるため、通常は最初に `gguf` が必要になった時点の環境・検索パスが選択に影響します。この helper 自身には値を保存する static cache はありません。

候補の追加後も `gguf` を import できない場合、または型名が `gguf.GGMLQuantizationType` にない場合は `SystemExit` を発生させ、`<tensor>: dtype <型> (no gguf-py with a dequantiser for it: GGUF_PY=<llama.cpp>/gguf-py)` を表示します。候補パスの無効さだけでは即時終了せず、ホーム候補も試します。dequantizer の実行時エラーなど、ここで捕捉している `ImportError` / `KeyError` 以外の例外はこの終了メッセージには変換されません（`tools/dsv41/ref_gguf.py:98-110`）。

## 根拠

- 環境変数の唯一の読み取りと import 失敗時の候補検索・終了経路: `tools/dsv41/ref_gguf.py:95-110`。
- GGUF tensor の型別変換と helper 呼び出し: `tools/dsv41/ref_gguf.py:67-92`。
- Q6_K engram 行からの helper 呼び出し: `tools/dsv41/ref_gguf.py:148-150,195-207`。
- 参照スクリプトの実行方法と CLI 引数: `tools/dsv41/ref_gguf.py:3-10,266-303`。
