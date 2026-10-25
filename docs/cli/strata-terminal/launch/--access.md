# `--access`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。調査 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--access KIND` |
| 別名 | なし |
| 値 | `local`、`lan`、`cloudflare`、`tailscale` |
| 既定値 | `local`（preset を読み込む場合は保存値を引き継ぎ、明示した `--access` で上書き） |

## 役割

起動する推論サーバーへの到達範囲を選びます。`local` はこのコンピューターだけ、`lan` はローカルネットワーク、`cloudflare` は Cloudflare quick tunnel、`tailscale` は tailnet 経由です。値は前後の空白を取り除いて小文字化してから照合されるため、大文字・小文字は区別されません。

```sh
strata launch --preset Office --access lan --no-tui
strata launch --model iq3_xxs --access tailscale --no-tui
strata launch --plan --model q2_0 --access cloudflare
```

## 値と動作

| 値 | bind address と追加動作 |
| --- | --- |
| `local` | `127.0.0.1` に bind し、このコンピューター内からのみ接続する設定です。 |
| `lan` | `0.0.0.0` に bind し、LAN アドレスで到達できるようにします。ネットワークアドレスが見つからない場合は警告しますが、設定値自体は拒否しません。 |
| `cloudflare` | サーバーは `127.0.0.1` に bind したまま、`cloudflared tunnel --no-autoupdate --url http://127.0.0.1:<port>` を起動して公開 URL を得ます。 |
| `tailscale` | `0.0.0.0` に bind し、Tailscale のアドレスまたは名前を接続先として表示します。Tailscale が未導入・未接続なら警告しますが、サーバー起動は続けます。 |

`--access` を省略したときの `local` は `LaunchSettings` の初期値です。`--preset NAME` を指定するとまず preset を読み込み、コマンドラインの値がその上に適用されます。`--access local` も明示的な値として preset の共有設定を上書きします。

## API key との相互作用

`local` 以外を選び、key がなく、preset も key なしを指定していない場合、launch は以前の key を再利用できればそれを使い、なければ新しい key を生成します。`--api-key KEY` または `--api-key-env NAME` で明示した key はこの自動選択に優先します。`--no-api-key` は key なし共有を明示し、その場合も拒否されず警告が出ます。key を明示したうえで `--no-api-key` を付けた場合は key が保持され、警告されます。

key なしで LAN/Tailscale に共有すると、そのアドレスへ到達できる利用者がモデルを使えます。Cloudflare はインターネット上で URL を知る利用者が到達でき、ソースの警告ではモデルとそのツールを通じてコンピューター上のファイルを読んだり変更したりできる旨を案内しています。key なし公開を選ぶ場合は、この警告を考慮してください。

## 適用条件、副作用、失敗経路

- `--plan` は選択した access と port を計画として表示して終了し、通常起動時の server や Cloudflare tunnel を開始しません。
- 通常の起動では、launch 用 config に access から決まる host と port、key の設定を書き、launch profile の host/port override も同じ値に置き換えます。`--save-preset` を使わなければ、preset を基にした CLI の変更は通常その起動に適用されます。
- LAN アドレスが見つからない、Tailscale が未導入・未接続、または Cloudflare helper がない場合、access の問題は警告として出ます。Cloudflare helper がない場合も server はこのコンピューター上で稼働します。
- Cloudflare helper が見つかった場合、Strata は `cloudflared` を別プロセスで起動し、最大45秒 URL を待ちます。URL を取得できなければその tunnel を停止して警告を返しますが、server 自体はこのコンピューター上で動作します。成功時は Cloudflare URL を表示します。停止時はこの launch が開始した tunnel だけを終了します。
- server 起動自体が失敗すると、runner は `LaunchError` を返し、CLI は理由と次の手順を表示して終了コードを返します。access の helper 警告は server 起動後に評価されるため、server 起動失敗時には access URL まで進みません。
- `lan` と `tailscale` は `0.0.0.0` bind ですが、この処理は firewall、router、Tailscale の設定を変更しません。Windows の人向け表示では LAN/Tailscale 選択時、初回のネットワーク許可確認について案内します。

## 入力検証

指定できるのは `local`、`lan`、`cloudflare`、`tailscale` の4値です。別の値を渡すと argparse の型変換が拒否し、候補と近い綴り（あれば）をエラー表示します。値は小文字化されるため `LAN` は `lan` として受理されます。port の数値範囲は同じ parser の `--port` が別途検証します。

## 根拠

- `strata_cli/launch/cmd.py:37-45,75-82,119-126` — choice 値の正規化・検証、`--access` の parser 定義と関連する API key オプション。
- `strata_cli/launch/settings.py:23-25,77-100` — 許可値と `LaunchSettings.access` の既定値。
- `strata_cli/launch/cmd.py:197-203,252-269,341-350` — preset 読み込み、CLI 値の適用、共有時の key 再利用・生成と `--no-api-key` の扱い。
- `strata_cli/launch/settings.py:168-191` — key なし共有の警告と access 検査。
- `strata_cli/launch/access.py:1-6,28-32,270-296,299-304` — host bind の対応、アドレス・helper の検出、Windows firewall 案内、firewall 等を変更しないこと。
- `strata_cli/launch/runner.py:371-382,1235-1263` — access に基づく run config、key の反映、launch config と profile の書き込み。
- `strata_cli/launch/runner.py:1560-1605,1674-1694,2011-2044` — server 起動失敗、起動後の access 処理、plan と通常実行の順序。
- `strata_cli/launch/access.py:376-423,426-449` — Cloudflare tunnel の起動、最大待ち時間、失敗時の停止、状態記録と停止処理。
- `strata_cli/launch/settings.py:173-191`、`strata_cli/launch/runner.py:1674-1694` — LAN/Tailscale/Cloudflare helper が使えない場合の警告継続。
- `docs/cli/README.md:925-935` — `strata launch` のコマンド階層と本 option 文書への索引リンク。

調査範囲は指定 commit の Terminal CLI ソース checkout です。別 revision のインストール済み CLI、OS ごとの firewall の実際の表示、外部サービス側の到達性は実行確認していません。
