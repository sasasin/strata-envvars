# `--profile`（alias: `--config`）

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--profile` |
| 別名 | `--config`（同じ引数として受理） |
| 値 | run config の JSON パス、または保存済み serving profile 名。省略不可 |

## 役割

`strata serve` が起動する推論サーバーの元になる run config を指定します。`--profile` と `--config` は同じ値を受け付けます。値が JSON パスとして解釈される場合はその設定を直接使い、保存済み serving profile 名として解釈される場合は profile が参照する run config と保存済み override を使います。オプション名に `profile` とありますが、JSON パスを渡す使い方もあります。

## 使い方

```sh
# 設定ファイルを読み込んで、有効な起動内容だけを表示する（サーバーは起動しない）
strata serve --profile ./models/strata-example.json --plan

# --config は同じ parser 引数の別名
strata serve --config ./models/strata-example.json

# 保存済み serving profile 名を指定して、その設定で前景サーバーを起動する
strata serve --profile local-gpu
```

## 値と既定値

- 値は必須で、既定値はありません。値を省略すると `argparse` が引数エラーにします。parser は `--profile` と `--config` の両方を `config` 属性へ格納します（`terminal/strata_cli/cli.py:67-69`）。
- 値が `.json` 拡張子（大文字小文字を問わない）、絶対パス、または `/`・`\` を含む場合はパスとして扱われます。`~` を展開して絶対パスへ解決し、そのファイルを読みます。それ以外は保存済み profile 名として扱います（`terminal/strata_control/profiles.py:400-405`）。相対パスはプロセスの作業ディレクトリを基準に解決されます。
- run config は UTF-8（BOM 付きも可）の JSON object で、`args` が文字列配列、`exe` と `tokenizer` が空でない文字列パスである必要があります。読み込み失敗や不正な JSON は `ProfileError` になります（`terminal/strata_control/profiles.py:135-150`）。
- 保存済み profile 名の場合、保存 profile を読み込み、profile に保存された絶対 `source_config` の run config も読みます。profile 自体は規定の schema と ID、override の検証を通ります（`terminal/strata_control/profiles.py:120-132,153-173,400-405`）。

## 実行時の動作

1. CLI は受け取った値を `_launch_plan` に渡し、`profiles.resolve` で run config のパスと、該当する場合は保存 profile・revision を解決します（`terminal/strata_cli/cli.py:974-975,821-823`、`terminal/strata_control/profiles.py:400-405`）。
2. 設定値を組み立てます。CLI で指定した server 設定が最優先で、続いて保存 profile の override、run config の値、既定値が使われます。`batch_telemetry` はさらに run config にも保存 override にもない場合、`STRATA_BATCH_TELEMETRY` 環境変数（値が `1` のとき有効）を既定値より先に参照します（`terminal/strata_cli/cli.py:783-807`）。
3. 有効値から server 引数と engine argv を組み立て、plan 出力には元 config のパス、設定値の出所、engine 実行ファイル・引数などを含めます（`terminal/strata_cli/cli.py:821-865`）。`--plan` を付けると plan を表示して終了し、server は起動しません。付けない場合は同じ config を server に渡し、前景で稼働させます（`terminal/strata_cli/cli.py:979-994`）。

このオプションの値は `--engine` の選択とは別です。`--engine` の既定は `strata` で、`mock` も選べますが、どちらの経路でも `--profile` / `--config` は必須です（`terminal/strata_cli/cli.py:68-71,833-835`）。

## 適用条件と副作用

- 保存 profile 名として解釈された場合は、profile の override が run config より優先されます。一方、`--parallel` など `strata serve` の CLI 指定は保存 profile より優先されます（`terminal/strata_cli/cli.py:783-807`）。
- `--parallel` は run config の `args` に `--batch` または `--slots` がある場合に競合として拒否されることがあります。`batch_groups` override も `args` 内に `--batch-groups` があれば拒否されます。また `queue_timeout` は `max_queue` と同時に有効でなければ拒否され、`offline` は config に `mcp_servers` または `before_load` がある場合には利用できません（`terminal/strata_cli/cli.py:808-818`）。これらは参照先 config / profile と他の `strata serve` オプションとの相互作用です。
- `--plan` では server を起動しません。通常実行では前景 server が起動し、ポートを使用します。POSIX / Windows では起動中に runtime activity lease を取得し、終了時に閉じます（`terminal/strata_cli/cli.py:979-994`）。
- `--ready-file` を併用すると、server 起動前に指定パスを preflight して、そのパスを server 引数へ渡します（`terminal/strata_cli/cli.py:845-849`）。

## 出力とエラー

- `--output json` は `--plan` と併用する必要があります。前景イベントを JSONL で受け取る場合は `--output jsonl` を使います。これらの組み合わせ違反は設定解決前にエラーになります（`terminal/strata_cli/cli.py:954-958`）。
- 存在しない config、読み取り不能ファイル、不正 JSON は読み込みエラーになります。通常の human 出力では CLI のエラー文を stderr に出し、失敗終了コードを返します。JSON/JSONL 出力では構造化エラーに変換されます（`terminal/strata_control/profiles.py:135-150`、`terminal/strata_cli/cli.py:868-875,2248-2265`）。
- 保存 profile 名が見つからない場合は `strata profile create` を案内するエラーになります（`terminal/strata_control/profiles.py:153-173`）。

## 根拠

- `terminal/strata_cli/cli.py:67-69` — `serve` parser における必須引数、alias、格納先、値の metavar。
- `terminal/strata_control/profiles.py:135-150,400-405` — config 読込と最低限の構造検証、パスと profile 名の判別。
- `terminal/strata_control/profiles.py:120-132,153-173` — 保存 profile の schema・override 検証と読み込み失敗。
- `terminal/strata_cli/cli.py:783-865` — 設定の優先順位、制約、server / engine 起動計画の組み立て。
- `terminal/strata_cli/cli.py:954-994` — `--plan`、出力形式の制約、前景 server 起動と lease の扱い。
- `terminal/strata_cli/cli.py:868-875,2248-2265` — 構造化エラーと通常エラーの処理。

調査範囲は上記の CLI parser、設定解決・検証、起動計画と dispatch 経路です。個々の engine/backend が run config 内の全設定をどう解釈するかは、このオプション文書では網羅していません。
