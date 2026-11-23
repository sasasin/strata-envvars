# `strata components add-build --feed`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components add-build <folder>` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | 文字列を1つ取る。型変換・形式検証はない |

## 役割

このコマンドでは `--feed` は受理されますが、値は使用されません。`--feed` は `update_cmd._common()` が update 系コマンド共通の引数として登録しますが、`add-build` の実行分岐は feed の選択・取得を行う処理より前に専用ハンドラーへ進みます。そのため、URL やフォルダーを指定しても、追加するローカル build の検証・登録・切り替えには影響せず、ネットワークアクセスも発生しません（`terminal/strata_cli/update_cmd.py:47-56,142-152,339-341,351-355`）。

## 使い方

```sh
strata components add-build ./build --feed https://example.invalid/strata-feed.json
```

この例の `--feed` 値は parser に渡されますが、`add-build` では無視されます。`./build` にはエンジン実行ファイルなどのローカル build が必要です。このコマンドは build をコンポーネント領域へコピーして使用中のエンジンに切り替えるため、実行するとローカル状態が変更されます（`terminal/strata_cli/update_cmd.py:95-99,425-441`、`terminal/strata_control/local_engine.py:127-130,153-173`）。

## 値と既定値

parser の定義は `default=None` で、`type`、`choices`、`metavar`、Strata 独自の値検証は指定されていません。引数を省略した場合は `None` になり、値を指定すれば文字列として受理されます。値を欠いた場合は引数 parser が usage error（終了コード 2）にします。値が URL かフォルダーか、実在するか、空文字列かは `add-build` の実行時には検証されません（`terminal/strata_cli/update_cmd.py:47-49`）。

共通 parser の help 文は URL またはフォルダーを「署名済み update feed の場所」と説明し、既定の供給元として `STRATA_UPDATE_FEED`、記憶済み feed、プロジェクトの feed を挙げています。ただしこの説明は共通定義によるもので、`add-build` には適用されません。実際の feed 選択関数 `_feed_source()` は `a.feed`、環境変数、記憶済み feed を調べますが、`add-build` はこの関数へ到達しません（`terminal/strata_cli/update_cmd.py:47-49,142-152,339-355`）。

## 実行時の動作

`--feed` の値は `add-build` の処理では読み出されません。`run()` は `add-build` の場合、`_add_build_command()` を呼び出して戻ります。feed の選択と署名鍵の読み込みはその後にある通常の update 処理でのみ行われます。したがって `--feed` と `STRATA_UPDATE_FEED` のどちらを指定しても、`add-build` が参照する build フォルダーやコンポーネント保存先、backend の決定には影響しません（`terminal/strata_cli/update_cmd.py:303-321,337-355`）。

`--feed` 以外の `add-build` の実処理では、ローカル build の内容と実行可否を確認し、build ファイルをコンポーネント領域へコピーして manifest を作成した後、そのエンジンを使用中に切り替えます。feed からのダウンロードは行いません（`terminal/strata_cli/update_cmd.py:425-441`、`terminal/strata_control/local_engine.py:127-173`）。

## 適用条件と副作用

`--feed` は `strata components add-build` parser に登録されているため構文上は使用できますが、同コマンドでは効果がありません。feed が不正または到達不能でも、それを理由に失敗する経路はありません。コマンド本体は別途ローカル build の検査、ファイルのコピーと manifest 作成、エンジン切り替えを行います（`terminal/strata_cli/update_cmd.py:95-99,425-441`、`terminal/strata_control/local_engine.py:131-173`）。

## 出力とエラー

`--feed` 自体は出力・警告・終了コードを変えません。成功時は人間向け出力または `--output json` / `--output jsonl` に応じた機械可読出力になり、失敗した build 検証などは通常の `add-build` エラー経路で報告されます（`terminal/strata_cli/update_cmd.py:303-311,425-442`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — `--feed` の parser 定義と共通引数としての登録。
- `terminal/strata_cli/update_cmd.py:95-99` — `add-build` parser が `_common()` を使うこと。
- `terminal/strata_cli/update_cmd.py:142-152` — feed の値、環境変数、記憶済み値から feed を選ぶ関数。
- `terminal/strata_cli/update_cmd.py:303-321,337-355` — `add-build` が feed 選択処理より前に専用処理へ分岐すること。
- `terminal/strata_cli/update_cmd.py:425-442` — 専用ハンドラーが feed を引数に使わず、ローカル build を追加して切り替えること。
- `terminal/strata_control/local_engine.py:127-173` — build の検証、コピー、ローカル manifest 作成、保存処理。
