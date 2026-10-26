# `TEMP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Strata が `TEMP` を明示的に参照する箇所は、HIP エンジン起動前の一時ディレクトリ検査と、画像エンコーダーが GGUF のメタデータだけを一時ファイルに保存する処理です。前者は `TEMP` が書き込み不可のとき子エンジンへ渡す値を差し替え、後者は一時ファイル名の親ディレクトリ候補を選びます。通常の Strata CUDA エンジンの動作を直接切り替える設定ではありません。

## 値と判定

- HIP 用の `child_env()` は親プロセスの環境をコピーし、設定プロファイルの `env` があればその値で上書きします。`TEMP` は文字列のまま扱われ、空白除去やパス正規化はしません。
- `hip_env_guard()` は `TEMP` が空文字でない場合に限り、そのディレクトリで `tempfile.TemporaryFile()` を作れるか確認します。未設定または空文字は検査対象になりません。
- 画像エンコーダーの C++ 側では、`TMPDIR` が未設定または空文字なら `TEMP`、それも未設定または空文字なら `TMP`、最後に `/tmp` を使います。この選択ではパスの存在・書き込み可否・空白を事前検査しません。

## 有効になる条件

- サーバーの HIP backend では `child_env()` から `hip_env_guard()` が呼ばれます。CUDA backend ではこのガードを通らず、`TEMP` を修正しません。
- HIP 起動環境に `TEMP`、`TMP`、`TMPDIR` のいずれか書き込み不可の値がある場合、ガードはそれらの不正なキーを同じ代替ディレクトリへ変更します。1つでも該当すれば、書き込み可能な代替先を `cfg.log` の親の `tmp`、次に Strata の `ROOT/tmp` の順で探します。
- 代替先を作成・検査できない場合、元の環境値は残ります。ガードはエラー文字列を stderr に出しますが、この関数自体は終了や起動拒否を行いません。
- 画像エンコーダーでは `TEMP` より `TMPDIR` が優先されます。`TEMP` が空でなくても、`TMPDIR` が空でない場合はこの処理では使われません。

## 実行時の詳細

HIP の子エンジン環境は `child_env()` が起動ごとに組み立てます。環境値は親プロセスからコピーされた後にプロファイルの `env` で上書きされ、その環境に対して HIP ガードが動きます。書き込み不可の値を置換した場合は、変更された各変数について `strata serve: AMD: <変数>=<元の値> is not writable: using <代替先>` を stderr に出します。代替先が見つからない場合は `strata serve: AMD: <変数一覧> not writable (AMD's runtime needs a writable temporary folder)` を出します。

画像エンコーダーの `strata_open_text_model()` は選んだディレクトリに `strata-vision-meta-<PID>.gguf` を作り、GGUF のキー・値ヘッダーをコピーして語彙のみのモデル読み込みを試みます。一時ファイルを削除した後、ヘッダーコピー経由で読み込めなければ元のモデルファイルを直接開きます。`TEMP` のパスが無効な場合、ヘッダーコピーが失敗して直接読み込みへ進む可能性があります。

Python の `Vision.work_dir()` も `tempfile.mkdtemp()` を引数 `dir` なしで呼び、作成できた一時ディレクトリのパスに空白がある場合は cwd、Windows のシステムドライブ直下を順に試します。この箇所は Strata が `TEMP` を直接読むのではなく、Python の一時ディレクトリ選択に委ねています。

## 文書との照合

`docs/DETAILS.md`、`docs/AMD_HIP.md`、`docs/DOCKER.md` には `TEMP` の Strata 側処理を説明する記述は見つかりませんでした。上記は調査対象 HEAD のコードに基づきます。

## 根拠

- `serve/server.py:3499-3537` — 子プロセス環境の複製、設定値の上書き、および HIP backend でのガード呼び出し。
- `serve/server.py:3540-3578` — 一時ディレクトリ書き込み確認、代替先、値の置換、stderr ログ。
- `serve/server.py:7980-7985,8349-8352` — エンジン起動と `child_env()` の使用箇所。
- `serve/server.py:2582-2600` — 画像エンコーダー用ディレクトリの作成と空白パスの回避。
- `tools/vision/gguf_meta.h:136-155` — `TMPDIR`、`TEMP`、`TMP`、`/tmp` の優先順、一時 GGUF の生成・削除、読み込み fallback。
- `tools/vision/strata_vision.cpp:208-212` — `strata_open_text_model()` を画像エンコーダーの起動時に呼ぶ箇所。
