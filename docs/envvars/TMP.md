# `TMP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリや OS が独自に読む場合の動作は対象外。

## 役割

`TMP` は `strata-vision` がテキストモデルの GGUF ヘッダーだけを複製する一時ファイルの保存先候補です。優先順位は `TMPDIR`、`TEMP`、`TMP`、`/tmp` で、`TMP` が選ばれるのは先行する二つが未設定または空文字のときです。通常の engine が直接読む設定ではありません。

Strata serve の HIP 起動経路では、子プロセスへ渡す `TMP` のディレクトリが書き込み可能かも確認します。使えない場合は、書き込み可能な代替ディレクトリへ環境値を差し替えます。

Desktop の agent 起動処理は `TMP` を継承対象の環境変数に含め、成果物追跡では `TMP` が指すパスを除外対象に加えます。

## 値と判定

| 状態 | `strata-vision` の一時ディレクトリ選択 |
|---|---|
| `TMPDIR` が非空 | `TMP` は参照しない。`TMPDIR` を使う |
| `TMPDIR` が未設定または空、`TEMP` が非空 | `TMP` は参照しない。`TEMP` を使う |
| `TMPDIR` と `TEMP` が未設定または空、`TMP` が非空 | `TMP` の文字列をそのまま使う |
| 三つとも未設定または空 | `/tmp` を使う |

値の trim、存在確認、書き込み確認、パス正規化はこの C++ 関数では行いません。選ばれたディレクトリ文字列の末尾に `/strata-vision-meta-<PID>.gguf` を連結します。したがって `TMP` が非空でも、ディレクトリが存在しない・書けない場合には一時ヘッダーの作成に失敗し得ます。

## 有効になる条件

- `tools/vision/strata_vision` が、画像のモデル読み込みで `strata_open_text_model()` を呼ぶ経路でのみ読み取ります。vision encoder をビルドしていない場合や、画像 encoder を起動しない場合にはこの読み取りはありません。
- `TMP` の候補順位は `TMPDIR` と `TEMP` より低く、これらが非空なら `TMP` の値は無視されます。比較は空文字かどうかだけで、大文字小文字や内容の形式は検査しません。
- Strata serve は起動環境をコピーし、設定の `env` を重ねた後に vision encoder へ渡します。vision 固有の環境処理は GPU 可視デバイス変数を扱うもので、通常 `TMP` はそのまま継承されます。
- serve の `hip_env_guard()` は backend が `hip` のときだけ呼ばれます。`TMP` を含む `TEMP`・`TMPDIR` の値が非空で、指す場所が書き込み不可なら、ログの親ディレクトリ配下の `tmp`、次に serve の `ROOT/tmp` を作成して書き込み確認し、最初に使えた場所で該当する環境値を置換します。どちらも使えなければ値は置換されず、警告を stderr に出します。値が空の場合、このチェックの対象にはなりません。
- Desktop agent の `agentEnvironment()` は起動元環境から許可リストに一致するキーを選び、`TMP` を Harness 子プロセスへ渡します。追加環境 (`extra`) に同名キーがあればそちらが優先します。agent bridge の `trackerFolders()` は truthy な `env.TMP` を成果物追跡の除外パスに加えます。この処理は追跡対象を定めるもので、agent の一時ファイル置き場を `TMP` に変更するものではありません。

## 実行時の詳細

`strata_open_text_model()` は `TMPDIR`、`TEMP`、`TMP` の順に `std::getenv()` し、未設定または空文字なら次候補へ進みます。選んだ場所に PID を含む名前で GGUF ヘッダーの一時コピーを作り、作成できた場合はそのファイルを vocab-only モデルとして読み込みます。コピーに失敗した場合は元のモデルファイルを直接読み込む経路を試します。コピー経路の後は一時ファイルを `std::remove()` します。`TMP` を選んだ後に自動でディレクトリを作成する処理はありません。

HIP serve の環境ガードが値を差し替える場合、stderr の文言は `TMP=<値> is not writable: using <代替先>` です。代替先が見つからない場合は `TMP` などの該当変数名を列挙して `not writable (AMD's runtime needs a writable temporary folder)` と出力します。このガードは書き込みテストに `tempfile.TemporaryFile(dir=p)` を使います。

画像ツールの一時ディレクトリ選択は関数呼び出しごとで、値をキャッシュしません。HIP guard はサーバー起動時に作る engine 子環境だけを変更し、サーバープロセス自身の環境は変更しません。Desktop agent の `TMP` 引き継ぎと追跡除外は、それぞれ Harness 起動時と成果物追跡時に使われます。

## 文書との照合

`docs/DETAILS.md` の vision 設定説明に `TMP` の選択規則は記載されていません。上記はソース上で確認できた適用範囲です。serve 側の HIP ガードの説明は Python の実装コメントと実処理を根拠にし、HIP runtime 内部の挙動そのものは説明していません。

## 根拠

- `tools/vision/gguf_meta.h:135-155` — `TMPDIR` → `TEMP` → `TMP` → `/tmp` の選択、一時 GGUF 名、読み込みと削除、直接ロードへの fallback。
- `tools/vision/strata_vision.cpp:208-212` — 画像 encoder の起動時に `strata_open_text_model()` を呼ぶ。
- `serve/server.py:3500-3537, 3540-3578, 8344-8352` — serve の子環境構築、HIP guard の条件と処理、Strata engine 起動時の呼び出し。
- `serve/server.py:3540-3578` — HIP backend 向けの一時ディレクトリ書き込み確認、環境値の置換と stderr 出力。
- `apps/host/server/agent/harness-runtime.mjs:20-36,75-83` — `TMP` を許可リストから Harness 子プロセスへ渡す処理。
- `apps/host/server/agent/agent-bridge.mjs:126-135,355` — `TMP` を成果物追跡の除外パスに加え、tracker に渡す処理。
