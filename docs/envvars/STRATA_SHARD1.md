# `STRATA_SHARD1`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更は表示されなかった。

## 役割

同梱 Python 検証ツール `tools/canonical_xcheck.py` が読み込む shard 1 GGUF の既定パスを指定します。この変数は `canonical_xcheck.py` が使うもので、Strata エンジン本体の環境設定ではありません。ツールは指定した GGUF を開き、量子化形式の canonical 化と復元を参照値と照合します（`tools/canonical_xcheck.py:1-5,607-616,723-745`）。

## 値と判定

| 環境変数の状態 | `SHARD1` に設定される値 |
|---|---|
| 未設定 | `tools/canonical_xcheck.py:46-47` に組み立てられた開発レイアウト上の `Q2_0/Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00001-of-00002.gguf` |
| 空文字 | 未設定と同じ既定パス。`os.environ.get(...) or ...` の `or` により fallback する |
| 空でない文字列 | 文字列をそのままパスとして使用する。数値変換、trim、存在確認、相対パスの補正はこの箇所では行わない |

有効値の形式検査や値域はありません。空白だけの値も truthy な文字列としてそのまま使われます。`os.environ.get` の値は `SHARD1` モジュール変数に代入されるため、読み取りはモジュールの import 時に一度です。

## 有効になる条件

`python tools/canonical_xcheck.py` の実行で、CLI の `--gguf` を指定しない場合に環境変数値（またはその fallback）が使われます。`argparse` の `--gguf` の `default` が `SHARD1` なので、`--gguf PATH` の明示指定は環境変数で決まる既定値より優先します（`tools/canonical_xcheck.py:723-738`）。OS、GPU backend、ビルド macro、モデル実行状態による条件分岐はありません。

`tools/strata_pack.py` も `canonical_xcheck` から関数を import するため import 時に `SHARD1` の式は評価されますが、pack の入力は必須 CLI 引数 `--gguf` から渡され、pack builder はその値を `pack_layer.SHARD1` に設定します。したがって、この環境変数は pack の入力選択を決めません（`tools/strata_pack.py:39,220-237,429-445,250-255`）。

## 実行時の詳細

`canonical_xcheck.py` はモジュール初期化時に `STRATA_SHARD1` を取得して既定値を作り、引数解析後は `args.gguf` を入力として `GGUFFile` に渡します。通常モードでは `GGUFFile` で GGUF テーブルを読み、続けて `open_shard` でファイルを read-only mmap します。`--full` モードも同じ `args.gguf` を使います（`tools/canonical_xcheck.py:35-47,607-616,628-641,723-745`）。

ファイルを開く処理の周囲に、このツール独自の `STRATA_SHARD1` 警告や fallback はありません。指定先が存在しない・開けない場合は、`GGUFFile` または `open_shard` の `Path.open` / `open` で例外になります。ツール末尾は `main()` の戻り値を `SystemExit` に渡すため、処理中に捕捉されない例外は Python の traceback と非ゼロ終了として観測されます（`tools/gguf_reader.py:91-99`, `tools/canonical_xcheck.py:607-616,798-799`）。入力を読み込めた後の比較結果は `PASS` / `FAIL` を標準出力に表示し、それぞれ成功時 0、不一致時 1 で終了します（`tools/canonical_xcheck.py:718-720,792-799`）。

## 根拠

- `tools/canonical_xcheck.py:45-47` — 変数の唯一の直接参照と fallback パス。
- `tools/canonical_xcheck.py:723-738` — CLI `--gguf` の既定値と優先関係。
- `tools/canonical_xcheck.py:607-616,638-641,742-745` — 入力ファイルの読み込み経路。
- `tools/canonical_xcheck.py:718-720,792-799` — 比較結果・終了コード。
- `tools/gguf_reader.py:91-99` — GGUF リーダーによるファイル open。
- `tools/strata_pack.py:39,220-237,429-445,250-255` — import 時の参照と pack 側の CLI 入力経路。
