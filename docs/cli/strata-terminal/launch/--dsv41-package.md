# `--dsv41-package`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--dsv41-package FILE` |
| 別名 | なし |
| 値 | DeepSeek-V4.1 用 engine package のファイルパス |

## 役割

DeepSeek-V4.1 の専用 engine package を手元にダウンロード済みの場合、そのファイルを Strata に検査・導入させます。通常の feed からの取得の代わりに使う指定です。モデルファイルの指定ではありません（`strata_cli/launch/cmd.py:87-88`、`setup.py:7764-7779`）。

## 使い方

```sh
strata launch --model MODEL --family deepseek41 --dsv41-package /absolute/path/strata-dsv41-package.tar.gz --no-tui
```

`MODEL` はカタログにある DeepSeek-V4.1 のモデル名に置き換えてください。`--dsv41-package` だけでは起動対象の選択になりません。対話端末では通常の案内画面に進みますが、このフラグ単独では選択内容として扱われません。非対話環境では `--model` または DeepSeek の preset など、起動対象も指定してください（`strata_cli/launch/cmd.py:197-213,680-710`）。

## 値と既定値

- `FILE` は必須の1値です。launch parser は拡張子、存在、内容を事前検証せず、`Path(...).expanduser()` で `~` だけ展開して設定に保存します。既定値はありません（`strata_cli/launch/cmd.py:87-88,197-205`）。
- setup の package installer は `.tar.gz`、`.tar.xz`、`.zip`、または展開済みディレクトリを処理できます。ただし launch の help は `.tar.gz` / `.zip` と説明しており、`.tar.xz` と展開済みディレクトリは setup 実装で確認できる追加対応です（`strata_control/dsv41_engine.py:38-39,51-75`）。
- `strata launch` は引数を setup に渡す際の作業ディレクトリを Strata の source checkout にします。相対パスを使うと呼び出し元ディレクトリではなく、その setup subprocess の作業ディレクトリを基準に解決されます。確実に指定するには絶対パスを使ってください（`strata_cli/launch/runner.py:948-959`）。

## 実行時の動作

launch は値を `LaunchSettings.dsv41_package` に保持し、選択された family が `deepseek41` の場合だけ `setup.py --dsv41-package FILE` に転送します。他の family では転送されず、package は使われません（`strata_cli/launch/settings.py:77-86`、`strata_cli/launch/runner.py:727-755`）。

DeepSeek の setup は専用 engine がまだ見つからない場合にこの package を導入します。受け入れ前に engine の manifest、実行ファイル名、ホスト platform、信頼済み鍵による署名、および manifest に記録された全ファイルの hash を検査します。成功すると engine を Strata の install folder 内の `engine-dsv41/<version>-<platform>-<backend>[-<variant>]/` に配置し、Unix 系では実行権限を設定します（`setup.py:7741-7743,7770-7779,8037-8053`、`strata_control/dsv41_engine.py:51-111`）。

指定 package がすでに導入済みの engine を強制置換する機能ではありません。launch は、既存モデル設定・必要なファイル・engine が揃っていれば setup を省略します。また setup 自体も engine が見つかった場合は指定 package をインストールしません。指定 package があると、通常の自動 upgrade も抑止されます（`strata_cli/launch/runner.py:925-938,1896-1903`、`setup.py:8041-8050`）。`--plan` は計画を表示して終了するため、package の導入には進みません（`strata_cli/launch/cmd.py:733-760`）。

## 適用条件と副作用

- launch からの転送条件は `family == "deepseek41"` です。対象が DeepSeek でない場合は値を保持しても利用されません（`strata_cli/launch/runner.py:752-753`）。
- macOS では `setup_args()` が setup に渡す引数を許可リストで絞り、このオプションは許可リストに含まれません。そのため launch parser は受理しますが、この経路では package が setup に渡りません（`strata_cli/launch/runner.py:752-775`）。
- install 時は install folder 内の `engine-dsv41.manual` 一時作業領域を作り、終了時に削除します。検証に通った package を配置する際、同じ version 名の既存 directory は削除して置き換え、さらに `engine-dsv41` 内の他の directory も削除します。別バージョンの手動保持や同時併置はされません（`setup.py:7741-7743`、`strata_control/dsv41_engine.py:62-64,100-116`）。
- package の取得元ファイルは installer が削除・移動する処理を確認できません。検査・展開・copy の対象はありますが、元ファイルは残ります（`strata_control/dsv41_engine.py:58-75,100-116`）。
- 不正な package の導入が失敗すると setup は `[X]` のエラーを出して終了し、launch は setup の出力をもとに model install error を返します（`setup.py:7775-7779,825-830`、`strata_cli/launch/runner.py:997-1012`）。launch の通常エラーは stderr、`--output json` 指定時は JSON 出力になります（`strata_cli/launch/cmd.py:630-641`）。

## 根拠

- `strata_cli/launch/cmd.py:75-89,197-205` — launch parser と path の取り込み。
- `strata_cli/launch/cmd.py:630-641,680-700,733-760` — 起動対象の判定、失敗出力、計画表示。
- `strata_cli/launch/runner.py:727-775,925-959,997-1012,1896-1903` — setup への引数転送、macOS の引数選別、setup 起動・失敗処理、upgrade 条件。
- `strata_cli/launch/settings.py:77-86` — LaunchSettings の値。
- `setup.py:7764-7779,8037-8058,8488-8491` — setup 側 parser・取得経路・対象 family の engine setup。
- `strata_control/dsv41_engine.py:38-39,51-116` — package 形式、検証、配置、削除範囲、失敗時の出力。

調査は上記 commit の checkout 内ソースに限定しました。同一 revision の CLI help と Release 配布物は実行・取得しておらず、配布実績や配布ファイル名は確認していません。
