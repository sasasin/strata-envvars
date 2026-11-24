# `strata serve --parallel`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--parallel` |
| 別名 | なし |
| 値 | 整数 `N`。1〜1024 |

## 役割

推論エンジンに要求スロット数を指定し、複数リクエストを同時に処理する設定です。`strata serve --engine strata` で run config を読み込む場合に適用され、保存済み config の `parallel` 値を今回の起動だけ上書きします。設定ファイル自体はこのオプションでは書き換えません。省略時は config の値が使われ、config にも値がなければこのオプションによる並列化は追加されません。

## 使い方

```sh
# run.json の engine 設定を使い、要求スロットを4にして起動する
strata serve --engine strata --config run.json --parallel 4
```

## 値と既定値

- `argparse` の整数値として読み取り、指定時は `1..1024` の範囲を受け付けます。範囲外は usage とエラーを出して終了します（parser の `type=int` と明示的な範囲検証、`terminal/serve/server.py:9179-9180, 9299-9304`）。
- 省略時の CLI 側の値は `None` です。その場合、config の `parallel` は変更しません。指定した場合はメモリ上の config に整数を設定します（`terminal/serve/server.py:9266-9268, 9299-9304`）。
- 値を省略したり整数として解釈できない値を渡したりすると `argparse` のエラーになります。既定値は `1` ではなく未指定です。

## 実行時の動作

- 実際のエンジンを使うには `--engine strata` と `--config` が必要です。`strata serve` の engine 既定値は `mock` であり、`strata` engine を選んで config がない場合は parser エラーになります（`terminal/serve/server.py:9157-9160, 9386-9389`）。mock engine では `parallel` を推論 engine 起動引数へ変換する経路に入らないため、このオプションによる engine の並列要求は適用されません（同 `:9386-9389, 9472-9477`）。
- 通常の engine では `parallel` が1以下なら追加引数を付けず、2以上なら `--batch N` に変換します。layer split 専用 engine は `--batch` の lane 数を `min(N, 8)` にします（`terminal/serve/server_parts/engines.py:803-806, 816-825, 834-851`）。
- Inkling-2-Mini では、config に `--parallel`、`--batch`、`--slots` が既にあれば追加せず、そうでなければ `N > 1` を engine の `--parallel min(N, 64)` に変換します。従って CLI が受け付ける上限1024と、この engine に渡す上限64は異なります（`terminal/serve/server_parts/engines.py:826-833`; `terminal/serve/inkling_kind.py:241-245`）。
- Hy4-Flash の専用引数組み立ては config の `args` と手動指定引数を元にし、トップレベルの `parallel` を自動で engine 引数へ変換する処理は確認できません。Hy4 でこのオプションが実際の並列数を変えるとはソースから確認できません（`terminal/serve/server.py:3671-3674`; `terminal/serve/hy4_kind.py:104-113`）。
- 通常 engine で `N > 8` の場合、`--batch-mtp`、`STRATA_BATCH_MTP`、または layer split の条件に該当しなければ「最大8で動作する」と stdout に通知しますが、要求値 `N` 自体は `--batch N` として渡されます。engine がサポート値に調整する場合があり、実際の有効数は engine と実行条件に依存します（`terminal/serve/server_parts/engines.py:803, 845-851`）。
- `--parallel` を明示し、保存済み engine 引数に `--batch` または `--slots` があると競合エラーになります。ただし all-cards split engine の `split_engine_note` がある config は例外です。CLI オプションを省略した場合、保存済み engine 引数はこの検査の対象になりません（`terminal/serve/server.py:9302-9304`; `terminal/serve/server_parts/engines.py:809-814`）。
- engine が複数スロットで動作すると、server は同時に実行中の要求ごとに状態・レート記録を分けます。engine のスロットがない場合は従来どおり FIFO で一件ずつ処理します（`terminal/serve/server.py:5992-5996, 6023-6028`）。待ち行列の上限は別オプション `--max-queue` で設定します。
- 起動時の drafting 選択にも要求スロット数が渡されるため、並列数によって drafter の適用判断・通知が変わることがあります（`terminal/serve/server.py:3687-3695`）。
- 1枚の GPU の VRAM が要求スロット数に対して不足する条件では、serve は要求数や context を下げず、CUDA では KV window、Intel Arc では prompt chunk と reserve を調整して GPU 外へ処理を移すことがあります。変更があれば起動時に通知されます。複数 GPU、layer split、Metal などはこの自動調整の適用外です（`terminal/serve/server.py:3711-3726`; `terminal/strata_control/vram_fit.py:280-290, 312-327`）。

## 適用条件と副作用

- `--parallel` は保存済み config を直接編集せず、起動時に読み込んだ config の値を上書きします。engine 引数への変換は engine 種別により異なり、Hy4-Flash ではトップレベル値の伝播を確認できません。
- 要求スロットを増やすと engine が保持する同時要求数が増える可能性があります。必要メモリや実効スロット数は model、GPU、engine のサポートに依存し、この文書では固定値を示しません。
- engine が実際に複数スロットを持つ場合、複数要求が同時実行されます。待ち行列数の上限はこのオプションでは設定されません。
- VRAM fit による調整は、該当環境では GPU 外へ処理を移す設定を変え、serve はその調整を遅くなる可能性のある動作として通知します（`terminal/serve/server.py:3711-3720`; `terminal/strata_control/vram_fit.py:280-284`）。

## 出力とエラー

- `1..1024` の範囲外や保存済み `--batch` / `--slots` との競合は `ArgumentParser.error()` で拒否されます。argparse の通常動作として usage とエラーを標準エラーへ出し、終了コード2になります。該当する分岐は `terminal/serve/server.py:9299-9304` です。
- 通常 engine の値が8を超え、上記の抑制条件に該当しない場合、標準出力に上限通知が出ます。layer split ではこの通知条件から除外されます（`terminal/serve/server_parts/engines.py:845-851`）。

## 根拠

- `terminal/serve/server.py:9157-9180` — `strata serve` の parser 定義。`--parallel` は整数値、既定値 `None`。
- `terminal/serve/server.py:9266-9268, 9299-9304` — config 読み込み後の範囲検証、engine 引数競合検証、起動時 config への代入。
- `terminal/serve/server.py:9386-9389, 9472-9477` — `strata` engine と config の必須条件、replica / split / 通常 engine の起動分岐。
- `terminal/serve/server.py:3665-3675, 3687-3695, 3758-3759` — engine 種別ごとの引数組み立てと drafting への slot 数の受け渡し。
- `terminal/serve/server.py:3711-3726`; `terminal/strata_control/vram_fit.py:280-327` — VRAM が不足する場合の自動調整条件と engine 引数の変更。
- `terminal/serve/server_parts/engines.py:803-851` — 通常 engine、layer split、Inkling の変換・衝突・上限通知。
- `terminal/serve/inkling_kind.py:241-245`; `terminal/serve/hy4_kind.py:104-113` — Inkling のトップレベル値伝播と Hy4 の専用引数組み立て。
- `terminal/serve/server.py:5992-5996, 6023-6028` — engine batch slot の有無による要求実行経路。

`--help` は実行せず、parser と使用箇所をソースから調査しました。
