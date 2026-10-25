# `--offline`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--offline` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると有効になる |

## 役割

サーバーを strict offline モードで起動する。サーバー自身によるリモート画像 URL の取得を拒否し、エンジンなどの子プロセスに offline 環境変数を渡す。MCP サーバーや `before_load` コマンドのようにネットワークを使いうる構成は起動前に拒否する。

このフラグはネットワーク接続そのものを OS レベルで遮断するサンドボックスではない。環境変数を無視して直接ソケットを開く子プロセスや、独自のネットワークスタックを持つ既ロード済みライブラリまでは遮断しない。また DNS lookup もブロックしない。

## 使い方

```sh
strata serve --profile /path/to/run-config.json --offline
```

`--profile` は必須で、`--config` は同じ引数の別表記。`--offline` 自体に値は付けない。`strata serve --plan` と組み合わせると起動せず有効設定を確認できるが、offline と両立しない構成は plan 表示より前に拒否される。

## 値と既定値

- CLI parser は `argparse` の `store_true`。CLI で省略した場合は `False`、指定時は `True` になる。正のフラグだけがあり、CLI から設定値を明示的に false にする `--no-offline` はない。
- 実効値は、`--offline` が指定されていれば `True`、そうでなければ保存済み profile の `offline`、run config の `offline`、既定値 `False` の順に決まる。従って CLI での省略は保存済み profile や run config の `offline: true` を無効化しない。
- `strata profile set NAME offline=true|false` で保存する値は真偽値のみ受理される。

## 実行時の動作

CLI は実効値を validation し、有効なら内部の `serve.server` 起動引数に `--offline` を追加して転送する。`--plan` の結果には `effective.offline` と値の出所が含まれる。

server は起動前に MCP サーバーまたは `before_load` コマンドがある構成を拒否する。さらに offline policy の事前検査で、設定が `images.remote_sources`、`images.allowed_hosts`、`images.url`、または対応する `vision` 設定を許可している場合も拒否する。構成が通ると、エンジンおよび replica の子プロセス環境に offline policy を適用する。例として Hugging Face／Transformers の offline 指定、pip の index 無効化、テレメトリ抑止、proxy 環境変数のクリアと `NO_PROXY=*`、`STRATA_OFFLINE=1` が設定される。run config の `env` より後に適用されるため、同名変数で上書きできない。

画像を含む要求では、画像ソースに `http://` または `https://` があればダウンロード前に拒否する。`data:` 画像やローカルファイルはこの URL 拒否条件には該当しない。ローカル API への接続は引き続き可能で、到達範囲は `--host` とポート設定に従う。

## 適用条件と副作用

- Strata エンジン起動で使う通常の `strata serve` 経路に加え、server 自身の画像 URL 検査にも適用される。`--engine mock` でも server の offline フラグと画像検査は有効だが、エンジン子プロセス向け環境変数の適用は Strata エンジン経路に関するもの。
- MCP、`before_load`、リモート画像ソースを要求する profile では起動が失敗する。ローカル画像や `data:` 画像を使うには、リモート画像設定が profile に残っていないことも必要。
- 子プロセスが環境変数に従わず自分で通信する場合は防げない。完全な通信遮断や OS サンドボックスを保証しない。
- 通常のローカル server API 通信は無効にならず、サーバーの bind address も変更しない。

## 出力とエラー

- `strata serve` の事前検査が拒否した場合、既定の human 出力では `strata: <理由>` を stderr に出し、終了コード 2 を返す。`--output json` では JSON error、`--output jsonl` では `failed` event と終了コードを出す。
- 通常の画像要求でリモート URL が使われた場合、server は `offline mode cannot download an image URL; send a data: image instead` の `ValueError` を発生させる。tool が返した画像 URL は同じ理由をログに出し、その画像を prompt からテキスト注記へ置き換える。server の内部 CLI parser による起動時拒否は argparse の usage error 経路。

## 根拠

- Terminal parser と help 文: `strata_cli/cli.py:46-67`。`--offline` は `store_true`。
- 実効値の優先順位・CLI false の扱い・profile/run config validation: `strata_cli/cli.py:745-779`。profile 値の真偽値 validation: `strata_control/profiles.py:25-27,88-95,115-116`。
- server 引数への転送と plan 内容: `strata_cli/cli.py:782-826`。
- CLI の事前エラー表現: `strata_cli/cli.py:527-533,829-835,915-955,2166-2173`。
- server parser: `serve/server.py:8171-8172`。起動前の MCP／`before_load`／remote-source 検査: `serve/server.py:8329-8341`、`strata_control/offline.py:139-166`。
- 子プロセス環境への policy 適用と適用順: `serve/server.py:3499-3527,7980-7984,8348-8351`。設定値: `strata_control/offline.py:44-61`。
- Service への flag 設定とリモート画像拒否: `serve/server.py:8443-8445,4802-4813,4833-4837`。
- policy の許可 URL と制約: `strata_control/offline.py:90-119,169-176`。

調査は指定 checkout のソースに限定した。実際の Release artifact や全 OS・全モデルでの通信遮断は検証していない。
