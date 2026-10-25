# `--config`（quick-benchmark）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh` / `BENCH.bat`（`tools/strata_bench.py` に委譲） |
| オプション | `--config` |
| 別名 | なし |
| 値 | 設定 JSON ファイルのパス（`FILE`）。parser 上の型・範囲検証なし |

## 役割

quick benchmark が起動する Strata サーバーのモデル設定 JSON を選びます。通常は設定内のエンジン実行ファイル・引数などを使ってサーバーを起動します。すでに対象サーバーが動いていれば、そのサーバーを使います。

このオプションは `strata bench run` の標準比較ベンチマークではなく、`bench.sh` / `BENCH.bat` が起動する `tools/strata_bench.py` のものです（索引: [`docs/cli/README.md`](../../README.md) の `quick-benchmark` 節）。

## 使い方

```sh
# Strata ルートで、指定した設定を使って quick benchmark を実行
./bench.sh --config strata-q4.json
```

Windows では同じ引数を `BENCH.bat --config strata-q4.json` に渡せます。両 wrapper は作業ディレクトリを Strata ルートへ移してから引数を Python スクリプトへそのまま渡します（`bench.sh:6-10`、`BENCH.bat:8-16`）。

## 値と既定値

- `FILE` は文字列として受け取られます。parser は拡張子、JSON schema、必須キーを検証しません（`tools/strata_bench.py:932-948`）。
- `--config` を省略し、`--url` も省略した場合、Strata ルート直下の `strata-*.json` を探します。`.shared-settings.json` で終わる名前、読めない/不正な JSON、`exe` がない設定、`args` が list でない設定は候補から除き、更新日時が最も新しいものを選びます。複数候補があると選んだファイル名を通知します（`tools/strata_bench.py:653-664,957-968`）。
- 指定した相対パスは、まずプロセスの現在ディレクトリから解決します。そのパスが存在しないときだけ Strata ルートを基準に再解決します。絶対パスはそのままです（`tools/strata_bench.py:959-963`）。wrapper 経由なら現在ディレクトリは Strata ルートです。
- `--config` の繰り返し指定に独自処理はありません。`argparse` の通常の単一値引数として解析されます（`tools/strata_bench.py:934,948`）。
- `--url` を使うと設定ファイルは起動サーバーの選択には使われません。ただし同時に `--config` を指定した場合は設定ファイルを先に読み込みます。`--url` と `--config` の両方を省略した場合だけ、設定ファイルの自動選択・読み込みを行わずに済みません（`tools/strata_bench.py:935,957-979`）。

## 実行時の動作

`--config` が指定されると、そのファイルが存在する通常ファイルかを確認して UTF-8 BOM を許容して JSON として読み込みます。ファイルが不在、または通常ファイルでない場合は stderr に設定がない旨を出し、終了コード `2` で終了します（`tools/strata_bench.py:959-973`）。

`--url` がなく、設定の port に Strata サーバーが応答していない場合、bench は `serve/server.py --engine strata --config FILE --port PORT` を子プロセスとして起動し、設定中の `host` と port を使って応答を確認します。設定 JSON はサーバーのエンジン設定（`exe`、`args`、`cwd` など）として渡されます。設定の相対 `exe` は server 側で `cwd` を基準に絶対パス化されます（bench: `tools/strata_bench.py:977-995`、server: `serve/server.py:8141-8142,8394-8404`）。`--port` が併用されると設定中の port に優先します（bench: `tools/strata_bench.py:936,977-979`）。

設定に `api_key` がある場合は接続キーの候補になります。明示した `--api-key`、または既定値として読み取った `STRATA_KEY` が空でなければそちらが使われます（`tools/strata_bench.py:938,974`）。

既定設定を自動選択する場合と異なり、明示した設定は `find_configs` の候補条件による事前検査を通りません。JSON の構文エラーは読み込み箇所で捕捉されず、設定オブジェクトの形式不足も bench 側では schema 検証されません（`tools/strata_bench.py:653-664,969-974`）。サーバー側では設定に従ってエンジンを起動し、設定エラーは `[strata] config ...` の形で終了させる経路があります（`serve/server.py:8394-8408`）。

## 適用条件と副作用

- `--url` がなく、設定に記載された接続先で Strata サーバーが既に動作している場合、bench はそのサーバーを使い、設定から新しいサーバーを起動しません。したがって、`--config` を指定しても稼働中サーバーの設定を差し替えません（`tools/strata_bench.py:983-995`）。`--url` を明示した場合はその URL に接続し、応答する Strata がなければ stderr に表示して終了コード `2` です（同: `975-987`）。
- 起動に使う設定に `args` 内の `--expert-profile-save FILE` または `--expert-profile-save=FILE` が含まれる場合、bench はその指定を除いた一時 JSON を OS の temp ディレクトリに作り、元の設定ファイルを変更せずに起動します。除去した旨を stderr に通知します（`tools/strata_bench.py:672-705`）。
- bench が起動したサーバーは、bench 終了時に停止されます。bench は同時に一時ディレクトリへサーバーログを書きます（`tools/strata_bench.py:992-999,1035-1037`）。
- ベンチマークが成功すると、結果レポートにも選択された設定由来の情報（モデル設定・起動引数など）が含まれます。設定中の secret/token/password 系キー、`log`、`cwd` はレポートの設定ビューから除外され、パスは一部の値でファイル名に短縮されます。出力先は既定で `bench/results` です（`tools/strata_bench.py:529-546,826-835,910-918,1017-1018`）。
- 不正な JSON は `--config` の読み込み時に `JSONDecodeError` となり、独自の利用者向けエラー処理や終了コード変換は確認できません（`tools/strata_bench.py:973`）。設定の JSON schema・キーごとの完全な受理規則はこのオプションの parser では検証されず、設定を消費する server の処理に依存します。

## 出力とエラー

- 指定ファイルが見つからない場合、または通常ファイルでない場合は、「このフォルダーに Strata モデルが設定されていない」旨を stderr に出し、終了コード `2`（`tools/strata_bench.py:969-972`）。
- `--config` による起動先 port が Strata 以外の応答を返す場合、port 指定を促すメッセージを stderr に出し、終了コード `2`（`tools/strata_bench.py:989-991`）。
- 起動サーバーが ready にならない場合、stderr に最後のログ行（最大 15 行）を表示して終了コード `1`（`tools/strata_bench.py:996-999`）。
- 明示した JSON の読み込み例外は捕捉されず、Python の例外出力になります（`tools/strata_bench.py:973`）。

## 根拠

- `tools/strata_bench.py:932-948` — parser 定義。値の型変換・既定値・alias は指定されていない。
- `tools/strata_bench.py:653-664,957-979` — 自動選択、明示パスの解決、存在確認、JSON 読み込み、port/host/key の利用。
- `tools/strata_bench.py:672-705,983-999,1035-1037` — 設定からのサーバー起動、profile-save の除去、一時ファイル、既存サーバー利用、起動待ち失敗、終了時停止。
- `serve/server.py:8141-8142,8394-8408` — server 側で設定 JSON を受け取り、設定の `exe` と `cwd` を使い、設定エラーを処理する箇所。
- `bench.sh:6-10`、`BENCH.bat:8-16` — wrapper がルートへ移動して引数を委譲する箇所。
