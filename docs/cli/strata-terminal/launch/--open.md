# `--open`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象 checkout は `main...origin/main` で未コミット変更なし。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--open` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる（`store_true`）。 |

## 役割

サーバーが serving 状態になった後、Strata のサーバーページを既定のブラウザーで開きます。既定ではブラウザーを開きません。

## 使い方

```sh
strata launch --preset "Office" --no-tui --open
```

`--open` は preset や model の指定に追加できます。`--no-tui` を付けない対話式起動でも、起動後に monitor を表示する経路で有効です。

## 値と既定値

値・引数はありません。省略時はブラウザーを開かず、複数回指定しても真偽値のままです。parser 側に個別の値 validation はありません。`strata launch --open` のように起動対象を指定せず、対話可能な TTY もない場合は、起動対象を明示するようエラーになります。`--open` 自体は起動対象を選びません。

## 実行時の動作

- フラグは TUI 起動時に `open_page` として渡されます。サーバー起動後、結果が serving であれば `webbrowser.open(url)` を呼びます。TUI 経路では `result.urls[0]` が選ばれ、URL がなければ `http://127.0.0.1:<port>` に fallback します。Cloudflare access の URL 一覧は tunnel URL が先頭になるため、TUI 経路では tunnel URL を開きます（`strata_cli/launch/app.py:404-412,471-474`、`strata_cli/launch/access.py:285-296`）。
- 非 TUI の人間向け出力では、URL 一覧から `127.0.0.1` を含む URL を優先し、なければ先頭 URL を開きます。現在の URL 生成処理では通常 localhost URL が一覧に含まれます（`strata_cli/launch/cmd.py:806-822`、`strata_cli/launch/access.py:285-296`）。
- `strata launch` はサーバー設定の `open_browser` を常に `False` にし、設定内の engine 引数から `--open` を取り除きます。ブラウザー起動は launch CLI 側の明示指定で行われ、エンジン任せではありません（`strata_cli/launch/runner.py:374-388`）。

## 適用条件と副作用

ブラウザーを開くのは起動結果が `serving` のときです。`--plan` は計画を表示して終了し、`--output json` は成功結果を JSON 出力して終了するため、どちらもブラウザーを開きません。管理操作（preset 一覧・削除、status、stop、show-key）も起動処理より先に終了します。既に同じ設定で serving 中の場合は runner が再利用結果を返すため、通常の人間向け経路ではその URL を開きます（`strata_cli/launch/cmd.py:659-676,697-710,735-760,784-805`、`strata_cli/launch/runner.py:1516-1521`）。

ブラウザー起動には Python 標準の `webbrowser` を使います。呼び出しが例外を送出した場合は握りつぶし、`webbrowser.open()` が偽を返した場合も追加エラーを出しません。したがってブラウザーが開かなくてもサーバー自体は止めず、アドレス表示など後続の案内を続けます（`strata_cli/launch/cmd.py:529-535,806-829`、`strata_cli/launch/app.py:471-475`）。

## 出力とエラー

このオプション固有の validation error はありません。ブラウザー起動失敗は標準エラーや警告として報告されません。通常の起動失敗は `strata launch` 共通のエラー経路を通り、人間向けでは `strata: ...` を stderr に出し、失敗コードを返します。起動結果が serving でない場合は通常の結果メッセージを出して終了し、ブラウザー処理には入りません（`strata_cli/launch/cmd.py:642-649,784-800,832-837`）。

## 根拠

- `strata_cli/launch/cmd.py:136` — `--open` の parser 定義（値なし、`store_true`）。
- `strata_cli/launch/cmd.py:529-535` — 標準 `webbrowser.open()` の呼び出しと例外抑制。
- `strata_cli/launch/cmd.py:688-710,780-783,793-805,820-829` — TUI・plan・JSON・非 TUI の分岐とブラウザー起動条件。
- `strata_cli/launch/runner.py:374-388,1516-1521` — server config での自動 browser 無効化、同一設定の稼働 server 再利用。
- `strata_cli/launch/app.py:404-412,471-475` — TUI 経路で開く URL と起動後の呼び出し。
- `strata_cli/launch/access.py:285-296` — access mode ごとの URL 順序。

調査範囲は上記 commit の Terminal CLI ソースです。OS ごとの `webbrowser` backend が実際にどのアプリを起動するか、各環境で URL を開けるかは実行確認していません。
