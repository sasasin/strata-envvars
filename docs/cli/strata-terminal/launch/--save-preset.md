# `--save-preset`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--save-preset` |
| 別名 | なし |
| 値 | `NAME`（文字列。parser に選択肢・長さ・文字種の制約はない） |

## 役割

今回の `strata launch` に指定した設定を、次回 `--preset NAME` で再利用できる名前付きプリセットとして保存します。既存プリセットを `--preset` で読み込んだ場合は、その設定に今回の CLI 指定を重ねた結果を指定名で保存します。

## 使い方

```sh
strata launch --model q2_0 --save-preset "Office" --no-tui
```

起動が成功すると、選択した設定を `Office` というプリセット名で保存し、以降は `strata launch --preset "Office"` で呼び出せます。

## 値と既定値

- `NAME` は `argparse` の文字列引数です。既定値は `None` で、オプションを省略したときは、このオプションによる保存を行いません（`terminal/strata_cli/launch/cmd.py:142`）。
- 名前の形式検証は parser では行いません。保存時に前後の空白を除き、ファイル名には小文字化と記号等の `-` への置換、最大48文字への切り詰めを行った slug を使います（`terminal/strata_cli/launch/store.py:36-38,76-85`、`terminal/strata_cli/launch/settings.py:462-467`）。
- 空文字列は parser では受理されますが、値が偽として扱われるため、このオプションによる保存指定にはなりません。空白だけの名前は値としては真ですが、保存時に空になり `A preset needs a name.` のエラーになります（`terminal/strata_cli/launch/cmd.py:311-313,962-964`、`terminal/strata_cli/launch/store.py:76-80`）。
- 同じ slug になる名前は同じ JSON ファイルを指します。同名プリセットがあれば確認なしで内容を置き換え、元の `created` 時刻は引き継ぎます。既存ファイルが読めない場合は保存前の読み込みでエラーになり、そのまま置換はされません（`terminal/strata_cli/launch/store.py:36-38,76-85,89-104`）。

## 実行時の動作

1. `settings_from_args` は指定値を `LaunchSettings.name` に設定します（`terminal/strata_cli/launch/cmd.py:215-221,311-313`）。他の設定オプションと一緒に `--preset` も指定した場合は、既存プリセットを基礎にして CLI の設定値を重ねます（同 `cmd.py:215-220`）。
2. `--plan` の経路では起動計画を表示して保存処理より前に戻るため、`--save-preset` を付けてもプリセットは書き込まれません（`terminal/strata_cli/launch/cmd.py:897-925`）。
3. 通常起動が成功すると、設定を保存し、`last_used` を更新します（`terminal/strata_cli/launch/cmd.py:962-966`、`terminal/strata_cli/launch/store.py:160-165`）。対話画面を伴う起動では `save` 指定を画面側に渡し、適用済み設定を起動前に保存します（`terminal/strata_cli/launch/cmd.py:945-948`、`terminal/strata_cli/launch/app.py:693-710`）。
4. `Runner.run()` が失敗した場合も、実行設定ファイルがすでに書かれていればプリセット保存を試みます。まだ設定を書いていない失敗では保存しません。救済保存そのものが失敗しても起動エラーを優先し、保存例外は表に出しません（`terminal/strata_cli/launch/cmd.py:949-961`）。

プリセットは既定ではプロファイル保存場所の隣の `launch-presets/` に JSON ファイルとして置かれます。`STRATA_LAUNCH_PRESET_DIR` が設定されていればそのディレクトリを使用します（`terminal/strata_cli/launch/store.py:28-38`）。保存は一時ファイルへの書き込み後に置換する方式で、Unix 系ではファイル mode `0600` を設定します。Windows では現在ユーザーだけにアクセスを制限する処理も試みます（同 `store.py:40-60`）。設定には API key が含まれ得るため、プリセットファイルは秘密情報を含むユーザー設定ファイルです（`terminal/strata_cli/launch/settings.py:143-148`、`terminal/strata_cli/launch/store.py:3-7,83-85`）。

## 適用条件と副作用

- 設定を伴う通常の launch で有効です。引数なしで画面を開く経路では、`--save-preset` 自体が設定済み選択肢を作らず、オプションの指定だけで通常の対話セットアップを開始・保存するものではありません（`terminal/strata_cli/launch/cmd.py:849-871`）。
- `--plan` は設定ファイルを変更しない経路です（`terminal/strata_cli/launch/cmd.py:897-925`）。
- 実行条件により `launch-presets/` ディレクトリと JSON ファイルを作成または置換します。加えて通常起動ではモデル準備、チューニング、サーバー起動等も行われますが、それらは `--save-preset` 固有の副作用ではありません。
- 設定ファイル書き込み後に起動が失敗した場合にもプリセットが残ることがあります。起動前の失敗ではこの救済保存を行いません（`terminal/strata_cli/launch/cmd.py:949-961`）。

## 出力とエラー

- 起動成功時の通常出力は、設定保存の案内と `strata launch --preset "NAME"` で再起動する方法を示します（`terminal/strata_cli/launch/cmd.py:641-647,1005-1007`）。
- 非対話の通常経路で保存時に名前が空白だけの場合など `PresetError` / `ValueError` が起きると、人向け出力では stderr に `strata: ...` を出し、終了コード `2` を返します。`--output json` では同じエラーを JSON の `error` として stdout に出します（`terminal/strata_cli/launch/cmd.py:759-764,1009-1014`）。フラグ指定から TUI を開く経路では起動前保存の例外を TUI ラッパーが捕捉し、一般的な画面エラーを stderr に出して終了コード `1` を返します（`terminal/strata_cli/launch/app.py:704-710`、`terminal/strata_cli/launch/cmd.py:650-660,945-948`）。
- 救済保存時の保存例外は握りつぶされ、元の launch エラーが返されます（`terminal/strata_cli/launch/cmd.py:952-961`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:141-142` — `strata launch` parser の `--save-preset NAME` 定義。
- `terminal/strata_cli/launch/cmd.py:215-221,311-313` — 保存名の設定と、既存プリセットへの CLI 値重ね合わせ。
- `terminal/strata_cli/launch/cmd.py:897-925,945-966` — plan、TUI、通常成功、起動失敗後の保存分岐。
- `terminal/strata_cli/launch/store.py:28-60,76-104,153-165` — 保存場所、ファイル書き込み、置換、読み込み、利用時刻更新。
- `terminal/strata_cli/launch/settings.py:143-148,462-467` — 設定に含まれる API key と名前の slug 化。
- `terminal/strata_cli/launch/app.py:693-710` — TUI 経路で起動前に保存する処理。
