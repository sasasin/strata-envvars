# `strata drafting plan --engines-unloading`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--engines-unloading` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`、既定値 `false`） |

## 役割

現在動いている Strata エンジンが新しいモデルの起動前に停止され、GPU メモリーを返す予定である場合、そのメモリーを空き容量の判定から差し引かずに all-cards split engine の採用可否を予測します。これにより、稼働中エンジンのメモリーを理由に分割エンジンを不採用とする誤判定を避けられます。フラグ自体はエンジンの停止やメモリー解放を実行しません（`strata_cli/drafting_cmd.py:42-56,80-82`）。

この引数は `strata drafting plan` と `strata drafting fetch` の両 parser に登録されていますが、この文書の対象は `plan` です（`strata_cli/drafting_cmd.py:19-35`）。

## 使い方

```sh
strata drafting plan --config /path/to/run-config.json --engines-unloading --output json
```

`--config` には対象モデルの run config を指定します。例のパスは説明用です。デスクトップアプリは、これから停止する自分のエンジンがある場合に内部 API からこのフラグを渡します（`apps/host/server/control-runtime.mjs:291-298`、`apps/host/server/native-control.mjs:323-333`）。

## 値と既定値

- 値は不要で、指定すると真、未指定なら偽です。短縮別名はありません（`strata_cli/drafting_cmd.py:31-32`）。
- 複数回指定の特別な検証はありません。`store_true` のため指定済みの真の状態になります。
- parser 宣言で `help=argparse.SUPPRESS` が指定されているため、このオプションは通常の `strata drafting plan --help` 出力に表示されません（`strata_cli/drafting_cmd.py:31-32`）。

## 実行時の動作

1. `_inputs()` は `--config` の JSON からモデル引数と設定を読み、`--mode` があればそれを優先し、なければ config の drafting 設定を使います。config の `mtp` が `false` で mode が `auto` の場合は `off` にし、分割エンジンの事前判定を行いません。また `auto` / `mtp` 以外の mode や `--no-split` の指定でも判定しません（`strata_cli/drafting_cmd.py:61-82`）。
2. 判定対象 mode でこのフラグが真なら、`_split_expected()` は実 GPU 情報を取得しつつ、各カードの `free_mib` を `None` に置き換えたカード情報を `split_engine.expected()` に渡します（`strata_cli/drafting_cmd.py:42-56`）。通常の split engine 判定では Linux 上のカード情報、GPU 選択、RAM、モデル情報なども考慮されます（`strata_control/split_engine.py:437-471`）。
3. `free_mib=None` のカードは、空きメモリーではなくカードの全 VRAM 容量を使えるものとして計算され、通常の 700 MiB 予約も差し引かれません（`strata_control/split_engine.py:74-78,97-104`）。この結果 split が可能と判定されると、計画結果の `split` が真になり、choice は `mtp` に切り替わります（`strata_cli/drafting_cmd.py:80-82,95-105`）。
4. `plan` は結果を表示して終了します。JSON 系出力には `split`、`choice` などが含まれます。ダウンロード処理は `fetch` 側の分岐であり、`plan` は実行しません（`strata_cli/drafting_cmd.py:95-112,113-137`）。

## 適用条件と副作用

- 実際に停止する Strata エンジンのメモリーが返却される見込みのときに使う想定です。このフラグはプロセスや GPU メモリーを確認・解放せず、全対象カードの現在の空き容量値を無視します。そのため、停止後も他プロセスが占有する VRAM まで利用可能とみなすことがあります。カード上の占有分がすべて解放される予定でない場合、split 可能という判定を過大評価するおそれがあります（`strata_cli/drafting_cmd.py:51-56`、`strata_control/split_engine.py:97-104`）。
- このフラグ自体はファイル変更やダウンロードを行いません。`plan` は判定結果を表示してコード 0 で終了します（`strata_cli/drafting_cmd.py:95-112`）。
- split の事前判定中に例外が起きると `_split_expected()` は `false` を返して例外を上位へ渡しません。そのため通常は DFlash2 側の判定を続け、この例外だけでは `plan` は失敗しません（`strata_cli/drafting_cmd.py:57-58`）。
- 無効な値を後置しても値としては受理されず、未認識の引数となります。`strata` の parser は余分な引数を `ap.error()` へ渡します（`strata_cli/cli.py:2244-2259`）。ただし、このエラー時の表示形式・終了コードの詳細は対象オプション専用の処理ではなく、argparse の標準エラー経路に依存するため、ここでは個別文言を固定しません。

## 根拠

- `strata_cli/drafting_cmd.py:19-35` — `plan` / `fetch` 共通 parser、フラグ型、非表示設定。
- `strata_cli/drafting_cmd.py:42-58,61-85` — GPU の空き容量を unknown にする変換、mode / `--no-split` 等の適用条件、例外時の扱い。
- `strata_control/split_engine.py:74-78,97-104,437-473` — free memory が不明なカードの容量計算と split 事前判定。
- `strata_cli/drafting_cmd.py:95-112` — `plan` の出力と終了。
- `apps/host/server/control-runtime.mjs:291-298`、`apps/host/server/native-control.mjs:323-333` — デスクトップアプリからの内部利用と、停止対象エンジンの条件。
