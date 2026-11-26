# `strata launch --feed`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | `URL|DIR`。署名済み更新 feed の URL またはフォルダー。parser では文字列として受け取る。 |

## 役割

エンジンやモデル形状専用エンジンを取得・更新するときに参照する署名済み feed を指定する。起動コマンド内ではこの値が `strata update`、形状専用エンジン取得処理、起動計画の feed 照会、およびモデル設定を行う `setup.py` に渡される。利用できるエンジンがすでにあり更新も不要なら、通常のエンジン確認経路は feed を読まずに進む。

## 使い方

```sh
# 指定した feed を使った起動計画を表示する（feed の照会が必要な計画ではネットワークアクセスが発生する）
strata launch --plan --family qwen --model q2_0 --feed https://updates.example/strata-feed.json
```

`URL|DIR` は parser の表示上の値形式であり、実際の URL やディレクトリの妥当性は後続の feed 読み込み処理が扱う。

## 値と既定値

- `--feed` は値を1つ取る。`argparse` 登録に `type`、`choices`、独自 validator はなく、空文字列も parser 自身では拒否しない（`terminal/strata_cli/launch/cmd.py:153`）。
- 省略時、まず `STRATA_UPDATE_FEED` が使われる。その環境変数もなければ、`strata update` が記憶済みの HTTPS feed を使い、利用可能な記憶値がなければプロジェクトの既定 feed を選ぶ（`terminal/strata_cli/launch/runner.py:1094-1106`、`terminal/strata_cli/update_cmd.py:33-45,142-151`）。
- CLI 値が空文字列の場合は `self.feed` が偽となり、CLI 値なしとして環境変数・既定値へ進む（`terminal/strata_cli/launch/runner.py:1094`）。複数回指定時の扱いは Strata 独自に定義されておらず、`argparse` の通常の単一値引数として最後に解析された値が残る。

## 実行時の動作

`strata launch` の parser は値を `run_launch` に渡し、対話画面経路には `feed` として、非対話経路には `Runner` の `feed` として渡す。`--plan` でも計画処理に渡され、画面または計画で必要な tuned drafter の有無を feed に照会する（`terminal/strata_cli/launch/cmd.py:870-877,897-899,945-948`、`terminal/strata_cli/launch/app.py:127-128,162-172`）。

通常エンジンの確認では、利用可能なエンジンがありモデルに必要な最低版を満たす場合、そこで戻るため feed は参照されない。エンジンがない、または古い場合は、`--feed` があればその値を `strata update --no-control --output jsonl` に付けて子プロセスを起動する。指定がなければ子プロセスが環境変数・記憶値・プロジェクト既定値を解決する（`terminal/strata_cli/launch/runner.py:1077-1107`、`terminal/strata_cli/runner.py:1263-1269`）。

モデル固有の形状エンジンが必要な場合は、CLI 値または `STRATA_UPDATE_FEED` を feed source として直接解決し、その feed から対応エンジンを確保する（`terminal/strata_cli/launch/runner.py:1231-1248`）。通常エンジンの取得後にモデル用 `setup.py` を呼ぶ経路では、明示した `--feed` を `setup.py --feed` として転送する。環境変数は子プロセス環境にも引き継がれる（`terminal/strata_cli/launch/runner.py:1033-1043,1412-1413`）。

## 適用条件と副作用

- feed のネットワーク照会・ダウンロードは、起動時にエンジンが未導入または古い場合、形状エンジン確認時、または計画・画面が feed 掲載の tuned drafter を確認するときに起きる。通常エンジンが利用可能で必要版を満たす場合は feed を使った更新を行わない（`terminal/strata_cli/launch/runner.py:1087-1107`）。
- ダウンロードされたエンジンは `strata update` / 形状エンジン管理処理が署名等を検証して導入する。`--feed` 自体は署名検証を無効化するオプションではない（通常更新経路: `terminal/strata_cli/update_cmd.py:33-35`、形状エンジン経路: `terminal/strata_control/shape_engine.py:290-295`）。
- ローカルフォルダーや loopback feed は一回限りのテスト feed として扱われ、記憶 feed として次回へ持ち越さない。通常更新の記憶値として許されるのは HTTPS URL（`terminal/strata_cli/update_cmd.py:148-158`）。
- feed にこの PC 向けエンジンがない場合、更新コマンドが成功終了しても起動側はエンジン未導入を警告として扱う。モデルのダウンロードを続ける前に確認する経路があり、`--yes` では質問を省略する（`terminal/strata_cli/launch/runner.py:1148-1154,1271-1287`）。

## 出力とエラー

- 通常エンジン取得の子 `strata update` が非0で終わると、起動は `LaunchError`（終了コード `6`）にし、feed の指定先を見直す案内を表示する（`terminal/strata_cli/launch/runner.py:1155-1167`）。
- 形状エンジンが取得できない場合は理由を警告として記録し、モデルをダウンロードするかの確認へ進み得る（`terminal/strata_cli/launch/runner.py:1240-1246,1271-1287`）。
- `--plan` は人向け出力に「Nothing was changed.」を表示するが、feed に tuned drafter の有無を尋ねる計画経路では読み取りのための照会は行う（`terminal/strata_cli/launch/cmd.py:897-925`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:153` — `--feed` の parser 定義、値形式、help。
- `terminal/strata_cli/launch/cmd.py:870-877,897-899,945-948` — 対話画面・`Runner`・計画への値の受け渡し。
- `terminal/strata_cli/launch/runner.py:1033-1043,1077-1107` — 環境の引き継ぎ、通常エンジンの適用条件、子 `strata update` への転送。
- `terminal/strata_cli/update_cmd.py:33-45,142-158` — プロジェクト既定値、feed の優先順位、記憶可能な値。
- `terminal/strata_cli/launch/runner.py:1148-1167,1231-1248,1271-1287,1412-1413` — 更新失敗、形状エンジン、未導入時の処理、モデル設定処理への転送。
- `terminal/strata_control/shape_engine.py:290-295` — 形状エンジン取得時の検証・導入処理。
