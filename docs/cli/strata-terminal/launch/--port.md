# `--port`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--port` |
| 別名 | なし |
| 値 | `N`。1〜65535 の整数 |

## 役割

`strata launch` が起動するモデルサーバーの待受ポートを指定します。ポート番号は生成する実行設定と launch プロファイルに反映され、起動中のサーバーの識別、接続 URL、Cloudflare tunnel の接続先にも使われます。待受アドレスや共有範囲は別の `--access` / `--listen` が決めます。

## 使い方

```sh
# 起動計画だけを表示し、サーバーは起動しない
strata launch --model q2_0 --port 8081 --plan

# モデルを選び、8081 番ポートでサーバーを起動して監視画面を使う
strata launch --model q2_0 --port 8081

# 画面や質問を使わず起動し、接続先を表示して終了する
strata launch --model q2_0 --port 8081 --yes --no-tui
```

## 値と既定値

- `N` は `int()` で整数に変換でき、1〜65535 の範囲に入る必要があります。範囲外や整数でない値は parser が拒否します。`0` は自動割当てを意味せず、無効です（`terminal/strata_cli/launch/cmd.py:53-60`）。
- 指定しない場合は `8080` です。新規設定の既定値は `terminal/strata_cli/launch/settings.py:75,143-145` にあります。保存済み preset を読み込む場合はその設定から始まり、CLI の `--port` を指定すると値を置き換えます（`terminal/strata_cli/launch/cmd.py:215-221,286-287`）。
- 1〜1023 は受理されますが、多くの環境で管理者権限が必要になるという警告になります（`terminal/strata_cli/launch/settings.py:228-238`）。
- 同じ `--port` を複数回指定した場合の専用処理は parser にありません。`argparse` の通常の単一値オプションとして扱われます。

## 実行時の動作

`--port` は `LaunchSettings.port` に入り、モデルの実行設定の `port` として保存されます。また、launch プロファイルの `host` / `port` override にも設定されます（`terminal/strata_cli/launch/cmd.py:286-287`、`terminal/strata_cli/launch/runner.py:724-734,2323-2346`）。結果 URL はこのポートを使い、`--access address` では指定アドレス、その他ではローカル URL を組み立てます。LAN や Tailscale の URL にも同じポートが使われ、Cloudflare tunnel の開始にも渡されます（`terminal/strata_cli/launch/access.py:62-74,342-355`、`terminal/strata_cli/launch/runner.py:2884-2904`）。

起動前に、別の `strata launch` プロファイルが同じポートで動いていないかを確認します。同じ設定が既に同じプロファイル・ポートで動いていれば再利用します。別の launch が同じポートを使っている場合や、同じ launch の設定が異なる場合は、対話画面では再起動確認を行い、確認できない実行では `--restart` がなければ終了します。異なるポートの launch は並行して続行できますが、GPU メモリが足りず新しい起動に失敗する可能性がある旨を通知します（`terminal/strata_cli/launch/runner.py:2554-2585`）。`--restart` で競合する launch を止める場合、そのサーバーは停止します（`terminal/strata_cli/launch/runner.py:2632-2643`）。

`--port` 単独は「起動する選択肢」として数えられません。対話端末では選択肢なしの画面経路に進み、非対話実行ではモデルまたは preset を指定するようエラーになります。したがって、起動時は `--model` / `--preset` などと組み合わせてください。`--plan` はこの選択肢チェックを通り、ポートを含む設定を計画に載せますが、サーバー起動経路には進みません（`terminal/strata_cli/launch/cmd.py:844-871,897-905`）。

## 適用条件と副作用

- 起動前の空き確認は、ローカルモードでは `127.0.0.1`、`--access address` とアドレス指定がある場合はそのアドレスへの TCP 接続を試します。接続できた場合は「使用中」として起動を拒否し、終了コード 6 の `LaunchError` になります（`terminal/strata_cli/launch/runner.py:2815-2829,2661`）。この確認は bind 試行ではなく TCP 接続による判定です。
- 同じポートを別プロセスが使っている場合、エラーにはポート番号と別ポートの例が示されます。空き確認後に実際の起動が失敗した場合も、起動失敗として報告され、今回の runtime を停止・cleanup します（`terminal/strata_cli/launch/runner.py:2828-2829,2686-2696,2831-2841`）。
- ポート値はネットワーク待受先を変えます。LAN・指定アドレス・Tailscale などの共有方式と組み合わせる場合、クライアントが接続する URL のポートも変わります。API key の有無やアクセス範囲そのものはこのオプションでは変更しません。
- `--port` のみを指定した対話起動は parser で値を読み取りますが、コマンド側の `have_choices` 判定には含まれず、選択肢なしの TUI 経路へ進みます。その経路には `LaunchSettings` が渡されません。単独指定でポート変更を意図せず、モデルまたは preset と併用してください（`terminal/strata_cli/launch/cmd.py:849-871`）。

## 出力とエラー

- 不正な形式または 1〜65535 外の値は、parser の引数エラーとして拒否されます。1〜1023 はエラーではなく権限に関する警告です（`terminal/strata_cli/launch/cmd.py:53-60`、`terminal/strata_cli/launch/settings.py:228-238`）。
- 起動前の接続確認で使用中と判定されると、`Port N is already in use by another program.` と別ポートを試す案内が出て終了コード 6 になります（`terminal/strata_cli/launch/runner.py:2815-2829`）。
- `--plan` は計画を表示します。通常の起動では完了後に選択された URL が結果として表示されます（`terminal/strata_cli/launch/cmd.py:897-905,980-985`、`terminal/strata_cli/launch/runner.py:3337-3343`）。出力形式は同じコマンドの `--output` により human / JSON を選べますが、`--port` 自体は出力形式を変えません。

## 根拠

- `terminal/strata_cli/launch/cmd.py:53-60,130-138` — parser の scope、型変換、範囲検査。
- `terminal/strata_cli/launch/settings.py:75,143-145,228-238` — 既定値と設定時の port validation / 低番ポート警告。
- `terminal/strata_cli/launch/cmd.py:215-221,278-287,401-416,844-871,897-905` — preset との合成、CLI 値の適用、アクセス検査、ポート単独指定時と plan の分岐。
- `terminal/strata_cli/launch/runner.py:724-734,2323-2346` — 実行設定と launch プロファイルへの反映。
- `terminal/strata_cli/launch/runner.py:2554-2585,2632-2643,2661,2815-2829,2686-2696,2831-2841` — 起動中 launch の競合、空き確認、失敗時の後始末。
- `terminal/strata_cli/launch/access.py:62-74,342-355`、`terminal/strata_cli/launch/runner.py:2884-2904,3337-3343` — URL、tunnel、起動後の接続先。
