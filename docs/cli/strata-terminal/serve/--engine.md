# `--engine`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--engine` |
| 別名 | なし |
| 値 | `strata` または `mock` |

## 役割

serve 起動時に、run config のエンジンを使う実運用経路か、GPU・モデルを使わない scripted mock 経路かを選びます。既定値は `strata` です。mock はクライアントとの接続確認などに使えるテスト用エンジンです。

## 使い方

```sh
# run config に記載された実エンジンを使って foreground で起動
strata serve --profile ./run-config.json

# 実エンジンの代わりに scripted mock を使う
strata serve --profile ./run-config.json --engine mock
```

`--profile` とその別名 `--config` は必須です。mock を選んでも profile/config の解決と読み込みは行われます。

## 値と既定値

- `strata`: 既定値。run config のエンジンを起動します。
- `mock`: scripted `MockEngine` を使い、実エンジンのプロセス、GPU、モデルを起動しません。Terminal CLI では script の内容を指定する引数は公開されておらず、server 側の既定応答が使われます。
- 他の値は parser の `choices` により拒否されます。値を省略した場合は `strata` です。

## 実行時の動作

parser は `strata` / `mock` のいずれかを受け取り、値を `server_args` の `--engine` として `serve.server.main` に渡します。起動前の計画生成では run config を読み、実エンジン引数も組み立てます。実起動時に server は config を読み、`strata` なら config から engine executable と引数を使って実エンジンを起動し、`mock` なら `MockEngine` を生成します。

`strata serve` の scope では `--profile` / `--config` が必須なので、`--engine mock` でも profile/config がない呼び出しは parser で失敗します。mock はエンジン選択のみを切り替えるため、profile/config 自体の読み込みや server の他の設定処理を省略する指定ではありません。

`--plan` を付けた場合は計画を表示して終了し、server を起動しません。その計画には `server_argv` の `--engine` 値が含まれます。実起動時は foreground server を呼び出します。

## 適用条件と副作用

値は `strata serve` の parser にのみ登録されています。低レベルの `terminal/serve/server.py` にも同名オプションがありますが、そちらは別入口の parser であり、既定値も `mock` です。この文書は索引で指定された Terminal CLI の `strata serve` scope を扱います。

`strata` は run config に基づく実エンジン起動経路です。`mock` は scripted mock エンジンを使いますが、HTTP server は通常どおり起動し、選択した host/port を使用します。どちらも foreground serve であり、`--plan` を使う場合だけ server 起動を行いません。

## 出力とエラー

- 未対応の値は argparse が不正引数として拒否し、usage とエラーを出して終了します（parser の通常の argparse エラー経路）。
- `strata` でエンジン構成・コンポーネント・tokenizer などの起動条件を満たさない場合、server の検証または起動経路で失敗します。mock では実エンジンの起動はありませんが、config の読み込み・server 起動自体のエラーは起こり得ます。
- CLI の `--output jsonl` では foreground の起動失敗を `failed` lifecycle event として出力します。終了コードは失敗経路によって異なります。

## 根拠

- `terminal/strata_cli/cli.py:67-71` — `strata serve` parser における scope、選択肢、既定値。
- `terminal/strata_cli/cli.py:821-865` — profile/config 解決、`--engine` の server 引数への転送、launch plan の生成。
- `terminal/strata_cli/cli.py:954-994` — 起動モードの検証、`--plan` 時の終了、server の foreground 呼び出し。
- `terminal/strata_cli/cli.py:868-875, 907-936` — JSONL 起動失敗イベントと終了コード処理。
- `terminal/serve/server.py:8641-8644` — 低レベル server 入口の別 parser と異なる既定値（この文書の対象外 scope）。
- `terminal/serve/server.py:8750-8755` — 渡された config の読み込みと retired config の拒否。
- `terminal/serve/server.py:8836-8839, 8870-8878` — `strata` 経路の tokenizer 条件、config 必須確認、実 engine 環境の準備。
- `terminal/serve/server.py:8957-8973` — `strata` で engine を起動し、その他の選択肢では scripted `MockEngine` を生成する分岐。
