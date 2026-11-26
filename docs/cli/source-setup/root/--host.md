# `setup.py --host`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`./setup.sh`、Windows の `START-HERE.bat` などから起動） |
| オプション | `--host` |
| 別名 | なし |
| 値 | サーバーが bind するアドレス文字列。parser に型・選択肢の制約はない |

## 役割

起動する Strata API サーバーの待受アドレスを指定する。既定の `127.0.0.1` はこの PC 内からのみ接続できる。`0.0.0.0` は全 IPv4 インターフェース、`::` は全 IPv6 インターフェースで待ち受ける。LAN 上の他の端末から接続させる場合に使う設定で、`--api-key` を併用することが推奨される。

## 使い方

```sh
# この PC だけで使う場合（既定値。明示指定も可能）
./setup.sh --host 127.0.0.1

# 全 IPv4 インターフェースで待ち受ける。ネットワーク公開時は API key も設定する
./setup.sh --host 0.0.0.0 --api-key 'replace-with-a-private-key'

# 全 IPv6 インターフェースで待ち受ける
./setup.sh --host :: --api-key 'replace-with-a-private-key'
```

## 値と既定値

`setup.py` の `argparse` 定義に `type` や `choices` はなく、値は文字列として受け取る。省略時、サーバーは run config の `host`、それもなければ `127.0.0.1` を使う。新規セットアップ時に `--host` が指定されると、その値をモデルの run config に保存する。すでにモデルがある場合の通常起動でも指定値をそのモデルの設定へ保存し、以後の起動に引き継ぐ。空文字列は setup の `if a.host` 判定を通らないため設定を上書きしない。値をカンマ区切りなどで複数指定する処理や、host 固有の形式検証は setup parser にはない。

## 実行時の動作

新規モデルの設定生成では `setup.py` から `setup_config.config_for()` に渡された引数を使い、`a.host` が真なら `cfg["host"]` に格納する。特殊な Intel/Hy4/Inkling/Metal 経路でも同様に設定へ格納する箇所がある。run config は `write_setup_config()` が JSON として書き出す。`--no-start` を併用した場合は設定を書いた後に終了し、サーバーはこの実行では起動しない。

既存モデルを通常起動する経路では `--host` を `start(..., keep=...)` に渡す。値が以前の設定と異なれば run config を更新してから、`serve/server.py --config <run-config>` を起動する。setup は host を server の command line に再指定せず、server が設定ファイルから読み取る。server 側で明示的な `--host` が指定された場合はその値が優先され、なければ設定の `host`、最後に `127.0.0.1` が選ばれる。

## 適用条件と副作用

- `0.0.0.0` と `::` はネットワーク上の他端末から接続可能な待受先になる。API key は推奨されるが必須ではない。LAN 待受で key がない場合、server は警告を出す。Windows ではファイアウォールによって接続が遮断される場合も案内する。
- 不正なアドレス形式や、この PC に割り当てられていないアドレスは setup の parser では拒否されない。server 起動時、モデル読み込みの前に bind を試み、失敗すれば起動できない。指定値は bind 前に設定ファイルへ保存されるため、起動失敗だけでは値は取り消されない。
- 通常起動時の `--host` はその場限りの値ではなくモデル設定に保存される。セットアップ経路では新しい run config に反映され、既存 config の書き換えは `.bak` の保存対象になる条件がある。
- Apple Silicon の通常セットアップでは `setup.py` が `engine/metal/setup_mac.py` に処理を委譲する。このスコープの option 文書は `docs/cli/README.md` の `source-setup/mac/--host.md` を参照する。

## 出力とエラー

server は bind に成功すると待受アドレスと port を含む `ready:` 行を出力する。非 loopback アドレスでは他端末向け URL も表示し、API key がなければ警告する。bind の `OSError` は `listen_problem()` で説明文に変換される。アドレスがこの PC にない場合は `host` 設定または `--host` の確認を案内し、ポート競合の場合は既存 server の終了か別 port を案内する。起動前の preflight で失敗すると server の argparse error 経路になり、終了コード 2 となる。

## 根拠

- `terminal/setup.py:11444-11503` — root parser と `--host` の値説明。型・choices を付けず、`--api-key` との併用を推奨。
- `terminal/setup.py:11436-11437` — macOS の通常セットアップを Metal 専用 setup に委譲する条件。
- `terminal/strata_control/setup_config.py:521-533` — 標準の新規 run config に `a.host` があれば保存。
- `terminal/setup.py:9441-9448`, `10012-10018`, `10404-10411`, `10943-10950`, `11341-11360` — 特殊セットアップ経路で host を設定し、run config を書き出す箇所。
- `terminal/setup.py:11761-11775`, `8558-8563`, `8566-8596` — 既存モデル起動時に `keep` で受け渡し、値の変更時に設定ファイルへ保存。
- `terminal/setup.py:8601-8602` — server を `--config` 付きで起動。
- `terminal/serve/server.py:9161-9163`, `9324-9344` — server 側の CLI override、config、既定値の優先順と bind preflight。
- `terminal/serve/server.py:8779-8785`, `9721-9745` — bind 実行、ready/他端末向け表示、key 未設定時の警告。
- `terminal/serve/server_parts/base.py:42-62` — bind 失敗理由の分類と利用者向け案内。
- `terminal/setup.py:12538-12543` — setup 完了時に非 loopback host の他端末向け案内を出す条件。
- `terminal/setup.py:7715-7754` — config 書き込み時の既存設定引き継ぎ、変更時の `.bak` 保存。
