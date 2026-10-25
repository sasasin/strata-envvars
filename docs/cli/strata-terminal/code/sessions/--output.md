# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code sessions` |
| オプション | `--output` |
| 別名 | なし（`--json` は同じ出力形式を選ぶ別オプション） |
| 値 | `human` または `json` |

## 役割

セッション一覧コマンドの出力形式を選ぶオプションです。`--output` は `sessions` サブコマンドに登録されています。索引でも `strata code sessions` 配下の項目です（`docs/cli/README.md:1119-1126`）。

## 使い方

```sh
strata code sessions list --output json
```

`--output` を省略した場合は `human` です。`--json` も `code sessions` に登録されており、指定すると `--output json` と同じ値に設定されます。

## 値と既定値

- `human`: 既定値です。
- `json`: 機械処理向け JSON 出力を選びます。
- 他の値は `argparse` の `choices` により拒否されます。値なしや不正値では parser が usage とエラーを stderr に出し、終了コード 2 になります。複数回指定した場合の値は、`argparse` の通常の引数処理に従い最後の指定です。
- `--json` を併用すると、引数解析後に `output` が `json` に設定されます。したがって `--output human --json` でも JSON が選ばれます。

## 実行時の動作

parser は `--output` に `human`/`json` の選択肢と `human` の既定値を設定します。また `code sessions` は `--json` と `--quiet` を持つ one-shot コマンド群に含まれています（`strata_cli/cli.py:505-515`）。`main()` は `--json` を `output=json` に変換してから `_run()` を呼びます（同 `:2232-2237`）。

この revision の `_run()` は `code` を実行すると、サブコマンドにかかわらず shared Desktop harness component が未導入で coding sessions は利用できない、というエラーを返します。そのため `sessions list` の成功時に一覧がどのように整形されるかは、この checkout のコードから確認できません（同 `:2162-2164`）。

## 適用条件と副作用

`strata code sessions` の parser 自体は存在しますが、この revision ではコマンド実行時に常に未導入エラーとなります。成功したセッション一覧の取得や、ファイル・ネットワーク・プロセスへの副作用は確認できません。`--quiet` は併用できますが、人間向け情報出力を抑止するための指定です。JSON 出力時は `main()` が quiet の stdout 捕捉を行わず `_run()` へ進みます（`strata_cli/cli.py:2236-2248`）。

## 出力とエラー

- `--output human`（または省略時）は stderr に `strata: the shared Desktop harness component is not installed; coding sessions are unavailable` を出し、終了コード 5 を返します。
- `--output json` または `--json` では stdout に `{"schema_version": 1, "ok": false, "error": {"code": 5, "message": "the shared Desktop harness component is not installed; coding sessions are unavailable"}}` 形式を出し、終了コード 5 を返します。
- 上記エラー形式は `_run()` の machine 判定と `_error()` の出力処理によります（`strata_cli/cli.py:2162-2164`, `:527-532`）。
- `strata code` 自体がこの version では利用不可で終了コード 5 になることは、CLI 文書 `docs/TERMINAL.md:275-277` にも記載されています。

## 根拠

- parser 定義、`--output` の値と既定値、`--json`/`--quiet` の共通登録: `strata_cli/cli.py:494-515`
- `--json` の `output=json` への変換、および quiet 時の分岐: `strata_cli/cli.py:2232-2248`
- `code` 実行時の未導入エラーと終了コード: `strata_cli/cli.py:2162-2164`
- human/JSON エラーの出力先と形式: `strata_cli/cli.py:527-532`
- 利用不可という補足記載: `docs/TERMINAL.md:275-277`

調査時点の Strata checkout は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5` で、`git status --short --branch` は `## main...origin/main`（未コミット変更なし）でした。別 revision の help 出力や実行結果は使用していません。
