# `--plan`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 取らないフラグ。指定すると真になる。 |

## 役割

`strata launch` が選んだ設定で何を行うかを計算して表示し、起動せずに終了します。通常の起動に進む前に、モデル、設定、ダウンロード見込み、警告などを確認するための表示モードです。parser は `action="store_true"` で定義し、help 文でも「何が起きるかを表示して終了、変更なし」としています（`strata_cli/launch/cmd.py:27,152`）。

## 使い方

```sh
strata launch --plan --model q2_0
```

保存済み preset の設定を基に確認する場合は、起動先を `--preset` で指定できます。モデルを指定しない場合は、後述のとおりコンピューターに合わせた候補選択も行われます。コマンド例は `strata_cli/launch/cmd.py:27` にあります。

## 値と既定値

- `--plan` 自体に値はありません。省略時は通常の対話式または起動処理に進みます（`strata_cli/launch/cmd.py:152,880-901,924-954`）。
- 同時に `--output json` を指定すると JSON 形式で計画を返します。`--output` の既定値は `human` です（`strata_cli/launch/cmd.py:154,790,927-928`）。
- preset を指定したときは、その設定を読み込んで CLI の指定を重ねます（`strata_cli/launch/cmd.py:212-231`）。モデル未指定かつ preset にもモデルがない場合、ハードウェアに基づく推奨モデルを選びます。推奨が得られないとエラーになります（`strata_cli/launch/cmd.py:372-384`）。

## 実行時の動作

`run_launch()` は `--plan` があると対話画面を無効にし、設定と既定値を適用した後に `runner.plan()` を呼びます。人向け表示にはモデル、context、画像・並列設定、ダウンロード見込み、drafting、speed、必要なら DeepSeek の配置情報、tuning/access/port、警告、再現用フラグを出します。成功時は終了コード `0` で終了し、通常起動の `runner.run()` には進みません（`strata_cli/launch/cmd.py:874-880,906-954,980-982`）。

計画データには設定と警告、モデル情報、想定ステップ、ダウンロード対象・容量、drafting と speed の説明が含まれます。DeepSeek の複数ファイルモデルでは配置情報を加え、`--parallel` が明示されて 1 より大きい場合に限り並列数の説明も加えます（`strata_cli/launch/runner.py:2398-2430`）。JSON 形式は `schema_version: 1`, `ok: true`, `plan` の形です。設定シリアライズでは API key の実値を出さず、設定済みなら `"set"` とします（`strata_cli/launch/runner.py:2413-2423`; `strata_cli/launch/settings.py:149-153`; `strata_cli/launch/cmd.py:927-928`）。

`download_plan()` はローカルのモデル・コンポーネント状態を調べ、不足するモデルファイル、draft layer、画像 reader、drafter などを見積もります。DeepSeek では共有ファイルも計算対象です。見積もり中に例外が起きた場合は「容量を計算できなかった」という結果を返して他の計画表示を続けます（`strata_cli/launch/runner.py:2249-2307,2317-2355,2408-2412`）。

## 適用条件と副作用

- 計画分岐ではモデルや engine のダウンロード、サーバー起動、設定書き込み、preset 保存には進みません。`--save-preset` を併記しても計画分岐で `store.save()` に到達しません（`strata_cli/launch/cmd.py:924-954,980-997`）。
- `--data-dir` と `--move-data` を併記しても既存モデルの移動は行いません。計画モードでは移動選択関数が false を返す条件に当たります（`strata_cli/launch/cmd.py:635-650`）。
- `--backend` を指定した場合、値はこのプロセスの環境変数に反映されますが、`--plan` 中は次回以降のための保存処理を呼びません。`auto` / `default` / `none` は保存済み選択を消さずに、現在のプロセス環境から backend 指定を外します（`strata_cli/launch/cmd.py:847-867`）。
- LAN などローカル以外への共有で key が必要な場合、通常起動と同様に既存 key を読み取るか新しい key をメモリー上で生成することがあります。計画表示は key の有無だけを示し、計画分岐では preset に保存しません（`strata_cli/launch/cmd.py:917-925,945-946`; `strata_cli/launch/settings.py:149-153`; `strata_cli/launch/cmd.py:437-446`）。
- 計画生成はハードウェア情報、モデル一覧、インストール状態、指定されたモデルファイルや保存済み preset を読み取ります。したがってローカル環境の検出結果に依存し、実際の起動可否や容量は実行時点で変わり得ます（`strata_cli/launch/cmd.py:868-874,909-925`; `strata_cli/launch/runner.py:1459-1480,2379-2423`）。
- `--plan` 単独で起動専用のモデル選択肢がない場合も計画分岐には進みます。選択可能な推奨があればそれを使い、見つからなければエラーになります（`strata_cli/launch/cmd.py:888-903,924-954,377-384`）。

## 出力とエラー

- 人向け出力は計画の各項目と最後の `Nothing was changed.` です。`--output json` では成功計画を JSON にします（`strata_cli/launch/cmd.py:927-954`）。
- 不正なモデル指定、引数間の矛盾、無効な `--model-path` などは失敗します。JSON モードでは `{schema_version, ok: false, error: {code, message}}`、通常モードでは標準エラーに `strata: ...` を出します。`argparse` の値変換エラーも parser の通常の usage/error 経路です（`strata_cli/launch/cmd.py:48-52,65-72,792-797,909-916,1048-1053`）。
- モデル一覧など必要なカタログを利用できない場合は終了コード `5`、設定・入力エラーは通常終了コード `2` です。計画中に自分のモデルファイルの検査で `LaunchError` になった場合は、その例外のコードを返します（`strata_cli/launch/cmd.py:868-874,902-916`; `strata_cli/launch/runner.py:1459-1474`）。

## 根拠

- `strata_cli/launch/cmd.py:27,75-82,152,154` — コマンド例、コマンド説明、`--plan` と出力形式の parser 定義。
- `strata_cli/launch/cmd.py:786-797,847-880,906-954` — backend の扱い、対話抑止、設定後の計画分岐、表示と終了。
- `strata_cli/launch/cmd.py:212-309,372-452` — preset と引数の合成、モデル選択・既定値・警告。
- `strata_cli/launch/cmd.py:635-650,980-997` — データ移動判定と、計画分岐後の通常起動・preset 保存。
- `strata_cli/launch/runner.py:1459-1480,2249-2355,2379-2430` — 指定ファイル検査、ダウンロード見積もり、警告・計画情報の生成。
- `strata_cli/launch/settings.py:149-153,208-226` — API key のマスクとアクセス設定の検査。
