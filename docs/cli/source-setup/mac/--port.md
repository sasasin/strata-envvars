# `--port`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（macOS の `./setup.sh` から委譲） |
| オプション | `--port` |
| 別名 | なし |
| 値 | `int` 型のポート番号。parser では範囲を検査しない |

## 役割

Metal エンジン用のモデルサーバーが待ち受けるポートを指定する。macOS では `terminal/setup.py` が Apple Silicon 向けの通常経路を `engine/metal/setup_mac.py` に委譲し、この parser が `--port` を受け取る。サーバー起動時には指定値を serve プロセスの `--port` に渡し、新規セットアップまたは `--setup` では設定ファイルと次回起動用スクリプトにも保存する。

## 使い方

```sh
# 新規セットアップでポート 8090 を設定し、完了後にサーバーを起動する
./setup.sh --model Qwen3.8-Flash-Next-Q4_K_M --port 8090

# すでにセットアップ済みなら、この起動だけポート 8090 を使う
./setup.sh --port 8090
```

モデル名は例示用で、実際に指定できる名前は同 revision の `MAC_MODELS` に従う。

## 値と既定値

- `argparse` の `type=int` で整数に変換される。整数に変換できない値は parser が拒否し、通常の argparse usage/error を表示して終了コード 2 となる（`engine/metal/setup_mac.py:375-403`）。
- Mac 用 parser 自体には既定値がない。既存設定をそのまま起動する場合、未指定なら保存済み設定の `port` が使われる。新規設定では未指定時に `8080` が選ばれる（`engine/metal/setup_mac.py:416-418,595-596`）。
- 値は `a.port or ...` で選択されるため、`--port 0` は OS に空きポートを割り当てさせる指定にはならない。既存設定の起動では保存済みポート、新規設定では `8080` に置き換わる（`engine/metal/setup_mac.py:324-325,418,595-596`）。
- Mac parser に数値範囲チェックはない。負数や 65535 より大きい値も整数として後段へ渡り、ソケット bind が失敗すれば serve 側でエラーになる。1024 未満のポートも parser は受け付けるが、macOS を含む Linux/macOS では通常、管理者権限なしの bind は拒否される（`terminal/serve/server.py:8824-8828`; `terminal/serve/server_parts/base.py:42-58`）。

## 実行時の動作

- 既存の Metal 設定があり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定されていない通常起動では、`--port` があればその値、なければ設定ファイルのポートを `start()` に渡す。この経路は設定ファイルを書き換えないため、指定値はその起動だけに適用される（`engine/metal/setup_mac.py:416-418`）。
- 新規セットアップまたは `--setup` では、指定値（偽値なら `8080`）を設定の `port` に格納し、`strata-<model>.json` と `run-<model>.sh` に反映する。次回起動用スクリプトは同じポートを `serve/server.py --port` に渡す（`engine/metal/setup_mac.py:593-613`; `engine/metal/setup_mac.py:243-245`; `terminal/setup.py:9149-9160`）。`--no-start` を併用すると設定・スクリプトは作成するが、その場ではサーバーを起動しない（`engine/metal/setup_mac.py:610-621`）。
- `--check` は Mac の適合性確認後に早期 return するため、ポートを使った起動・設定作成は行わない。`--update` もエンジン更新の処理後に早期 return し、モデルの設定作成や起動へ進まない（`engine/metal/setup_mac.py:429-432,479-495`）。
- 起動関数は `serve/server.py --engine strata --config <設定> --port <値>` を呼び出す。serve はそのポートで HTTP サーバーを bind し、起動成功後に URL を表示する。待ち受けアドレスは `--host` または設定の host があればそれに従い、どちらもなければ `127.0.0.1` である（`engine/metal/setup_mac.py:311-332`; `terminal/serve/server.py:8641-8647,8806-8808,8824-8828,9182-9190`）。

## 適用条件と副作用

- `terminal/setup.py` の macOS 委譲分岐で選ばれる Metal セットアップに適用される。Control アプリ経路と Hy4-Flash / Inkling-2-Mini のモデル経路はこの委譲条件から除外されている（`terminal/setup.py:11216-11220`）。
- ポートを指定してサーバーを起動すると、その TCP ポートを HTTP API と Web UI が使用する。ポートが他プロセスに使われている、OS が予約している、または権限がない場合は bind に失敗する。ポート競合は serve の事前 bind 検査でエラーになり、異なるポートを使うよう案内される（`terminal/serve/server.py:8824-8828`; `terminal/serve/server_parts/base.py:42-58`）。
- 新規設定時には設定 JSON と起動スクリプトのファイル作成・更新を伴う。既存設定を通常起動する際に `--port` を指定した場合は、設定ファイル自体には保存されない（`engine/metal/setup_mac.py:416-418,610-613`）。

## 出力とエラー

- 整数として不正な値は Mac parser の argparse エラーとなる。整数でも OS の bind に失敗すると、serve 側が `ap.error(...)` を呼び、port が使用中なら「already in use」と別ポートの利用を案内する。argparse のエラーは usage とエラーを stderr に出して終了コード 2 となる（`engine/metal/setup_mac.py:375-403`; `terminal/serve/server.py:8824-8828`; `terminal/serve/server_parts/base.py:42-58`）。
- 起動に成功すると、serve は実際に bind したアドレスとポートを `ready:` 行などに表示する（`terminal/serve/server.py:9182-9190`）。

## 根拠

- `terminal/setup.py:9205-9210,11216-11220` — macOS の通常経路を Metal 用 `setup_mac.py` に引数ごと委譲。
- `engine/metal/setup_mac.py:372-403` — Mac CLI parser。`--port` は `type=int`、範囲 validator なし。
- `engine/metal/setup_mac.py:416-418,593-621` — 既存設定の起動、新規設定の既定値、設定・スクリプト作成、`--no-start` 分岐。
- `engine/metal/setup_mac.py:311-332` — config fallback を含めた server subprocess の引数組み立てと起動。
- `terminal/setup.py:9149-9160` — 保存される起動スクリプトが serve にポートを渡す。
- `terminal/serve/server.py:8641-8659,8806-8808,8824-8828,9182-9190` — serve 側のポート parser、host fallback、bind 検査、起動後の表示。
- `terminal/serve/server_parts/base.py:42-58` — bind 失敗の分類とポート競合・権限エラーの案内。
