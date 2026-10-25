# `strata code run --quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code run` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。既定値は `false` |

## 役割

人向けの案内出力を抑えるフラグとして定義されています。ただし、この revision の `code` コマンドは共有 Desktop harness が未導入として終了する実装であり、`code run` の正常な harness 実行や、その実行中の人向け出力抑制はまだ行われません。

## 使い方

```sh
strata code run --prompt-file PROMPT.txt --policy POLICY.json --quiet
```

`--prompt-file` と `--policy` は必須です。上記は parser が受け付ける構文例であり、現行実装では harness のターン実行には至りません（下記「実行時の動作」参照）。

## 値と既定値

- `store_true` のため値を指定せずに付けます。省略時は偽、指定時は真です。
- `code run` parser での既定値は `argparse.SUPPRESS` です。親の `strata code` parser にも同名フラグがあり、`strata code --quiet run ...` と `strata code run ... --quiet` の両方で同じ `quiet` 属性を真にできます。
- 繰り返し指定しても真のままです。値（例: `--quiet=true`）を取る定義ではありません。
- `--output` は `jsonl` のみを選べ、既定値も `jsonl` です。

## 実行時の動作

parser は `code run` に `--quiet` を登録しますが、トップレベル dispatcher は `a.command == "code"` の場合、共有 Desktop harness がない旨をエラーとして返します。`code_command` を `run` と判定して別の runner に渡す処理は、この経路にはありません。

`main()` の静かな人向け出力の捕捉処理は、`quiet` が真でも `output` が `json` または `jsonl` なら実行されません。`code run` は `jsonl` 固定なので、このオプションで失敗通知を隠したり、機械可読出力を抑止したりはしません。現在の dispatcher は機械形式のエラーを stdout に出力し、終了コード `5` を返します。

## 適用条件と副作用

- この option は `strata code run` の parser に属します。親 parser の `strata code --quiet` もありますが、この文書は索引の階層どおり `run` parser 側を扱います。
- 対象 commit では harness が未導入として処理が終了し、prompt や policy の読み込み、coding session の実行には進みません。`--quiet` 自体によるファイル変更・ネットワークアクセス・子プロセス起動は確認できません。
- CLI 共通の起動処理では、利用可能な場合に `private_files.adopt_user_defaults()` を呼びます。これは `--quiet` 固有の副作用ではありません。

## 出力とエラー

- `--prompt-file` または `--policy` が欠けている場合や、`--output` に `jsonl` 以外を指定した場合は、`argparse` が実行前に構文エラーとして拒否します。
- 必須引数を満たして実行すると、現行 dispatcher は `{"schema_version":1,"ok":false,"error":{"code":5,"message":"the shared Desktop harness component is not installed; coding sessions are unavailable"}}` 相当の JSON 1 行を stdout に出し、終了コード `5` を返します。`--quiet` はこの機械形式の出力を抑えません。
- 利用者向け `docs/TERMINAL.md` も、この revision の `strata code` が終了コード 5 で harness 未導入を報告すると説明しています。

## 根拠

- `strata_cli/cli.py:494-504` — 親 `code` と子 `run` の parser 定義。`--quiet` は引数なしで `store_true`、run 側 default は `argparse.SUPPRESS`。`--output` は `jsonl` 固定。
- `strata_cli/cli.py:527-532` — エラーを machine mode では JSON として stdout に出し、指定コードを返す処理。
- `strata_cli/cli.py:2162-2164` — `code` の dispatcher は harness 未導入エラー（コード 5）を返す。
- `strata_cli/cli.py:2217-2248` — CLI の parse、`jsonl` 出力時に quiet capture を迂回する条件、および人向け出力を捕捉する経路。
- `docs/TERMINAL.md:275-277` — 利用者向け資料にある `strata code` の現行制約。
