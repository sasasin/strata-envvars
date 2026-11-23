# `OWN5_DUMP_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

これは製品版 Strata の環境変数ではなく、`terminal/tools/image/gate` の OWN-5 テスト専用ハーネスが stage-hook 付きの `sd-cli` コピーで使う出力先である。`stage_hooks.py` は pinned `stable-diffusion.cpp` のコピーへ hook を生成・挿入し、生成された C++ hook がこの変数を読み取る。通常の Strata 実行ファイルにこの hook が組み込まれる経路は、このソースからは確認できない（`terminal/tools/image/gate/stage_hooks.py:1-2,25-35,118-145`、`terminal/tools/image/gate/build_variant.py:1-9,28-30`）。

設定先では初期ノイズ、conditioning、DiT の入出力、latent、Qwen-Image-2.1 の位置埋め込み、VAE 入出力、および tokenizer 入力の dump 用ファイル名が定義される。hook は値を推論計算の入力として使わず、指定先へ書き出す（`terminal/tools/image/gate/stage_hooks.py:4-18,34-51,67-80,128-164`）。

## 値と判定

生成 C++ の `own5::env` は `std::getenv` の結果が null、または先頭文字が NUL の空文字なら null を返す。値の文字列比較、数値変換、パス検査はせず、空でない文字列全体をディレクトリ名として `"/"` とファイル名の前に連結する。従って `0`、`1`、`true`、`false`、空白を含む文字列も、空でなければ有効なパス文字列として扱われる。大文字小文字や数値としての妥当性は判定しない（`terminal/tools/image/gate/stage_hooks.py:33-38,45-51`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| stage-hook 付き `sd-cli` の生成コード | dump を行わない | 空でない任意の文字列（`0`、`1`、`true`、`/tmp/dump`） | 空文字。unset と同様に dump を行わない |

## 有効になる条件

- 実行する `sd-cli` が `stage_hooks.py` により hook を挿入されたコピーからビルドされていること。`build_variant.py` は `--noise` がない場合にそのコピーを作り、`stage_hooks.py` を適用する（`terminal/tools/image/gate/build_variant.py:22-30`）。
- hook が呼ばれる処理まで実行されること。通常のハーネスでは `run_set.py --dump` が各画像用の出力ディレクトリを作成して `OWN5_DUMP_DIR` を設定する。`--env OWN5_DUMP_DIR=...` だけでも基底環境には設定できるが、後続の `--dump` があればその値は画像ごとのディレクトリで上書きされる（`terminal/tools/image/gate/run_set.py:102-107,127-133`）。
- `te_tok_collect.py` は各子プロセスの一時ディレクトリを値に設定して起動する（`terminal/tools/image/gate/te_tok_collect.py:26-37`）。
- OS、GPU backend、モデル状態による `OWN5_DUMP_DIR` 自体の追加判定は生成 hook にない。どの hook 呼び出しに到達するかは実行する処理に依存する。

## 実行時の詳細

Python 側では `run_set.py` が `IM.image_env(cfg)` と `--env K=V` から基底環境を作り、各画像ごとにコピーした環境へ `--dump` 時のディレクトリを設定する。その環境を `subprocess.Popen(..., env=env)` で子 `sd-cli` に渡す。`te_tok_collect.py` も `os.environ` を複製して `OWN5_DUMP_DIR` を加え、`subprocess.run` に渡す（`terminal/tools/image/gate/run_set.py:102-107,127-149`、`terminal/tools/image/gate/te_tok_collect.py:36-37`）。

生成 C++ 側は `dump` と `dump_ids` の呼び出しごとに環境を再取得し、値を static cache しない。空でない値なら `<値>/<名前>.bin` と shape 情報等のファイルを開いて書き込む。`fopen` が失敗した場合はそのファイルへの書き込みを黙って飛ばす。生成コードはこの出力先ディレクトリを作らないが、`run_set.py --dump` は子プロセス起動前に画像別ディレクトリを作成する。`OWN5_DUMP_DIR` による timeout、終了、フォールバックはない（`terminal/tools/image/gate/stage_hooks.py:33-51`、`terminal/tools/image/gate/run_set.py:127-149`）。

## ログと測定値

`OWN5_DUMP_DIR` の未設定・空値やファイルオープン失敗を示すログは生成 hook にない。token dump の直後に終了する `OWN5_EXIT_AFTER_TOKENS` は別変数であり、設定時は `OWN5: exit after the token dump` を stderr に出して `exit(0)` する。この終了条件は `OWN5_DUMP_DIR` の値判定ではない（`terminal/tools/image/gate/stage_hooks.py:45-52`）。

## 根拠

- 読み取りとファイル出力: `terminal/tools/image/gate/stage_hooks.py:25-51`
- hook の生成・挿入箇所: `terminal/tools/image/gate/stage_hooks.py:118-164`
- テスト用ビルド経路: `terminal/tools/image/gate/build_variant.py:1-9,22-30`
- 子プロセスへの設定・転送: `terminal/tools/image/gate/run_set.py:102-107,127-149`; `terminal/tools/image/gate/te_tok_collect.py:26-37`
