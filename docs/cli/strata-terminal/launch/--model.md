# `strata launch --model`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--model` |
| 別名 | なし |
| 値 | `NAME`。カタログに登録されたモデルサイズ名 |

## 役割

起動するモデルサイズを選びます。名前は大文字・小文字を区別せず照合され、カタログ上の正式表記に解決されます。複数のファミリーに同じサイズがある場合は [`--family`](--family.md) でファミリーを指定できます。`--preset` と併用すると、保存済み設定を基礎にしつつ、この起動で使うモデルを上書きします。

## 使い方

```sh
strata launch --model iq3_xxs --no-tui
strata launch --preset "Office" --model q2_0 --plan
strata launch --model iq3_xxs --model-path /data/models/IQ3_XXS --no-tui
```

通常起動ではモデルの準備後にサーバーを起動します。`--plan` を付ける例は計画を表示して終了します。既存ファイルを使う場合は `--model-path` も指定します（その値の扱いは [`--model-path`](--model-path.md) を参照）。

## 値と既定値

- parser は `NAME` を必須値として受け取ります。parser 自体に `choices` や型変換、既定モデルはありません。`--model` の省略時は preset のモデルやモデルファイルから判定でき、どちらもなければ後段で PC 別推奨モデルを選びます。選択肢を付けず対話端末から呼んだ場合は、モデルを選ぶ案内画面が先に開きます。
- `Catalog.resolve()` はモデル名をカタログ内の名前と大文字・小文字を無視して照合します。該当がなければ候補モデル名と、あれば近い候補を含む `ValueError` になります。
- `--family` を併記した場合、ファミリー名はカタログ内の識別子と完全一致で照合され、そのファミリーが当該サイズを提供する必要があります。未登録ファミリーまたは組み合わせ不一致はエラーです。
- `--family` を省き、同じモデルサイズを複数ファミリーが提供するときは、`qwen` が候補にあれば `qwen`、なければカタログ順で最初の候補が選ばれます。

## 実行時の動作

設定は空の `LaunchSettings` または指定 preset から始まり、`--model` があればカタログで解決した `(family, model)` を設定します。`--model-path` が同時にない場合は preset に保存されたモデルファイルのパスをクリアします。`--model-path` だけを指定した場合は、preset にモデルが保存されていても family と model をクリアし、ファイルからモデルを判定する経路へ渡します（`strata_cli/launch/cmd.py:197-217`）。

通常の起動処理では、解決した family と model を `setup.py` に `--family` / `--model` として渡します。モデル準備では既存のインストール済み設定を再利用できる場合があり、それ以外は setup を子プロセスとして呼びます。準備後は launch 用設定を作成して profile に保存し、チューニングを経てサーバーを開始します。モデルファイルのダウンロードや設定作成は `--model` の値に応じて起こり得ます（`strata_cli/launch/runner.py:727-759, 925-959, 2011-2044`）。

`--model-path` と併用した場合、ファイルを先に検査します。DeepSeek-V4.1-Flash の shard と判定されるファイルはモデル指定がなくてもモデル名を補い、別ファミリーを明示した場合は拒否します。一般のファイルで `--model` も指定した場合、ヘッダー判定が指定モデルと異なっても直ちには拒否せず、指定したモデルのファイルをそのフォルダーから探す旨を通知します（`strata_cli/launch/runner.py:1116-1147, 1156-1198`）。

## 適用条件と副作用

- Terminal CLI に同梱されたモデルカタログが必要です。カタログを読み込めず `--model` が指定されている場合はエラーになります。
- PC に適合しないと判定されたモデルも起動を禁止せず、警告を出して試行を続けます。起動が遅い、またはメモリー不足になる可能性があると説明されます。
- 選んだモデルによっては大きなモデルファイルや engine の取得、ローカルの run config / profile の作成、推論サーバーの起動が発生します。`--plan` は別経路で計画を出して終了し、実変更を行いません。
- 同じ選択・同じ port ですでに serving 中なら再起動せず既存サーバーを再利用します。異なる選択が同じ port を使う場合、`--restart` がなければ対話時は確認し、確認できない実行ではエラーになります。別 port の server は並行稼働し得ます（`strata_cli/launch/runner.py:1505-1539`）。

## 出力とエラー

モデル名、ファミリー名、またはその組み合わせが不正な場合、`ValueError` は通常、人向けでは `strata: ...` を stderr に出して終了コード 2、`--output json` では `ok: false` とエラー情報を含む JSON に変換されます。モデルカタログがなく、モデルまたはモデルファイルのパスを指定した場合は終了コード 5 です。独自ファイルのパス・内容検査も失敗し得ます（`strata_cli/launch/cmd.py:630-641, 679-685, 832-835`、`strata_cli/launch/catalog.py:350-374`）。

## 根拠

- `strata_cli/launch/cmd.py:83-90` — `strata launch` parser。`--model` は `NAME` を取り、例と大文字小文字の扱いを説明する。別コマンド `strata connect` にも独立した `--model` があるが、本書のスコープは `strata launch`。
- `strata_cli/launch/cmd.py:197-217` — preset、`--model`、`--family`、`--model-path` の設定合成。
- `strata_cli/launch/catalog.py:350-374` — 大文字小文字を無視したモデル照合、family 検査、候補選択。
- `strata_cli/launch/cmd.py:302-340` — 未指定時のモデル推奨、適合警告、モデル固有の補正。
- `strata_cli/launch/runner.py:727-759,925-959,2011-2044` — setup への値の転送、モデル準備と launch の実行順。
- `strata_cli/launch/runner.py:1116-1147,1156-1198` — 既存モデルファイルからの判定と明示モデルとの相互作用。
- `strata_cli/launch/runner.py:1505-1539` — 既存 server がある場合の再利用・再起動条件。
- `strata_cli/launch/cmd.py:630-641,679-685,832-835`、`strata_cli/launch/catalog.py:350-374` — エラー出力形式と終了コード。

同一 revision の CLI `--help` は実行せず、checkout の parser 定義と使用箇所を確認しました。リリース配布物の確認、build、テスト、GPU 実行、性能測定は行っていません。
