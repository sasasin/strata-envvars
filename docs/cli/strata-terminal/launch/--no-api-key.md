# `--no-api-key`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--no-api-key` |
| 別名 | なし |
| 値 | 値なしのフラグ（省略時 `False`） |

## 役割

`--access` でLAN・指定アドレス・Cloudflare tunnel・Tailscaleなど、このPCの外から到達できる共有先を選ぶとき、API keyを要求せずにモデルを提供する意図を明示します。鍵なしでも起動を拒否せず、利用者とサーバーログに警告します。`--access` を指定しない場合の既定は `local` なので、このフラグだけでは外部向けにlistenしません。

## 使い方

```sh
# LANに共有し、API keyなしを明示する（到達できる人は認証なしで利用可能）
strata launch --access lan --no-api-key --model q2_0

# 変更を加えず、鍵なし共有の警告を含む実行計画を確認する
strata launch --access cloudflare --no-api-key --model q2_0 --plan
```

## 値と既定値

引数値を取らない `store_true` フラグで、未指定時は無効です。parser側にこのフラグ固有の値validationはありません。`strata launch --api-key-env NAME` も指定した場合は、環境変数が空・未設定だと鍵なし指定の処理より前にエラーとなります（`terminal/strata_cli/launch/cmd.py:137-140,288-299`）。

## 実行時の動作

- 引数処理は既定設定または `--preset` から読み込んだ設定にフラグを重ねます。`--no-api-key` が有効で、同時に `--api-key` / `--api-key-env` が指定されていなければ、現在の起動設定の `api_key` を消し `no_key=True` にします。保存済みpresetに鍵があってもこの起動設定からは外れます（`terminal/strata_cli/launch/cmd.py:215-220,288-301`）。
- `--api-key` または `--api-key-env` も渡した場合は、鍵を保持して「key is kept」という警告を追加します。後段の `--new-key` は新しい鍵を作って `no_key=False` に戻すため、鍵なし指定より鍵ありになります（`terminal/strata_cli/launch/cmd.py:288-301,890-892`）。
- 非ローカル共有で鍵なし、かつ `no_key` の明示もない場合は既定で鍵を再利用または生成します。`--no-api-key` はその自動鍵生成を抑止します（`terminal/strata_cli/launch/cmd.py:402-411`）。
- 設定をrun configへ反映する際、共有先が非ローカルなら `api_key: "none"` を保存して意図的な鍵なしを表します。`local` ではこのフラグにより外部listenへ切り替わることはなく、run configから `api_key` を除きます（`terminal/strata_cli/launch/runner.py:724-739`）。
- `--plan` では鍵なしの注意がwarningsとして表示され、変更は行いません。実起動時はrun configを書いてserverを起動し、`--save-preset` も指定すれば `no_key` を含む起動設定をprivate presetへ保存します（`terminal/strata_cli/launch/cmd.py:897-924,962-966`; `terminal/strata_cli/launch/runner.py:2234-2238`; `terminal/strata_cli/launch/store.py:76-86`）。`--preset` とこのフラグだけなら、保存済みpresetの鍵設定を恒久変更せず今回の起動に重ねます。

## 適用条件と副作用

警告の種類は共有方法に応じて変わります。Cloudflareでは「公開アドレスを見つけたインターネット上の誰でも」利用できる旨、それ以外の非ローカル共有ではポートへ到達できる人が利用できる旨を通知します。警告は拒否ではありません。モデルとそのツールが利用可能になり、ツールはこのPC上のファイルを読み書きできると警告文は明記しています（`terminal/strata_cli/launch/settings.py:241-264`）。サーバーも非ループバックlistenかつ鍵なしの場合、到達先とともに警告を出します。managed serverの標準出力・標準エラーはserver logへ送られます（`terminal/serve/server_parts/http_api.py:228-235`; `terminal/serve/server.py:9730-9740`; `terminal/strata_control/runtime.py:1046-1074`）。

設定を書き出す際に鍵なしの値は `api_key: "none"` です。ただし起動プロセスが `STRATA_API_KEY` を継承している場合、server parserはその環境変数を `--api-key` の既定値にし、server側では引数または環境の値をconfig値より先に選びます。そのためこの環境変数に実鍵がある場合、configの `"none"` が実鍵で上書きされ、鍵ありで動く可能性があります。`STRATA_API_KEY=none` は鍵なしの明示値です（`terminal/strata_control/runtime.py:1056-1060,1071-1074`; `terminal/serve/server.py:9202,9331-9338`; `terminal/serve/server_parts/http_api.py:222-225`）。

## 出力とエラー

`--plan` は鍵なし共有の警告を計画表示に含め、通常の起動では設定確認時に警告します。`--output json` では起動結果の `notices` に警告が含まれます（`terminal/strata_cli/launch/cmd.py:883-904,975-979`）。server起動後も非ローカルアドレスで鍵がなければ標準出力へ警告を出します（`terminal/serve/server.py:9730-9740`）。このフラグ単独を理由に終了・拒否する経路はありません。鍵環境変数が空・未設定の場合など、同時指定した別オプションに由来するエラーは発生します（`terminal/strata_cli/launch/cmd.py:290-299,1011-1012`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:130-140` — 共有先とAPI key関連オプションのparser登録。
- `terminal/strata_cli/launch/cmd.py:215-220,288-313,402-411` — presetへのフラグ適用、鍵の競合・自動生成条件。
- `terminal/strata_cli/launch/settings.py:241-264` — network/public警告の文言と適用条件。
- `terminal/strata_cli/launch/runner.py:724-739,2234-2238` — `api_key: "none"` を含むrun config生成・書き込み。
- `terminal/strata_cli/launch/cmd.py:883-924,975-979` — 計画・起動時noticeの表示経路。
- `terminal/strata_cli/launch/store.py:76-86` — `--save-preset` による設定保存。
- `terminal/strata_control/runtime.py:1056-1060,1071-1074`; `terminal/serve/server.py:9202,9331-9338`; `terminal/serve/server_parts/http_api.py:222-235`; `terminal/serve/server.py:9730-9740` — 環境変数継承、server側の鍵優先順位、鍵なしの明示値と起動警告。
