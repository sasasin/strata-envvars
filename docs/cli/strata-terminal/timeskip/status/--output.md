# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip status` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

取得した Time-skip run の状態を、人向けの複数行表示か、機械処理向けの JSON で標準出力へ出します。run の読み込み先は `--output` ではなく `--state-dir`、`STRATA_TIMESKIP_DIR`、または OS ごとの既定状態ディレクトリで決まります。

## 使い方

```sh
strata timeskip status <run-id> --output json
```

`<run-id>` は必須の位置引数です。省略時は argparse が usage とエラーを標準エラーへ出し、終了コード 2 で終了します（`strata_cli/cli.py:371-374, 2223-2231`）。

## 値と既定値

- `human`: 既定値です。run ID、状態、workspace、prompt、各 checkpoint の ID・digest・check 結果、attempt の判断、decision と retained 情報を行単位で表示します。必要な情報がない場合は該当する行を省略します（`strata_cli/cli.py:1507-1521`）。
- `json`: 成功時に `{"schema_version":1,"ok":true,"run":...}` 形式の JSON を1行で標準出力へ出します。`run` は保存された run 全体です（`strata_cli/cli.py:1505-1506, 535-538`）。
- 他の値は parser の `choices` により拒否され、argparse の usage/error 経路になります（`strata_cli/cli.py:374`）。空文字も受理されず拒否されます。オプションの重複指定時の規則は parser の宣言では個別に定められておらず、argparse が最後に解析した値を Namespace に設定します。

## 実行時の動作

`--output` は表示形式だけを選び、run の選択や内容の変更には使われません。status 処理は `TimeSkipStore.get(run_id)` で保存済み `run.json` を読みます（`strata_cli/cli.py:1500-1506`; `strata_control/time_skip.py:715-716, 374-379`）。

保存先は明示 `--state-dir` があればそれを使い、なければ `STRATA_TIMESKIP_DIR`、さらに未設定なら `state_base()/time-skip` を使います。POSIX の `state_base()` は `$XDG_STATE_HOME/strata`（未設定時 `~/.local/state/strata`）、Windows は `%LOCALAPPDATA%\Strata`（未設定時ユーザープロファイル配下）を返します（`strata_cli/cli.py:1476-1485`; `strata_control/paths.py:13-21`）。

## 適用条件と副作用

このオプションは `strata timeskip status` にのみ属します。`timeskip run`、`list`、`apply` にも同名 option はありますが、別コマンドのスコープです（`strata_cli/cli.py:352-394`）。`--output` はファイルを書き出さず、結果は標準出力へ出します。

status の実行開始時に `TimeSkipStore` が初期化され、指定した状態ルートに `mkdir(parents=True, exist_ok=True)` を行います。そのため、読み取り目的でも状態ディレクトリが未作成なら作成されます（`strata_cli/cli.py:1485`; `strata_control/time_skip.py:695-700`）。この初期化は `--output` の値によらず行われます。

## 出力とエラー

run が見つからない場合、`TimeSkipRun.load` は `TimeSkipError` を送出し、status は終了コード 2 でエラーを返します（`strata_control/time_skip.py:374-379`; `strata_cli/cli.py:1500-1505`）。`human` では `strata: <message>` を標準エラーへ出し、`json` では `{"schema_version":1,"ok":false,"error":{"code":2,"message":"..."}}` を標準出力へ出します（`strata_cli/cli.py:527-532`）。

読み込み時のファイルシステムエラーは共通例外処理を通り、終了コード 6 でエラーになります。JSON 出力時は同じ JSON error envelope が使われます（`strata_control/time_skip.py:379`; `strata_cli/cli.py:2176-2183, 527-532`）。不正な `run.json` の JSON は `ValueError` 系の例外処理に入り、通常は終了コード 2 になります（`strata_control/time_skip.py:379`; `strata_cli/cli.py:2166-2173`）。

## 根拠

- parser、必須 run ID、選択肢と既定値: `strata_cli/cli.py:371-374`
- status の run 取得、human/JSON 出力、TimeSkipError 処理: `strata_cli/cli.py:1500-1522`
- 保存ルートの優先順位と store 初期化: `strata_cli/cli.py:1476-1485`; `strata_control/time_skip.py:695-716`
- run ファイルの読み込みと見つからない場合のエラー: `strata_control/time_skip.py:374-379`
- 既定状態パス: `strata_control/paths.py:13-21`
- 共通成功・エラー JSON と例外経路: `strata_cli/cli.py:527-542, 2166-2183`

調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更は表示されませんでした。対象ファイルはこの revision のソースに限定して確認しました。
