# `strata drafting fetch --no-split`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--no-split` |
| 別名 | なし |
| 値 | 取らない真偽フラグ。指定すると有効になる。 |

## 役割

fetch の「必要な drafter」を判定するとき、全カード split engine が今回の起動を担う見込みを考慮せず、設定された drafting mode に基づいて判定します。split engine の起動後に split 用 draft layer を取得できず、DFlash2 drafter を取得し直したい場合などに、`--if-needed` と組み合わせて使うための指定です。parser の説明にも、人が選ぶ場合と split 用 layer の取得失敗後にアプリが指定する場合が記されています（`terminal/strata_cli/drafting_cmd.py:30-37`）。

## 使い方

```sh
# 設定の drafting mode に従って DFlash2 drafter が必要か判定し、必要な場合だけ取得する
strata drafting fetch --config /path/to/run.json --no-split --if-needed
```

`--config` は実際の run config に置き換えてください。`--mode` があれば設定の mode より優先されます（`terminal/strata_cli/drafting_cmd.py:25-30,101-123`）。

## 値と既定値

- 値を取りません。`argparse` の `store_true` action なので、省略時は偽、指定時は真です（`terminal/strata_cli/drafting_cmd.py:30-31`）。
- 繰り返し指定しても真のままです。引数値の validation はありません。
- オプションを受け付ける範囲は `strata drafting fetch` です。同じ parser 定義は `strata drafting plan` にも共有されていますが、この文書は fetch の挙動を扱います（`terminal/strata_cli/drafting_cmd.py:21-38`）。

## 実行時の動作

fetch は `_inputs` で `--mode` または run config の `drafting` 値を選びます。値が `auto` または `mtp` で、`--no-split` がなく、split engine の事前判定が成功すると、内部 mode を `mtp` にし、split 用 MTP layer を使う想定として drafter の必要性を計算します。`--no-split` を指定するとこの分岐を通らず、元の mode で必要性を判定します（`terminal/strata_cli/drafting_cmd.py:101-136`）。split の事前判定は config の GPU 指定、engine 引数、context、KV 指定などを使って `split_engine.expected` を呼び、例外時は split なしとして扱います（`terminal/strata_cli/drafting_cmd.py:45-62`; `terminal/strata_control/split_engine.py:477-513`）。

この必要性判定が実ダウンロードを止めるのは `--if-needed` も指定した場合です。必要でなければ「Nothing to download.」を表示して終了し、JSON/JSONL では `skipped: true` を出します。`--no-split` により判定が必要へ変われば、後続の fetch 処理へ進みます（`terminal/strata_cli/drafting_cmd.py:240-272`）。`--if-needed` を付けない fetch は、この判定結果にかかわらず後続へ進み、`drafting_fetch.ensure_for` を呼んで DFlash2 drafter を準備します。そのため `--no-split` 単独ではこの経路の実ダウンロード対象を切り替えません（`terminal/strata_cli/drafting_cmd.py:267-305`; `terminal/strata_control/drafting_fetch.py:349-374`）。

## 適用条件と副作用

- `--no-split` が判定を変えるのは、選択 mode が `auto` / `mtp` で、split の事前判定が真になる場合だけです。`dflash2` / `off`、split 判定が偽または失敗の場合には、このフラグによる mode 補正差はありません（`terminal/strata_cli/drafting_cmd.py:120-125`; `terminal/strata_control/split_engine.py:487-513`）。
- 実ダウンロード・ファイル変更が起こるかは fetch 全体の分岐に依存します。`--if-needed` が必要判定を通した場合、tuned または標準 DFlash2 pack を取得し、pack・補助ファイルを data directory に置きます。tuned pack 取得に失敗したときは既存 stock pack に戻る経路があります（`terminal/strata_cli/drafting_cmd.py:267-305`; `terminal/strata_control/drafting_fetch.py:349-374,376-443`）。
- split 予測はホストの GPU 情報や RAM を読むことがあります。`--no-split` を指定した場合、その予測関数は短絡評価により呼ばれません（`terminal/strata_cli/drafting_cmd.py:123-125`; `terminal/strata_control/split_engine.py:497-513`）。

## 出力とエラー

- `--if-needed` により不要と判定されると、human 出力は `Nothing to download.`、machine 出力は成功・skip 結果です（`terminal/strata_cli/drafting_cmd.py:267-272`）。
- fetch に進んだ後、download/packing の `DraftingError` または acquisition refusal はエラーを出力して終了コード `5` になります。`--no-split` 自体に固有のエラー経路は確認できません（`terminal/strata_cli/drafting_cmd.py:281-301`）。

## 根拠

- `terminal/strata_cli/drafting_cmd.py:19-38` — `plan` / `fetch` 共通 parser と、`--no-split` の `store_true` 宣言。
- `terminal/strata_cli/drafting_cmd.py:101-136` — config・mode の選択、split 判定を抑止する条件と内部 mode の補正。
- `terminal/strata_cli/drafting_cmd.py:240-272` — 必要性計算、`--if-needed` による skip。
- `terminal/strata_cli/drafting_cmd.py:281-305` — fetch 呼び出し、失敗出力と終了コード。
- `terminal/strata_control/split_engine.py:477-513` — split 起動予測の条件と例外時の扱い。
- `terminal/strata_control/drafting_fetch.py:349-374,376-443` — tuned / stock DFlash2 drafter の取得と pack 処理。
