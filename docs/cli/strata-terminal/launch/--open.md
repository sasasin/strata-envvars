# `strata launch --open`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--open` |
| 別名 | なし |
| 値 | なし。`argparse` の `store_true` フラグ |

## 役割

サーバーが起動した後、そのサーバーの Web ページを既定のブラウザーで開きます。省略時はブラウザーを開きません。ブラウザーを開く処理は Terminal CLI 側にあり、起動設定の `open_browser` を有効にしたり、サーバーへ `--open` を転送したりするものではありません。

## 使い方

```sh
# モデルを起動し、サーバーが利用可能になったらブラウザーで開く
strata launch --model q2_0 --no-tui --open
```

`--no-tui` を付けない対話画面から起動する場合も、`strata launch --open` を指定すると、起動完了後にページを開きます。

## 値と既定値

値を取りません。parser は `action="store_true"` で登録しているため、指定すると真、未指定では偽です。別名はなく、複数回指定しても同じ真偽値として扱われます（`terminal/strata_cli/launch/cmd.py:141-151`）。

## 実行時の動作

フラグ起動では、`Runner.run()` が serving 状態を返した後、人向け出力経路で開く URL を選び、`--open` が指定されていれば `open_page()` を呼びます。URL は `127.0.0.1` を含むものを優先し、なければ返された URL の先頭を使います（`terminal/strata_cli/launch/cmd.py:967-999`）。対話画面ではフラグを画面処理へ渡し、結果が serving の場合にその URL を開いてから monitor を開始します（`terminal/strata_cli/launch/cmd.py:867-871, 947-948`; `terminal/strata_cli/launch/app.py:693-695, 713-730`）。

起動用設定を組み立てる際、`open_browser` は常に `false` にされ、設定内の既存 `args` にある `--open` も取り除かれます。したがってこのオプションの作用は CLI 側の明示的なブラウザー起動に限定されます（`terminal/strata_cli/launch/runner.py:724-749`）。サーバー自身にも別の `--open` parser とブラウザー起動処理がありますが（`terminal/serve/server.py:9195, 9746-9751`）、`strata launch` の設定ではそれを有効化しません。

## 適用条件と副作用

- 通常起動でサーバーが serving になり、人向け出力経路に到達した場合に働きます。起動結果が serving でなければ呼び出されません（`terminal/strata_cli/launch/cmd.py:967-999`）。
- 対話画面でも serving の場合に限り、起動後にブラウザーを開きます（`terminal/strata_cli/launch/app.py:713-730`）。
- `--plan` は計画を表示して終了し（`terminal/strata_cli/launch/cmd.py:897-925`）、`--output json` は起動結果を JSON 出力して終了するため（同 `975-979`）、どちらもブラウザーを開きません。
- `--list-presets`、`--delete-preset`、`--stop`、`--status`、`--show-key` も起動処理より前に分岐して終了する管理モードです（`terminal/strata_cli/launch/cmd.py:766-815`）。これらのモードに `--open` を併記してもページを開く処理には到達しません。
- 実際にブラウザーを開く関数は Python の `webbrowser.open(url)` を呼びます。OS の既定ブラウザー起動につながる副作用があります（`terminal/strata_cli/launch/cmd.py:625-631`）。

## 出力とエラー

`webbrowser.open()` が偽を返す場合や例外を送出する場合、関数は `False` を返して終了し、CLI はその結果を確認しません。したがってブラウザーを起動できなくても、この処理自体は警告や非ゼロ終了コードを出しません（`terminal/strata_cli/launch/cmd.py:625-631, 997-1000`）。サーバーの起動失敗は `--open` のブラウザー起動より前に扱われ、`LaunchError` は `fail()` 経由でエラー出力・終了コードになります（同 `950-961`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:73-80, 141-151` — `launch` parser と `--open` の `store_true` 登録。
- `terminal/strata_cli/launch/cmd.py:897-925, 950-1000` — 計画・起動失敗・JSON・人向け起動結果それぞれの分岐とブラウザー起動。
- `terminal/strata_cli/launch/cmd.py:625-631` — ブラウザー呼び出しと例外の扱い。
- `terminal/strata_cli/launch/app.py:693-730` — 対話画面からの起動結果とブラウザー起動。
- `terminal/strata_cli/launch/runner.py:724-749` — 起動設定で `open_browser` を無効化し、引数から `--open` を除く処理。
- `terminal/serve/server.py:9195, 9746-9751` — 別途存在するサーバー側 `--open` と、その条件付きブラウザー起動。

調査範囲はこの revision の Strata 所有ソースです。OS ごとの `webbrowser` の既定ブラウザー選択や、起動要求後にブラウザーが実際に表示されるかは Python・OS 側の挙動に依存するため、ここでは断定していません。
