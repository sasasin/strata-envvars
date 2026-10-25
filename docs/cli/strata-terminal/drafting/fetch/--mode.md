# `strata drafting fetch --mode`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--mode` |
| 別名 | なし |
| 値 | `auto`、`mtp`、`dflash2`、`off` のいずれか |

## 役割

モデルにどの drafting 方式を適用するかを fetch コマンドの「必要なら取得する」判定へ渡します。このオプション単独で取得対象を選択したり、実行後のモデル設定を変更したりはしません。通常の無条件 fetch では値は取得処理に影響しません。

## 使い方

```sh
strata drafting fetch --config ./run-config.json --mode dflash2 --if-needed
```

`--config` を省略してこの判定をモデル構成へ結び付けない場合は、必要に応じて `--family` と `--data-dir` も指定します。`--mode` の値を選ぶ判定を確認するだけなら、対応する `strata drafting plan` を使います。

## 値と既定値

- `--mode` は `drafting.MODES` を choices として parser に登録しており、現行値は `auto`、`mtp`、`dflash2`、`off` です。値の省略は許されます。既定値として parser が埋める値はなく、`--config` の `drafting` 値があればそれを使い、なければ `auto` 相当で判定します。
- choices 以外の値は `argparse` が拒否し、usage と invalid choice のエラーを出します。複数回指定時の扱いは argparse の通常の単一値引数です（後の値が有効値なら最後の値が残ります）。
- `--mode` と `--config` の両方がある場合、明示した `--mode` が config の `drafting` より優先します。config の読み込みに失敗した場合は空の設定として処理されます。

## 実行時の動作

`--mode`（または config の `drafting`）は `_inputs()` から `drafting.needs_pack()` に渡され、pack が未配置かつ選んだ方式が DFlash2 を必要とするかを判定します。この判定が `--if-needed` の分岐条件です。`--if-needed` があり `needed` が偽ならネットワーク取得を行わず、「Nothing to download.」または JSON の `skipped: true` を返して終了コード 0 になります。

現 revision では `ENGINE_SERVES_DFLASH2` が `False` です。そのため `needs_pack()` は `dflash2` や `auto` を含め、すべての mode で偽となり、`--if-needed` を指定した fetch は常にスキップします。一方、`--if-needed` を付けない fetch はこの判定を使って取得可否を決めず、`drafting_fetch.ensure()` を実行します。したがって `--mode` は無条件 fetch の取得量・保存先・pack 内容を変えません。

この fetch コマンドは config を読んで判定に使いますが、config を書き換えません。実際にサーバー起動へ適用される drafting 設定は別の経路です。

## 適用条件と副作用

`--if-needed` による判定は mode に加え、GPU arch から分類した card class、モデル名または family、data dir と pack の有無も参照します。DFlash2 がサポートする family は `qwen` と `gyro`、または run config の適合するモデル名です。現在は engine の serving 条件が無効化されているため、この判定では実際の取得には至りません。

無条件 fetch は `--mode` と独立に、pack が既にあればそのファイルを保持します。なければ pinned な配布元からファイルを取得・検証し、エンジン用 pack を生成して保存します。これはネットワーク通信とデータディレクトリへの書き込みを伴います。

## 出力とエラー

このオプション自身に固有の出力はありません。無効値は parser 段階で拒否されます。`--if-needed` で不要と判定された場合は成功扱いでスキップします。無条件 fetch の取得・pack で `DraftingError` または `AcquisitionRefused` が発生すると、人間向け出力は stderr に `strata: ...` を出し、JSON 系出力では `ok: false` と `drafting_failed` を返し、終了コード 5 になります。

## 根拠

- `strata_cli/drafting_cmd.py:17-29` — `plan` と `fetch` の parser。両方で同じ `--mode` choices を使い、fetch 固有の `--if-needed` を追加。
- `strata_cli/drafting_cmd.py:40-54` — config 読み込み、明示 `--mode` の優先、未指定時の config 値および data dir 解決。
- `strata_cli/drafting_cmd.py:57-99` — mode を含む入力の組み立て、`needs_pack` 判定、`--if-needed` のスキップ、無条件 `ensure()`、出力と終了コード。
- `strata_control/drafting.py:23-25,136-138` — 有効 mode と正規化時の既定値 `auto`。
- `strata_control/drafting.py:141-146,162-183` — DFlash2 serving 条件、方式決定および必要 pack 判定。
- `strata_control/drafting_fetch.py:54-102` — pack の再利用、ネットワーク取得、検証、pack 作成、元データ削除。
- `strata_control/acquisition.py:32-44,70-84` — 取得拒否時の例外と終了コード。
- 索引: [`strata drafting fetch`](../../../README.md) の `--mode` 項目。
