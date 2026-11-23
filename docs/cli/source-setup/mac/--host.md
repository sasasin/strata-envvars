# `source-setup`（mac）`--host`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（`setup.py` から委譲） |
| オプション | `--host` |
| 別名 | なし |
| 値 | 値を取る文字列。parser に選択肢・形式・範囲の指定はない |

## 役割

Apple Silicon の Mac でモデルをセットアップするとき、生成するモデル設定にサーバーの bind address を保存する。サーバーは保存値を使って待受けるため、loopback に限定するか、他のインターフェースでも接続を受けるかを決められる。

## 使い方

```sh
# Mac 上でセットアップし、サーバーをこの PC だけで待ち受ける
./setup.sh --host 127.0.0.1

# セットアップし、全 IPv4 インターフェースで待ち受ける
./setup.sh --host 0.0.0.0 --api-key 'replace-with-a-long-secret'
```

`setup.py` は Mac 経路で引数を `engine/metal/setup_mac.py` にそのまま渡す。`setup_mac.py` の parser は `--host` を値付き引数として登録し、セットアップ後に設定へ保存する（`terminal/setup.py:9206-9210`、`engine/metal/setup_mac.py:375-403`、`engine/metal/setup_mac.py:602-611`）。

## 値と既定値

- `--host` は `argparse` の文字列値で、choices や独自 validation はない。省略時はセットアップが `host` キーを書かず、サーバー側で設定値もなければ `127.0.0.1` になる（`engine/metal/setup_mac.py:382`、`terminal/serve/server.py:8808`）。
- 設定へ値をコピーする条件は `if a.host` のため、空文字列は保存されない（`engine/metal/setup_mac.py:602-603`）。
- ヘルプ文言では `127.0.0.1` をこの Mac のみ、`0.0.0.0` を全 IPv4、`::` を全 IPv6 インターフェースとして示す。setup parser 自体はこれら以外の文字列も拒否しない（`terminal/setup.py:11283-11284` と対照）。
- 同じ `--host` を複数回指定した場合は通常の `argparse` の単一値引数として最後に解析された値が残る。Mac parser で追加の重複指定処理はない（`engine/metal/setup_mac.py:382`）。

## 実行時の動作

モデルのセットアップ経路では、真偽値として空でない `a.host` を生成する `strata-<model>.json` の `host` キーに入れ、その設定を書き出してからサーバーを起動する（`engine/metal/setup_mac.py:593-611`、`engine/metal/setup_mac.py:619-621`）。設定ファイルは一時ファイルに書いてから置換されるため、再セットアップで同じモデル設定を更新するときは設定全体が置き換わる（`terminal/setup.py:7447-7453`）。

既に Metal 設定があり、実行が通常起動条件に該当すると、`main()` は既存設定で `start()` へ戻り、モデル設定を作り直す処理を通らない。その場合 `--host` は設定変更に使われない。`--setup`、`--model` などでセットアップ処理へ進むときに設定へ反映される（`engine/metal/setup_mac.py:416-418`）。サーバー起動時は CLI の `--host`、設定 JSON の `host`、`127.0.0.1` の順に選択し、Mac 起動ラッパーは設定 JSON を渡す（`engine/metal/setup_mac.py:311-332`、`terminal/serve/server.py:8808`）。

## 適用条件と副作用

- `0.0.0.0` や `::` など loopback 以外の address は他端末から到達可能な待受けを意図する。API key は Mac parser では強制されないが、共有ネットワークでの利用時に指定する例を推奨する。サーバーは loopback 以外で待ち受け、API key がなければ警告を表示する（`terminal/serve/server.py:9191-9201`）。
- 値が実際に bind 可能かはサーバー起動時に OS の socket bind で確認される。起動前の preflight が `OSError` になると `listen_problem()` の説明を usage error として出す（`terminal/serve/server.py:8824-8828`）。
- 誤ったホスト文字列の具体的な受理範囲や各 macOS の bind 挙動はこの parser では定義されないため、ここでは列挙しない。

## 出力とエラー

セットアップ後のサーバーは待受 URL を標準出力へ表示する。loopback 以外の場合、他端末向け URL も表示し、API key がなければ警告を出す（`terminal/serve/server.py:9182-9201`）。bind 失敗は上記 preflight のエラー経路を通る（`terminal/serve/server.py:8824-8828`）。

## 根拠

- `terminal/setup.py:9206-9210` — Mac（Apple Silicon）で `engine/metal/setup_mac.py` を呼び出す委譲経路。
- `engine/metal/setup_mac.py:375-403` — Mac parser と `--host` 登録、未知引数の警告。
- `engine/metal/setup_mac.py:416-418` — 既存モデルの通常起動経路。
- `engine/metal/setup_mac.py:593-621` — host をモデル設定に追加し、設定を保存して起動する経路。
- `terminal/setup.py:7447-7453` — 設定 JSON の一時ファイル経由の置換。
- `terminal/serve/server.py:8808-8828` — host の優先順位、API key 検証後の bind preflight と失敗処理。
- `terminal/serve/server.py:9182-9201` — bind 実行、待受 URL とリモート接続時の表示・警告。
