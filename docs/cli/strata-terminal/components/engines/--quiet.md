# `--quiet`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査対象 checkout は `main`（`origin/main` と一致）で、調査開始時の作業ツリーに未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | なし。真偽値フラグ |

## 役割

人間向けの情報出力を抑えます。このコマンドでは、導入済み engine の一覧を成功時に標準出力へ出さなくなります。engine の探索や適合性の確認を省略するオプションではありません。

## 使い方

```sh
strata components engines --quiet
```

通常は成功時の一覧表示が抑制され、終了コード `0` になります。JSON が必要な場合は `--output json` を指定します。

## 値と既定値

- 値を取らない `store_true` フラグです。指定しない場合は無効で、指定すると有効になります。複数回指定しても真偽値は有効のままです（`strata_cli/cli.py:508-515`）。
- `strata components engines` の parser に `--quiet` を直接追加するのではなく、`update_cmd.add_parsers()` が返す parser 群に対して `strata_cli/cli.py` が後から共通オプションとして追加します。対象の `engines` parser はその群に含まれます（`strata_cli/update_cmd.py:82-95`、`strata_cli/cli.py:140,508-515`）。
- `--quiet` は `--output` の選択値や `--json` と排他的ではありません。ただし出力形式が `json` または `jsonl` の場合、quiet による標準出力の抑制経路には入りません（`strata_cli/cli.py:2249-2260`）。

## 実行時の動作

`strata components engines` は `update_cmd.run()` から `_engines_command()` に渡り、engine library がローカルにある engine 情報を組み立てます（`strata_cli/cli.py:2136-2138`、`strata_cli/update_cmd.py:272-273,358-364`）。この一覧処理は engine をダウンロード・変更しません。導入済み component の走査、実行中プロセスの確認、およびハードウェア情報による適合判定は引き続き行われます（`strata_control/engine_library.py:91-111,136-162,167-195`）。

`--output` の既定値 `human` で `--quiet` を指定すると、CLI はコマンドの標準出力を一時バッファーに取り込みます。終了コードが `0` ならバッファーの内容を出さず、非 `0` なら最大 64 KiB の保持内容を標準エラーへ出します。保持上限を超えた失敗では、省略を示すメッセージを先に標準エラーへ出します（`strata_cli/cli.py:2197-2215,2253-2265`）。engine 一覧の通常表示は標準出力に書かれるため、成功時は表示されません（`strata_cli/update_cmd.py:363-377`）。

## 適用条件と副作用

- `--quiet` は一覧表示を抑えるだけで、コマンド自体を読み取り専用に変えるものではありません。そもそも `engines` の一覧処理はファイルを読み取り、engine 状態を表示する処理であり、変更・ダウンロードをしません（`strata_control/engine_library.py:180-195`）。
- `--output json` または `--output jsonl`（`--json` も含む）を使うと機械可読出力が優先され、`--quiet` を併記しても JSON は標準出力へ出ます。`engines` の machine 経路は一覧オブジェクトを単一の JSON 文書として出力します（`strata_cli/cli.py:513-515,2249-2254`、`strata_cli/update_cmd.py:363-367`）。
- 共通 parser は `--feed`、`--wait`、`--force`、`--model-config` などもこのサブコマンドで受理しますが、`engines` 分岐は一覧処理へ進み、これらを使用しません。`--components-dir` は一覧対象の root、`--backend` は検出した backend の上書きとして `update_cmd.run()` で反映されます（`strata_cli/update_cmd.py:47-56,244-256,272-273`）。

## 出力とエラー

- 人間向け出力では成功時の engine 一覧が抑制されます。JSON 出力指定時は抑制されず、一覧が標準出力へ出ます（`strata_cli/update_cmd.py:363-377`、`strata_cli/cli.py:2253-2265`）。
- CLI が扱う `ValueError`、`OSError`、`ClientError`、割り込みなどは `_run()` がエラーメッセージを標準エラーまたは JSON に出し、対応する終了コードを返します。quiet 時も stderr はリダイレクトされず、さらに非ゼロ終了でバッファー済み stdout があれば標準エラーへ戻されます（`strata_cli/cli.py:2167-2194,2258-2265`）。
- `--quiet` に固有の値 validation や失敗コードはありません。未知の引数など parser 段階のエラーは `main()` の引数解析時に処理されます（`strata_cli/cli.py:2230-2248`）。

## 根拠

- 索引上のコマンド階層と予定リンク: `docs/cli/README.md:274-290`。
- `engines` parser と共通オプション: `strata_cli/update_cmd.py:47-56,82-95`、後付け `--quiet` 定義: `strata_cli/cli.py:140,508-515`。
- `engines` の dispatch と一覧出力: `strata_cli/cli.py:2136-2138`、`strata_cli/update_cmd.py:272-273,358-377`。
- quiet 時の出力処理: `strata_cli/cli.py:2197-2215,2249-2265`。
- 一覧が参照する engine 状態と読み取り範囲: `strata_control/engine_library.py:91-111,136-162,167-195`。
