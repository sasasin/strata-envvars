# `strata drafting plan --family`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--family NAME` |
| 別名 | なし |
| 値 | モデル family 名を表す文字列。parser には列挙値制約なし |

## 役割

run config がない場合などに、DFlash2 の対象モデル family を指定し、選択した drafting mode で DFlash2 が必要かどうかの判定に使います。`plan` 自体は取得計画を表示するコマンドで、family に対応するモデルを選択したり、ファイルを取得したりはしません。

## 使い方

```sh
strata drafting plan --family qwen --mode dflash2
```

`--mode` を省略した場合は config の `drafting` 値が使われ、それもなければ `auto` として判定されます。family 名は parser では検証されず、DFlash2 を明示した判定で対応 family かどうかを照合します。

## 値と既定値

- `--family` は `NAME` を1つ取ります。parser は型を文字列として受け取り、`choices` や必須指定を設けていません（`strata_cli/drafting_cmd.py:22-29`）。
- 省略時は `None` です。`--config` を指定しても family は config から読み込まず、この引数の値だけを判定関数に渡します。config からは `model_name`、`drafting`、engine 引数中のデータ directory が参照されます（`strata_cli/drafting_cmd.py:40-55`）。
- family が判定に使われる場合、大文字小文字を無視して `qwen` または `gyro` が DFlash2 対応として扱われます。それ以外は非対応です。family が `None` のときだけ、config の `model_name` が Qwen3.8-Flash-Next の名前パターンに合うかで判定します（`strata_control/drafting.py:102-112`）。
- `--mode` の受理値は `auto`、`mtp`、`dflash2`、`off` です。省略時は config の drafting 値を使い、値もなければ `auto` に正規化されます（`strata_cli/drafting_cmd.py:26,54`、`strata_control/drafting.py:23-24,136-138`）。

## 実行時の動作

`--family` は `drafting.needs_pack()` と `drafting.decide()` の双方に渡されます。`needs_pack()` は、選択 mode が DFlash2 を選び、family が対応し、実行 engine が serving で DFlash2 を使え、pack が未取得の場合に限り `true` になります（`strata_cli/drafting_cmd.py:60-66`、`strata_control/drafting.py:179-183`）。

この revision では `ENGINE_SERVES_DFLASH2` が `False` です。そのため、`--mode dflash2 --family qwen` のように対応 family を指定しても取得は必要と判定されず、実行時選択は MTP にフォールバックし、「このモードでは DFlash2 を使えない」という note が付きます（`strata_control/drafting.py:141-146,162-176`）。未対応 family を `dflash2` と組み合わせた場合は「Qwen3.8-Flash-Next 専用」という note になります。

family の省略時、`auto` は GPU architecture から分類した card class を使います。現在の suggestion 表は全 card class で MTP を選ぶため、`--family` だけを付けても DFlash2 は選ばれません（`strata_cli/drafting_cmd.py:32-38,54`、`strata_control/drafting.py:50-79`）。

`--config` は UTF-8 BOM を許容して読みます。読み込み時の `OSError` または JSON parse error は空 config として扱われます。`--data-dir` があればその directory が優先され、なければ config 内の engine 引数、さらに見つからなければ Strata の標準 data directory が使われます（`strata_cli/drafting_cmd.py:40-55`）。family 自体はこの directory 解決には関与しません。

## 適用条件と副作用

- `plan` は pack の有無・サイズを filesystem 上で確認して、取得量や表示文を組み立てます。plan 経路は `drafting_fetch.ensure()` を呼ばず、ネットワーク取得・pack 生成・ファイル削除を行いません（`strata_cli/drafting_cmd.py:57-73`、`strata_control/drafting_fetch.py:29-40,54-101`）。
- card class の取得は CUDA/HIP architecture 検出関数を呼びます。例外は捕捉され `other` になります（`strata_cli/drafting_cmd.py:32-38`）。
- `--output human` は通常、取得計画の文を表示します。mode または config を指定して pack が不要と判定され、かつ decision note がある場合は短い fallback 文を表示します。`--output json` / `jsonl` は schema version 1 の JSON を出力し、`needed`、`drafter`、`note`、`line` などを含みます（`strata_cli/drafting_cmd.py:58-73`）。

## 出力とエラー

- `--family` に未知の文字列を指定しても parser error にはなりません。DFlash2 を明示して判定した場合、未知 family は非対応として MTP に fallback します（`strata_cli/drafting_cmd.py:25-26`、`strata_control/drafting.py:107-112,168-176`）。
- `--mode` に許可されていない値を渡すと `argparse` が受け付けず usage error になります（choices 定義: `strata_cli/drafting_cmd.py:26`）。
- plan 分岐は成功時 `0` を返します（`strata_cli/drafting_cmd.py:63-73`）。fetch 時のダウンロード失敗・拒否・pack 失敗はこのオプションの plan 経路には該当しません。

## 根拠

- `strata_cli/drafting_cmd.py:17-29` — `plan` / `fetch` 共通 parser と `--family`、mode、出力形式の定義。
- `strata_cli/drafting_cmd.py:32-73` — card class、config / data directory の解決、family の転送、plan 出力と終了コード。
- `strata_control/drafting.py:50-79,102-112,136-183` — Auto の選択、family 対応判定、mode 正規化、DFlash2 利用可否と必要 pack 判定。
- `strata_control/drafting_fetch.py:29-40,54-101` — 読み取り専用の計画生成と、plan から呼ばれない fetch / pack 処理。
