# `strata drafting plan --no-split`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--no-split` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる |

## 役割

通常の計画では、条件が合えば「全カード split engine が起動する」と見込み、ドラフト方式を MTP に切り替えて計画する。このフラグはその見込みを無効にし、全カード split engine が起動しない前提で計画する。計画だけを変える指定であり、実際の engine 起動を直接制御するオプションではない。

## 使い方

```sh
# run config を使い、全カード split engine を見込まずドラフト計画を表示する
strata drafting plan --config ./model.run.json --no-split
```

## 値と既定値

値や別名はない。parser は `store_true` として登録しているため、省略時は偽、指定時は真になる。同じフラグを繰り返しても真のままで、値を伴う形式は定義されていない。`--mode` が省略された場合のドラフト選択は run config の `drafting` 値を使い、それもなければ `auto` として正規化される。`--mode` が明示される場合は `auto`、`mtp`、`dflash2`、`off` のいずれかを選べる（`terminal/strata_cli/drafting_cmd.py:24-31`、`terminal/strata_control/drafting.py:37-38,882-884`）。

## 実行時の動作

parser は同じ `--no-split` を `strata drafting plan` と `strata drafting fetch` の両方に登録している。この文書の対象は索引に従って `plan` のみである（`terminal/strata_cli/drafting_cmd.py:19-38`）。

`plan` は config などからモデル、drafting mode、実行引数を読み、明示された `--mode` があればそちらを使う。config の `mtp` が `false` で mode が `auto` のときは先に `off` へ変える。それ以外で正規化後の mode が `auto` または `mtp` なら、通常は全カード split engine の見込みを調べるが、`--no-split` がある場合はその判定を呼ばず、mode を split 用の `mtp` に上書きする分岐にも入りません（`terminal/strata_cli/drafting_cmd.py:101-125`）。

このため、フラグは全カード split engine を理由とする MTP 選択を抑えます。DFlash2 を強制するものではなく、モデル・backend・実行条件・ドラフトファイルの有無に基づく通常の選択処理が続きます（`terminal/strata_control/drafting.py:1548-1587`）。既定の「auto」選択などが別の理由で MTP を選ぶ場合、その選択までは無効にしません。`dflash2` または `off` の mode では split 見込み分岐自体が適用されないため、このフラグによる mode 変更はありません。

全カード split engine の判定は `split_engine.expected` が行い、split engine の mode、カード・メモリ、モデル、engine 実行ファイル等を条件にします。判定中の例外は「split しない」として扱われます（`terminal/strata_cli/drafting_cmd.py:45-61`、`terminal/strata_control/split_engine.py:477-513`）。ここで抑止されるのは全カード split engine の計画であり、通常の layer split まで無効にする指定ではありません。

## 適用条件と副作用

`strata drafting plan` はダウンロード予定を説明するコマンドで、ファイルや engine 設定を変更しません（`terminal/strata_cli/drafting_cmd.py:22-23,247-266`）。human 出力は計画テキストを表示し、`--output json` または `jsonl` では結果を JSON として出力します。指定した model/config で DFlash2 を取得する必要がなければ、表示用の必要量を `0` にし、準備状態によっては `Nothing to download.` とします（`terminal/strata_cli/drafting_cmd.py:251-265`）。

デスクトップアプリは全カード split 用の MTP 層を取得できなかった場合、`drafting plan` を `--no-split` 付きで再照会し、続く DFlash2 drafter の判定・取得にも同じ指定を渡します（`app/host/server/native-control.mjs:610-616`）。このアプリ経路でも、本フラグ自体がダウンロードを行うわけではありません。

無効な追加値や未知の引数に対する専用エラー処理はこのオプション用には実装されていません。parser は値なしフラグとして定義されています（`terminal/strata_cli/drafting_cmd.py:30-31`）。

## 根拠

- `terminal/strata_cli/drafting_cmd.py:19-38` — `drafting plan` / `fetch` の parser、flag の型、scope。
- `terminal/strata_cli/drafting_cmd.py:101-125` — config と mode の解決、および `--no-split` による split 見込み分岐の抑止。
- `terminal/strata_cli/drafting_cmd.py:247-266` — plan の結果組み立てと出力。
- `terminal/strata_control/split_engine.py:477-513` — 全カード split engine の予測条件と例外時の扱い。
- `terminal/strata_control/drafting.py:37-38,882-884,1548-1587` — mode の候補・既定値、ドラフト方式の通常判定。
- `app/host/server/native-control.mjs:610-616` — MTP 層を取得できない場合にアプリが再計画・取得へ渡す指定。
