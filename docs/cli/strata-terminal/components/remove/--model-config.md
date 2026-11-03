# `strata components remove --model-config`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | `RUN_CONFIG.json` として表示される値。parser は文字列として受け取り、型・選択肢・パスの検証を指定しない |

## 役割

このオプションは、共通 parser 上では「テスト起動に使うモデルの run config」を指定する引数です。しかし `strata components remove` はエンジンを削除する経路で、run config をテスト起動に使いません。このコマンドでは値は受理されますが、削除処理に影響しません。

## 使い方

```sh
strata components remove 0.1.54 --model-config /path/to/run.json
```

これは構文例です。`--model-config` はこのコマンドでは参照されないため、例のファイルを読み込んだり検証したりしません。削除対象は位置引数 `engine` で指定します。

## 値と既定値

- `_common()` が `--model-config` を `default=None`, `metavar="RUN_CONFIG.json"` で登録しています。`type` や `choices`、専用 validator の指定はありません（`strata_cli/update_cmd.py:47-56`）。
- `remove` parser は位置引数 `engine` と `--family` を定義した後、この共通引数群を追加します（`strata_cli/update_cmd.py:88-91`）。値を省略した場合は `None` です。
- `strata_cli/update_cmd.py:254-256` で値は `Context.run_config` に格納されますが、`remove` の処理では参照されません。したがって存在しないパスや不正な JSON を指定しても、このオプション自体を理由とするエラーにはなりません（削除処理が別の理由で失敗する可能性はあります）。

## 実行時の動作

1. `run()` は `a.model_config` を `Context.run_config` に渡します（`strata_cli/update_cmd.py:244-256`）。
2. `components_command` が `remove` の場合、`_engines_command()` に進みます（`strata_cli/update_cmd.py:272-273`）。
3. `_engines_command()` は engine 一覧から `engine` と任意の `--family` に一致する項目を選び、`lib.delete_engine()` を呼びます。呼び出しに渡されるのは context、family、folder、root であり、run config は引数として渡されません（`strata_cli/update_cmd.py:358-360,378,395`）。
4. `delete_engine()` 内でも `ctx.run_config` は参照されず、engine の一覧・削除可否を調べて対象フォルダーを削除します（`strata_control/engine_library.py:294-334`）。

対照として、`Context.run_config` は更新後 engine の test start 経路で使われ、値があればそのパスから JSON を読みます（`strata_control/updater.py:988-1005`）。この用途は更新処理のもので、`remove` の実行経路には接続されていません。

## 適用条件と副作用

- `--model-config` の指定による削除条件・選択・設定変更はありません。モデルの run config を変更・削除せず、削除対象エンジンの選択にも使いません。
- 実際の削除では、稼働中のプログラムが使用している engine、および現在使用中の engine は拒否されます。削除先フォルダーを一時名 `.deleting-<識別子>` に rename してから再帰削除し、Qwen engine では更新状態の pin/previous/failed 情報や履歴も必要に応じて更新します（`strata_control/engine_library.py:167-176,294-334`）。
- `--family` は `qwen` または `deepseek` の選択に関わります。`engine` は版番号またはフォルダー名として照合され、複数一致ならフォルダー名を使うようエラーになります（`strata_cli/update_cmd.py:88-91`; `strata_control/engine_library.py:198-211`）。

## 出力とエラー

- 成功時は通常出力で削除した版と解放容量を表示し、JSON/JSONL モードでは成功結果を JSON で出力します（`strata_cli/update_cmd.py:395-400`）。`--json` と `--quiet` は個別 parser 宣言ではなく、CLI が update parser 群へ追加します（`strata_cli/cli.py:508-515`）。
- 対象が見つからない、指定が曖昧、現在使用中、または稼働中のプログラムが使用している場合、`UpdateError` code 2 で拒否されます（`strata_control/engine_library.py:198-211,294-309`）。通常表示では stderr、機械可読出力ではエラー JSON になり、終了コードが返されます（`strata_cli/update_cmd.py:237-242,307-311`）。
- フォルダーを退避名へ rename できない場合は、何も変更していない旨を含む `UpdateError` code 6 になります（`strata_control/engine_library.py:310-317`）。
- `--model-config` の欠落・不正値・参照先の読み込み失敗による出力や終了コードは、この remove 経路ではありません。削除実装がこの値を読まないためです。

## 根拠

- parser と既定値: `strata_cli/update_cmd.py:47-56,88-91`
- context への格納とコマンド分岐: `strata_cli/update_cmd.py:244-256,272-273`
- `remove` の対象解決・削除呼び出し・成功出力: `strata_cli/update_cmd.py:358-360,378-400`
- 削除可否判定、rename・削除・状態更新: `strata_control/engine_library.py:167-176,294-334`
- 更新の test start で run config を読む別経路: `strata_control/updater.py:988-1005`
- JSON/quiet の後付けと失敗出力: `strata_cli/cli.py:508-515`; `strata_cli/update_cmd.py:237-242,307-311`

調査範囲は上記 commit の checkout 内の Terminal CLI と engine library です。同一 revision の CLI `--help` や Release 配布物は確認していません。parser と実行経路のソースから、`remove` では値が使用されないことを確認しました。
