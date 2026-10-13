# `STRATA_SHARD1`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

同梱 Python ツール `tools/canonical_xcheck.py` が検査対象にする GGUF shard 1 のパスを指定します。Strata のエンジンやサーバーの実行時設定ではなく、この検証ツール専用です。環境変数の参照はリポジトリ全体でこのファイルの1箇所だけです。

## 値と判定

| `STRATA_SHARD1` の状態 | `--gguf` の既定値 |
|---|---|
| 未設定 | `<Strata の2階層上>/Q2_0/Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00001-of-00002.gguf` |
| 空文字 | 未設定時と同じ既定パス |
| 空でない文字列 | その文字列をパスとして使用 |

`os.environ.get("STRATA_SHARD1") or ...` のため、値の真偽値判定は Python の空文字判定だけです。`0`、`false`、空白を含む文字列などは空でない限りそのまま使われます。数値変換、パスの存在確認、独自の無効値 fallback はありません。相対パスなら Python プロセスのカレントディレクトリを基準に開かれます。

## 有効になる条件

`tools/canonical_xcheck.py` を実行し、CLI の `--gguf` を指定しない場合に限り、この値が使われます。`--gguf PATH` が指定されると argparse がその値で既定値を置き換えるため、環境変数より CLI 引数が優先されます。Strata 本体、`tools/pack_layer.py`、`tools/strata_pack.py` がこの環境変数を直接読む実装は確認できません。

## 実行時の詳細

モジュール読み込み時に環境変数を一度読み、モジュール変数 `SHARD1` に保存します。`main()` はこれを `--gguf` の argparse 既定値に設定し、選ばれたパスを `GGUFFile` と `open_shard()` に渡します。`open_shard()` はそのファイルをバイナリ読み取り専用で開いて mmap します。したがって、モジュール読み込み後にプロセス内で環境を変更しても `SHARD1` は更新されません。子プロセスへの伝播や環境変数を設定する処理はありません。

指定パスが存在しない、読めない、または有効な GGUF でない場合、この変数専用の警告や fallback はなく、ファイルオープンまたは GGUF 読み込みでエラーになります。ツールの通常の比較結果は stdout に `tools/canonical_xcheck.py PASS` または `FAIL` を出力しますが、これは環境変数の parse 結果を示すログではありません。

## 根拠

- `tools/canonical_xcheck.py:35-47` — モジュールの `REPO` と、環境値または開発用既定パスから `SHARD1` を作る箇所。
- `tools/canonical_xcheck.py:607-616` — パスを開き、読み取り専用 mmap にする箇所。
- `tools/canonical_xcheck.py:723-745` — `--gguf` の既定値・CLI 引数優先、および選択したパスの読み込み。
- `tools/canonical_xcheck.py:793-795` — 通常実行の結果表示と終了コード。
- `tools/canonical_xcheck.py:1-20` — ツールの用途と起動方法。

`docs/DETAILS.md` などの利用者向け資料には、この環境変数の説明は見つかりませんでした。ソース上の用途は上記の検証ツールに限定されています。
