# `--listen`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--listen` |
| 別名 | なし |
| 値 | `ADDRESS`。この PC の現在のネットワークアドレスを文字列で指定する。 |

## 役割

サーバーをこの PC の全アドレスで待ち受ける代わりに、指定した一つのアドレスだけで待ち受ける。設定すると共有方法も `address` に切り替わる。別のネットワークカードや VPN のアドレスに限定して公開したい場合に使う。

## 使い方

```sh
# この PC の指定アドレスだけで待ち受け、サーバー起動後に接続先を表示する
strata launch --model q2_0 --listen 192.168.1.20 --no-tui
```

`ADDRESS` は例示値ではなく、その時点で実際にこの PC に割り当てられているアドレスに置き換える。IPv6 の URL 表示ではアドレスが角括弧で囲まれる。

## 値と既定値

- 値を一つ取る。parser は `ADDRESS` の文字列形式や IP 構文を独自の型変換では検証せず、設定適用時に前後の空白を除いて保持する。
- `--listen` を指定すると `access=address` と `listen=ADDRESS` が設定される。`--access` も同時に指定した場合でも `--listen` の指定が `--access` の値より優先され、`address` になる。
- `--listen` を省略した場合の既定は `local`（この PC のみ）。ただし `--access address` を指定した場合、既存の listen 値がなければ検出したローカルアドレス一覧の先頭を選ぶ。リストが空なら値は未設定のままになり、起動時の検査で拒否される。
- `--listen` 自体には専用の書式・範囲 validator がない。実際にサーバーを起動する経路では、値（IPv6 の `%zone` 部分を除いたもの）が現在のローカルアドレス一覧に含まれることを検証する。無効値を別アドレスへ補正する動作はなく、起動を拒否する。

## 実行時の動作

設定構築時には `--listen` の値が `LaunchSettings.listen` に入り、共有方式が `address` になる。実行設定と profile の host に同じ値が設定されるため、起動するサーバーはそのアドレスで待ち受ける。起動後に表示する接続 URL もそのアドレスを使い、IPv6 なら URL 用に角括弧を付ける。

実際の起動では、engine の準備や既存サーバーを止める処理より先にアドレスを再確認する。起動時点でローカルアドレス一覧から消えていれば失敗し、全アドレス待受け（`0.0.0.0`）へ黙って切り替わることはない。アドレス一覧は `lan_ips()` と、取得できる場合は `psutil` のネットワークインターフェース情報から作られ、loopback と link-local は候補から除外される。

## 適用条件と副作用

- アドレスの有効性は実際の起動時点のローカルインターフェース一覧に依存する。ネットワークや VPN の状態が変わり、指定アドレスがなくなった場合は再度正しいアドレスを選ぶ必要がある。
- IPv6 の zone ID は一覧照合時に除かれる一方、設定に保存される値自体は空白除去後の文字列である。zone ID を付けた値をサーバー側がどう解釈するかは、この CLI のソースだけでは確定できない。
- launch の設定ファイルと profile の host override が更新される。アドレスを一つに限定するため、他のローカルアドレスでは待ち受けない。
- Windows では `address` 共有時にネットワーク許可ダイアログが出る可能性を事前に案内する。

## 出力とエラー

起動時に指定アドレスがこの PC のアドレスとして見つからない場合、現在検出できたアドレスを列挙したエラーを返し、終了コード `2` で停止する。human 出力では `strata: ...` を標準エラーへ出し、`--output json` では `ok: false` とエラーコード・メッセージを含む JSON を標準出力へ出す。検査は起動処理の前に行われる。

## 根拠

- `terminal/strata_cli/launch/cmd.py:130-136` — `--listen ADDRESS` parser 定義と `--access` との関係を示す help。
- `terminal/strata_cli/launch/cmd.py:278-285` — `--access` と listen 値の適用順、空白除去、`address` 指定時の自動選択。
- `terminal/strata_cli/launch/settings.py:124-126` — 共有方式・listen 値・port の設定項目。
- `terminal/strata_cli/launch/access.py:28-35` — 共有方式と listen 値から bind host を選ぶ処理。
- `terminal/strata_cli/launch/access.py:38-54,77-85` — ローカルアドレス候補の収集・除外条件、および指定値の照合と不一致メッセージ。
- `terminal/strata_cli/launch/access.py:62-66,342-355` — ローカル接続 URL と起動後の公開 URL の組み立て。
- `terminal/strata_cli/launch/access.py:358-363` — Windows のネットワーク許可に関する案内条件。
- `terminal/strata_cli/launch/runner.py:680-689,2257-2270` — host 値の実行設定への反映と profile override の保存。
- `terminal/strata_cli/launch/runner.py:3141-3155` — 実起動時のアドレス検査が engine 準備・既存サーバー確認より先に行われること。
- `terminal/strata_cli/launch/cmd.py:753-764,949-961` — 起動エラーの human / JSON 出力と終了コードの返却。

調査範囲は上記 revision の Terminal CLI ソースである。bind 後の OS・engine 側のアドレス解釈や、firewall の実際の動作はこの文書では確定していない。
