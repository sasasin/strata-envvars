# `strata tune run --prompt-tokens`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--prompt-tokens N` |
| parser の既定値 | `512` |

## 概要

測定スイープ全体で使う workload の prompt 長を指定します。整数として受け取り、指定しない場合は512です。`--max-new` とともに、候補間で固定される workload の一部になります。

```sh
strata tune run --engine ./strata --backend cuda --model example \
  --prompt-tokens 4096
```

## 値と検証

- parser は `type=int` で値を整数に変換します。整数として解釈できない値は argparse のエラーになり、コマンド処理に入る前に失敗します。
- parser に正数などの範囲検証はありません。0 や負数も整数としては受理されます。
- protocol モードの実際の prompt token 列は `max(1, int(prompt_tokens))` 個生成されます。そのため0以下を指定すると、指定値のままではなく1 token の workload が実行されます。
- API モードではこの数値を HTTP prompt 長として使いません（後述）。

## 効果と適用条件

`strata tune run` は、`--prompt-tokens`、`--max-new`、seed `1`、temperature `0.0` から共通の workload を組み立て、計画と測定関数に渡します。この workload は候補間で同じです。prompt 長を増やすと測定対象の prompt 処理量が増え、prompt prefill の計測値にも関係します。

### `--mode protocol`（既定）

protocol 測定では、各候補の engine を起動し、`GEN` 要求に `--prompt-tokens` の長さに基づく token ID 列を含めます。実装は固定の決定的な列 `[1000 + (i % 97)]` を作り、モデル固有 tokenizer による文章の token 化ではありません。候補ごとに同じ列を使い、同じ処理量を比較します。

### `--mode api`

API 測定の HTTP prompt は `--api-prompt` が指定する文字列です。API 用 measure の生成には `--prompt-tokens` が渡されず、`--max-new` は HTTP リクエストの生成上限に渡されます。このモードでも workload としての `prompt_tokens` は計画・比較 identity に含まれるため、値を変えると記録上の workload identity は変わりますが、API の送信文面やその token 数を直接指定する効果はありません。API モードでは `--config` と `--api-expect` も必須で、どちらかがない場合はエラーを出して終了コード2を返します。

## 相互作用、副作用、失敗経路

- `--max-new` は同じ固定 workload の出力長です。両方の値は baseline、候補、baseline 再測定に共通して使われます。
- parser で整数化できない値は argparse が拒否します。範囲外の整数に対する専用 validation は確認できません。
- protocol モードでは `--prompt-tokens` に従った要求を engine に送り、測定候補ごとに engine を起動します。起動失敗、要求の timeout、engine の `ERR`、不正な完了結果などはその候補の失敗として記録され、遅い測定値として扱われません。baseline 自体が失敗すると候補探索を行わず、その理由を job に記録します。
- 実行は tuning job として state directory に計画・候補・report を保存します。正常に完了した run は report を出力しますが、profile は変更しません。推奨設定の適用は別の `strata tune apply` 操作です。
- protocol モードの報告値は engine 自身の serve protocol で測った値です。ユーザーが HTTP API で待つ時間を表すものではありません。API 経由の確認には `--mode api` を使用します。

## 根拠

- Strata `strata_cli/cli.py:414-459` — `tune run` parser、`--prompt-tokens` の整数型・既定値、および関連オプション。
- Strata `strata_cli/cli.py:1708-1709,1742-1786` — `run` からの dispatch、workload への組み込み、API/protocol モード別の measure 選択と API モードの必須値検査。
- Strata `strata_control/tuning.py:723-768` — workload を plan と測定 identity に含める処理。
- Strata `strata_control/tune_engine.py:42-49,501-510,560-568` — workload の既定値、protocol 要求、prompt token 数の最低1への丸めと固定列。
- Strata `strata_control/tune_api.py:259-291` — API measure が受け取る値、候補 config の一時ファイル利用と後始末。
- Strata `strata_control/tuning.py:423-484,486-500` — baseline・候補・再測定、job の保存、測定失敗の記録。
- Strata `strata_cli/cli.py:1802-1847` — job 実行後の JSON/人向け出力、protocol/API の測定範囲と profile を変更しない旨の表示。
