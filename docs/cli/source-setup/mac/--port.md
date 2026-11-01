# `--port`（source-setup / mac）

- 調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`
- 調査日: 2026-11-01
- 調査時の Strata working tree: clean（`main...origin/main`）
- scope: Apple Silicon の macOS で `setup.py` から委譲される `metal/setup_mac.py` の parser

## 役割

セットアップが生成する Metal 用 API server の待受ポートを指定します。すでに Metal 設定がある状態で通常起動する場合は、その起動時に server へ渡すポートを上書きします。

## 使い方

Strata source checkout のルートで実行します。

```sh
./setup.sh --port 8081
```

macOS では `setup.py` が Control install でない場合に引数を `metal/setup_mac.py` へそのまま渡します。ラッパー `setup.sh` 自体は `setup.py` を実行します（`setup.py:9068-9069`, `setup.py:7703-7707`, `setup.sh:12`）。

## 値と既定値

- parser は `--port` を `type=int` で受け取り、既定値は `None` です。明示的な範囲 validator はありません（`metal/setup_mac.py:327-335`）。
- 新しい設定を作る経路では `a.port or 8080` が使われるため、省略時と `--port 0` のどちらも 8080 になります。0 を OS の空きポート選択に使うことはできません（`metal/setup_mac.py:542-545`）。
- 数字でない値は argparse の型変換で拒否されます。負数や 65535 を超える値に対する独自チェックはありません。実際の bind 前に server が `Server((host, port), ...)` を試し、`OSError` が起きると argparse error として終了します。OS が受け付ける範囲外の値や使用中ポートではこの経路が失敗します（`serve/server.py:9143-9147`）。

## 実行時の動作と適用条件

- Metal 設定がすでにあり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定されていない場合、最初の既存設定で直ちに起動します。ここでは `--port` を `start()` に渡し、`serve/server.py --port` に指定値、または未指定なら設定の `port`（それもなければ 8080）を渡します。設定ファイル自体はこの分岐で書き換えません（`metal/setup_mac.py:369-371`, `metal/setup_mac.py:302-323`）。
- セットアップまたはモデル設定を作る経路では、指定値（truthy の場合）または 8080 を `strata-<model>.json` の `port` に保存し、生成する `run-<model>.sh` にも渡します。`--no-start` を同時指定すると設定とスクリプトを作成した後、server 起動を省略します（`metal/setup_mac.py:542-570`, `setup.py:7647-7659`）。
- server は `--port` を整数で受け取り、待受 socket を作ります。ポート 0 は server 単体なら OS 割当を許し、実際のポートを ready 出力に使いますが、`setup_mac.py` は 0 を 8080 に置き換えるため、この自動割当動作はこの source-setup option からは利用できません（`serve/server.py:8438-8444`, `serve/server.py:8985-8986`, `serve/server.py:9486-9494`）。
- 指定ポートがすでに使用中など bind に失敗した場合、モデル起動前の事前確認でエラーになります。server parser の `ap.error(...)` 経由で失敗します（`serve/server.py:9143-9147`）。

## 出力と副作用

新規設定時は設定 JSON と起動スクリプトが生成され、通常は server 子プロセスが起動してそのポートを listen します。成功時の server は実際の API URL とポートを標準出力に表示します（`metal/setup_mac.py:559-570`, `setup.py:7647-7659`, `serve/server.py:9486-9494`）。セットアップが既存設定から通常起動した場合、選択したポートはその起動プロセスにのみ渡され、保存済みの設定・生成済みスクリプトには反映されません（`metal/setup_mac.py:369-371`, `metal/setup_mac.py:315-323`）。

`setup_mac.py` 自身は不正な数値範囲を事前検証しません。bind 失敗時の具体的なエラー文は OS の `OSError` に依存するため、文書では固定文言を断定しません。一般的な setup failure helper はメッセージと修正ヒントを表示し、終了コード 1 で終了しますが、server のポート bind 失敗は server parser のエラー経路です（`setup.py:904-909`, `serve/server.py:9143-9147`）。

## 根拠

- parser、既存設定時の分岐、新規設定への反映: `metal/setup_mac.py:327-371`, `metal/setup_mac.py:542-570`
- macOS 委譲: `setup.py:7703-7707`, `setup.py:9068-9069`, `setup.sh:12`
- 起動時の server 引数と設定値の fallback: `metal/setup_mac.py:302-323`
- 生成スクリプト: `setup.py:7647-7659`
- server の port parser、bind 事前確認、起動出力: `serve/server.py:8438-8444`, `serve/server.py:8985-8986`, `serve/server.py:9143-9147`, `serve/server.py:9486-9494`

## 調査範囲

指定された macOS source-setup parser と、設定・起動先の server 実装を確認しました。macOS 上での実行や help 表示は行っていません。ポートの受理範囲を `setup_mac.py` が独自に制限する実装は確認できず、OS/socket の bind 可否が最終判定になります。
