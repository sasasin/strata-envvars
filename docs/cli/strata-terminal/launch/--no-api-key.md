# `--no-api-key`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--no-api-key` |
| 別名 | なし |
| 値 | 取らない真偽フラグ。指定時は有効、未指定時は無効 |

## 役割

`strata launch` で LAN や Cloudflare など、このコンピューターの外へ共有するときに、API キー認証を意図的に無効にします。認証を無効にしても起動を拒否せず、CLI とサーバーが警告を出します。到達できる人はモデルとツールを使え、ツールからこのコンピューター上のファイルを読み書きできる可能性があります（`strata_cli/launch/cmd.py:126`、`strata_cli/launch/settings.py:168-170`、`serve/server.py:7655-7662`）。

## 使い方

```sh
strata launch --model q2_0 --access lan --no-api-key --plan
```

`--plan` を外すと実際の起動処理に進みます。`--plan` はこの例の設定を表示して終了し、変更を行いません（`strata_cli/launch/cmd.py:138`、`strata_cli/launch/cmd.py:733-759`）。

## 値と既定値

- 値や `=` 形式は取りません。`argparse` の `store_true` action で定義されるため、既定値は偽です（`strata_cli/launch/cmd.py:126`）。
- 未指定なら保存済みプリセットのキーはそのまま引き継がれます。共有モードでキーも `--no-api-key` もなければ、以前の起動で使ったキーを再利用し、なければ新規作成します（`strata_cli/launch/cmd.py:201-203`、`strata_cli/launch/cmd.py:341-350`）。
- このフラグ自体の値検証はありません。オプションの後に値を渡す構文は parser の定義にないため、通常の `argparse` 引数エラーになります（`strata_cli/launch/cmd.py:126`）。

## 実行時の動作

- フラグが有効で `--api-key` / `--api-key-env` が指定されていない場合、現在の設定の API キーを `None` にし、`no_key` を真にします。これはプリセットに保存されていたキーも外す処理です（`strata_cli/launch/cmd.py:256-269`）。
- この状態では共有モード用の自動キー再利用・生成を行いません（`strata_cli/launch/cmd.py:341-350`）。実行設定では `api_key: "none"` として記録し、`serve/server.py` がこれを「キーなし」の指定として認識します（`strata_cli/launch/runner.py:371-382`、`serve/server.py:7649-7652`）。
- `--api-key KEY` または `--api-key-env NAME` と同時に指定すると、キーを保持して「API key was given as well as `--no-api-key`, so the key is kept.」という警告を出します。環境変数名が未設定または空なら、キー保持の分岐に進む前にエラーになります（`strata_cli/launch/cmd.py:256-267`）。
- `--new-key` も同時に指定すると、後続処理で新しいキーを作り `no_key` を解除します（`strata_cli/launch/cmd.py:726-728`）。
- `--access local`（既定）では、共有アクセス向けキー自動生成の対象外です。このフラグがあっても `no_key` の実行設定化は非 local の場合に限られ、local では `api_key` を設定から除去します（`strata_cli/launch/settings.py:97-100`、`strata_cli/launch/cmd.py:341-350`、`strata_cli/launch/runner.py:377-382`）。

## 適用条件と副作用

- `lan`、`cloudflare`、`tailscale` など `local` 以外のアクセスでキーなしになると、CLI は警告を追加します。Cloudflare の場合は「公開アドレス上で、見つけた人が利用できる」旨を示します。警告は拒否ではありません（`strata_cli/launch/settings.py:173-191`）。
- サーバーが loopback 以外へ bind し、API キーがない場合、サーバーは到達可能な相手がモデルを使える旨を標準出力へ警告します。MCP ツールが設定されていれば、ツールがファイルを読み書きできる旨も加わります（`serve/server.py:8624-8633`、`serve/server.py:7655-7662`）。
- `--save-preset` と併用すると、このキーなし設定をプリセットへ保存します。通常起動では設定ファイルを書き、サーバーを起動し、Cloudflare を選択して補助プログラムが利用可能ならトンネルも開きます（`strata_cli/launch/cmd.py:788-792`、`strata_cli/launch/runner.py:2025-2043`、`strata_cli/launch/runner.py:1675-1694`）。
- 既に同じ設定のサーバーが動作中なら再起動せず、そのサーバーを再利用します。設定が異なる場合の置き換えには別途 `--restart` が関係します（`strata_cli/launch/runner.py:1505-1521`、`strata_cli/launch/cmd.py:132-134`）。

## 出力とエラー

- `--plan` の人間向け出力には警告が表示され、JSON 出力では `warnings` に含まれます。いずれも計画だけでサーバーは起動しません（`strata_cli/launch/cmd.py:733-759`）。
- 実起動後、人間向け出力では結果に応じて通知を `[!]` 付きで表示します。API キーがない場合はキー表示行を出さず、キーなしで `strata monitor` を起動する案内を出します（`strata_cli/launch/cmd.py:801-829`）。
- `--api-key-env` の参照先が空または未設定の場合、通常出力では `strata: ...` を標準エラーへ、JSON モードではエラーオブジェクトを標準出力へ出し、終了コード 2 で終了します（`strata_cli/launch/cmd.py:256-262`、`strata_cli/launch/cmd.py:636-641`、`strata_cli/launch/cmd.py:832-835`）。

## 根拠と調査範囲

- parser と既定値: `strata_cli/launch/cmd.py:119-126`
- プリセットへの適用、キーとの相互作用、自動生成条件: `strata_cli/launch/cmd.py:197-203`、`strata_cli/launch/cmd.py:256-269`、`strata_cli/launch/cmd.py:341-350`、`strata_cli/launch/cmd.py:726-728`
- 警告条件: `strata_cli/launch/settings.py:168-191`
- サーバー用設定への反映と既存起動の再利用: `strata_cli/launch/runner.py:371-382`、`strata_cli/launch/runner.py:1505-1521`
- サーバー側の「キーなし」認識と起動時警告: `serve/server.py:7649-7662`、`serve/server.py:8624-8633`

調査開始時の Strata checkout は `main` が `origin/main` と一致し、`git status --short --branch` に未コミット変更はありませんでした。ソース checkout の処理を調査し、同一 revision の CLI `--help` や Release artifact は照合していません。OS ごとのネットワーク到達性や外部トンネルの動作・配布状況は、このオプションのソース追跡範囲外です。
