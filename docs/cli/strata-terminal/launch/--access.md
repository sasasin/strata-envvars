# `--access`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--access` |
| 別名 | なし |
| 値 | `local`、`lan`、`address`、`cloudflare`、`tailscale` のいずれか |

## 役割

起動する Strata server をどのネットワーク範囲で利用可能にするか選びます。選択は server の bind host に反映されます。`local` はこの PC 内だけ、`lan` と `tailscale` は全インターフェース、`address` はこの PC の指定アドレス1つ、`cloudflare` は loopback server に Cloudflare quick tunnel を組み合わせます。

## 使い方

```sh
# LAN からアクセスできるようにして起動
strata launch --model q2_0 --access lan --no-tui

# Cloudflare quick tunnel を使って起動
strata launch --model q2_0 --access cloudflare --no-tui
```

## 値と既定値

値は大文字小文字を区別せず、前後の空白を取り除いてから小文字化され、上記5種類と照合されます。省略可能な値ではなく、`--access` を指定した場合は必ず1値が必要です。既知の値以外は parser が拒否し、選択肢を示します。型変換後の既定値は `local` ですが、保存済み preset を使う場合はその preset の値が引き継がれ、明示した `--access` で置き換わります。

## 実行時の動作

- `local` と `cloudflare` は `127.0.0.1` に bind します。`lan` と `tailscale` は `0.0.0.0`、つまり全インターフェースに bind します。`address` は `--listen` の値に bind します。
- `--listen ADDRESS` を同時指定すると `--access` の指定値にかかわらず access は `address` になり、ADDRESS が使われます。`--listen` なしで `--access address` を指定した場合は、検出したローカルアドレス一覧の先頭を使います。指定アドレスが起動時にこの PC のアドレスでなくなっていれば、全インターフェースへ黙って切り替えず起動を失敗させます。
- `local` 以外では API key が未設定かつ `--no-api-key` でない場合、既存 launch の key を再利用するか、新しい key を生成します。key なしで共有する設定では、到達可能な利用者がモデルやそのツールを使える旨を警告します。`cloudflare` の key なしはインターネットに公開される危険を明記した警告です。
- `cloudflare` を選ぶと、利用可能な `cloudflared` がある場合に quick tunnel を開始します。成功時は tunnel URL をアクセス先として扱います。`lan` は検出できた LAN アドレス、`tailscale` は接続済みなら tailnet 名や IP もアクセス先に表示します。

## 適用条件と副作用

`lan` にローカルネットワークアドレスがない場合、`address` にローカルアドレスがない場合、または `tailscale` が未導入・未接続の場合、起動経路は不足条件を警告します。Cloudflare helper が見つからない場合も案内を警告しますが、server 自体はこの PC 上で動作し続けます。これらの helper の不足を理由に firewall、router、Tailscale の設定を Strata が変更することはありません。

Windows で `lan`、`address`、`tailscale` を使うと、python.exe のネットワーク許可を求める Windows firewall prompt が出ることがあります。`lan` や `tailscale` を選ぶと全インターフェースに bind するため、API key を設定しない場合はアクセス可能な相手が server を利用できます。

## 出力とエラー

未知の値は argparse の型変換で拒否され、候補値と近い入力があれば候補を示します。`address` の listen 先が現在のローカルアドレスでない場合、起動前検査が `LaunchError` と終了コード `2` を返します。利用可能な helper やアドレスの不足は、起動を必ず中止するのではなく警告として出力される経路があります。

## 根拠

- `terminal/strata_cli/launch/cmd.py:35-43` — choice 値を trim・小文字化して許容値と照合し、無効値を parser error にする。
- `terminal/strata_cli/launch/cmd.py:130-140` — `strata launch` parser の `--access` 宣言と共有関連 option の scope。
- `terminal/strata_cli/launch/settings.py:23-28`、`terminal/strata_cli/launch/settings.py:143-145` — 許容値と設定既定値 `local`、`listen` の保存先。
- `terminal/strata_cli/launch/cmd.py:278-286` — 明示 access の適用、`--listen` が `address` に設定を上書きする処理、listen 省略時のアドレス選択。
- `terminal/strata_cli/launch/cmd.py:402-413`、`terminal/strata_cli/launch/settings.py:246-264` — 共有時の API key 再利用・生成と、key 不在時の警告条件。
- `terminal/strata_cli/launch/access.py:28-36`、`terminal/strata_cli/launch/runner.py:724-739` — access 値から bind host を導き、実行 config に host・port・key を設定する処理。
- `terminal/strata_cli/launch/access.py:77-84`、`terminal/strata_cli/launch/runner.py:3296-3308` — address の再検査と、条件不一致時に起動前に停止する経路。
- `terminal/strata_cli/launch/access.py:327-363`、`terminal/strata_cli/launch/runner.py:2884-2904` — helper・ネットワーク状態の確認、警告、URL 表示、Cloudflare tunnel 開始経路。
- `terminal/strata_cli/launch/settings.py:241-264` — key なしで共有する場合の注意文。
- `terminal/strata_cli/launch/cmd.py:1011-1014` — `ValueError` と割り込み時の失敗出力・終了コード。

調査対象は上記 commit の Strata checkout 内の parser と実装に限定しました。実際の OS firewall 表示や Cloudflare/Tailscale 側のネットワーク動作は実行しておらず、Strata ソースが示す条件と処理までを記載しています。
