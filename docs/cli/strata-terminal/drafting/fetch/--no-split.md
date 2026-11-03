# `strata drafting fetch --no-split`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--no-split` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時は真、未指定時は偽 |

## 役割

モデル設定から「全カード分割エンジン（all-cards split engine）が起動する見込み」と判定された場合に、その判定を使ってドラフティング方式を MTP に差し替える処理を抑止します。`fetch` では、その結果 DFlash2 drafter を必要とするかどうかの判定が変わることがあります。これは `strata drafting fetch` の計画・取得判定に対するフラグであり、後続の `strata launch` で split engine の起動を禁止する設定ではありません（`strata_cli/drafting_cmd.py:68-78`）。

## 使い方

```sh
strata drafting fetch --config ./run.json --no-split --if-needed
```

`--config` を省略する場合は `--data-dir` や `--family` などで対象を指定できます。`--no-split` 自体は `fetch` と `plan` の両方に登録されています（`strata_cli/drafting_cmd.py:21-32`）。

## 値と既定値

- `argparse` の `store_true` フラグです。値は不要で、既定値は `False` です。値を渡す形式や独自の範囲検証はありません（`strata_cli/drafting_cmd.py:28-29`）。
- `--mode` を省略したときの選択は、run config の `drafting` 値を使います。設定がない場合の `auto` は `drafting.py` の既定値です（`strata_cli/drafting_cmd.py:69-75`; `strata_control/drafting.py:34-36,404-406`）。
- `--mode` は `auto`、`mtp`、`dflash2`、`off` のいずれかです（`strata_cli/drafting_cmd.py:27`; `strata_control/drafting.py:34-37`）。

## 実行時の動作

`fetch` は入力を組み立てる際、config の `args`、GPU 指定、`split_engine`、`drafting`、`user_args`、`replicas` などを使って `_split_expected` を問い合わせます。問い合わせで例外が起きた場合は split 予定を `False` として扱います（`strata_cli/drafting_cmd.py:39-51`）。

`--no-split` を指定せず、モードが `auto` で、split engine が使われる見込みなら、内部モードを `mtp` にして plan 結果に `split: true` を付けます。split engine はモデルの MTP draft layer を使い、DFlash2 drafter とは異なる取得対象になるためです。`--no-split` を指定すると、この条件分岐を通らず、元の `auto` として `needed` 等を計算します（`strata_cli/drafting_cmd.py:68-78,84-95`; `strata_control/split_engine.py:398-430`）。

その後の `fetch` は `needed` が偽でも、`--if-needed` が指定されていなければ `drafting_fetch.ensure()` を実行します。従って `--no-split` は DFlash2 の取得を直接強制するオプションではありません。取得をスキップする条件は `--if-needed` と `needed == false` の組み合わせです（`strata_cli/drafting_cmd.py:81-88,103-108,116-117`）。

split 見込みの判定は、モードが off、明示的な DFlash2/off 選択、user args または replicas があると偽になります。それ以外にもカード、メモリ、モデル・実行ファイルの条件で偽になる場合があります。判定は例外を外へ出さず偽を返します（`strata_control/split_engine.py:398-430`）。また、`--no-split` を指定しても `mtp` や `dflash2` など明示したモードは書き換えません。モード差し替えの分岐自体が `auto` のときだけ実行されます（`strata_cli/drafting_cmd.py:69-75`）。

## 適用条件と副作用

- 効果が現れるのは、`--no-split` がない場合に限り、入力モードが `auto` で、かつ `_split_expected` が真となるケースです。
- config が読めない、JSON として不正、または読み込み時に OS エラーとなる場合、CLI はその失敗をここでは報告せず空 config として続行します。その場合 `--no-split` が抑止する split 見込みも通常はありません（`strata_cli/drafting_cmd.py:54-68`）。
- このフラグの効果は `drafting fetch` の判断に限られます。fetch 自体は明示コマンドとしてネットワーク取得、検証、pack 作成を行い得ます。取得の詳細やファイル副作用は `--no-split` によるものではなく、`drafting_fetch.ensure()` の処理です（`strata_cli/drafting_cmd.py:116-127`; `strata_control/drafting_fetch.py:144-206`）。

## 出力とエラー

`--no-split` 専用の出力・警告・エラー経路はありません。`--if-needed` で取得をスキップした場合は human 出力で `Nothing to download.`、JSON/JSONL では `skipped: true` を出して終了コード 0 です。取得に失敗し `DraftingError` または `AcquisitionRefused` となった場合、machine 出力は `ok: false`、human 出力は stderr に `strata: ...` を出し、終了コード 5 です（`strata_cli/drafting_cmd.py:103-123`）。

## 根拠

- parser 定義と `plan` / `fetch` 共通スコープ: `strata_cli/drafting_cmd.py:18-32`
- config・モード・split 判定の入力と `--no-split` 条件: `strata_cli/drafting_cmd.py:39-78`
- `needed` の計算、`--if-needed` の早期終了、取得・エラー処理: `strata_cli/drafting_cmd.py:81-127`
- split 見込み判定の条件: `strata_control/split_engine.py:398-432`
- モード既定値と DFlash2/MTP/off 選択、pack 必要性: `strata_control/drafting.py:34-41,653-691,712-722`
- fetch の取得・pack 作成と検証: `strata_control/drafting_fetch.py:144-206`
