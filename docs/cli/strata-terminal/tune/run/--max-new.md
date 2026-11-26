# `strata tune run --max-new`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--max-new` |
| 別名 | なし |
| 値 | 整数。既定値 `128`。parser に最小値・最大値の指定はない |

## 役割

チューニング sweep の各測定で生成要求に指定する最大出力トークン数を固定します。ベースラインと候補設定の測定条件に共通する workload の一部であり、探索対象の設定値ではありません。既定値は `128` です（`terminal/strata_cli/cli.py:442-458,1836-1843`）。

## 使い方

```sh
# エンジン固有の serve protocol で測る（--engine と --model は利用環境に合わせる）
strata tune run --engine ./strata --backend cuda --model example --max-new 64

# HTTP API 経由で測る場合は、設定ファイルと正解判定用の正規表現も指定する
strata tune run --engine ./strata --backend cuda --model example \
  --max-new 64 --mode api --config ./strata-example.json --api-expect 'hash table'
```

## 値と既定値

`argparse` の `type=int` で整数へ変換し、省略時は `128` です。整数として解釈できない値は parser で拒否されます。parser と `_tune_run` の workload 組み立てには正数制約がなく、ゼロ・負数もここでは拒否・補正されず測定側へ渡ります。その場合の受理可否や結果は、選択した engine / worker の処理に依存し、この CLI のソースだけでは一律に確定できません（`terminal/strata_cli/cli.py:457-458,1836-1843`）。

## 実行時の動作

`--max-new` は `--prompt-tokens`、固定 seed `1`、temperature `0.0` とともに workload に入り、チューニング計画と比較 identity に記録されます。各候補で同じ workload を使うため、候補設定ごとに生成上限が変わることはありません（`terminal/strata_cli/cli.py:1836-1843`、`terminal/strata_control/tuning.py:800-815`）。

- 既定の `protocol` mode では、測定 harness が `GEN <max-new> ...` の行を engine の stdin に送ります。engine 固有の serve protocol で測るため、HTTP API を通した利用者の待ち時間そのものを測るモードではありません（`terminal/strata_control/tune_engine.py:507-523`、`terminal/strata_cli/cli.py:1858-1859,1913-1918`）。
- `--mode api` では値を HTTP chat completion の `max_tokens` として渡します。この mode では `--config` と `--api-expect` が必須で、どちらかがなければ標準エラーに理由を出して終了コード `2` を返します（`terminal/strata_cli/cli.py:1844-1857`、`terminal/strata_control/tune_api.py:146-163`）。これは上限値の指定であり、指定数のトークンが必ず生成される保証ではありません。

いずれの mode でもこの値は測定 workload の条件であり、測定候補の engine flags に追加される設定ではありません。測定で使う workload は比較 identity に含まれるため、異なる `--max-new` の結果は同一 workload として扱われません（`terminal/strata_cli/cli.py:1836-1843`、`terminal/strata_control/tuning.py:800-815`）。

## 適用条件と副作用

指定値は sweep のベースラインと候補測定に適用されます。engine protocol mode は候補ごとに engine subprocess を起動し、指定値を含む `GEN` 要求を送ります（`terminal/strata_control/tune_engine.py:388-420,507-523,602-616`）。API mode は候補ごとに設定ファイルのコピーを一時 JSON ファイルとして作成し、その設定で worker を起動して HTTP 要求を送ります。元の `--config` ファイルは書き換えず、一時ファイルは測定後に削除を試みます（`terminal/strata_control/tune_api.py:259-292`）。

Sweep の進捗・結果は tuning job の状態ファイルに保存されます。オプション自体は active profile を適用・変更しません。実行結果の推薦を設定へ適用する操作は別の `strata tune apply` です（`terminal/strata_control/tuning.py:364-409,470-529`、`terminal/strata_cli/cli.py:1815-1829,1913-1919`）。

## 出力とエラー

engine または worker が指定値を含む要求を拒否した場合、測定側は失敗理由を候補の状態・理由として記録し、候補を推薦対象の正常測定として扱いません（`terminal/strata_control/tune_engine.py:549-556`、`terminal/strata_control/tune_api.py:188-222`、`terminal/strata_control/tuning.py:533-570`）。`--mode api` の必須引数不足は前述のとおり終了コード `2` です。整数に変換できない引数も parser がエラーにします（`terminal/strata_cli/cli.py:457,2325-2334`）。

## 根拠

- `terminal/strata_cli/cli.py:442-458` — `tune run` parser への登録、整数型、既定値、および隣接する workload / mode オプション。
- `terminal/strata_cli/cli.py:1815-1859` — engine の存在確認、workload への格納、API mode の必須条件、各測定 harness への値の受け渡し。
- `terminal/strata_control/tune_engine.py:507-523` — protocol mode が値を `GEN` 要求へ埋め込み engine に送る処理。
- `terminal/strata_control/tune_api.py:146-163,259-292` — API mode が値を `max_tokens` として使い、候補設定コピーを用意・削除する処理。
- `terminal/strata_control/tuning.py:800-815,533-570` — workload を比較 identity と計画に含める処理、および測定失敗の記録。
- `docs/cli/README.md:683-703` — 対象 command path `tune/run` と `--max-new` の索引登録。
