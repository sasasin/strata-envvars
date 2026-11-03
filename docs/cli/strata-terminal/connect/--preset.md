# `--preset`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--preset` |
| 別名 | なし |
| 値 | 保存済み launch preset の名前（`NAME`） |

## 役割

`strata connect <app> --preset NAME` は、名前付き launch preset に対応する起動中の Strata launch、または保存 preset から接続情報を解決し、アプリ向け設定を表示・生成します。これは `strata launch --preset` のようにモデルを起動する指定ではありません。parser は `connect` 専用で、値は必須です（`strata_cli/launch/cmd.py:163-179`）。

## 使い方

```sh
strata connect opencode --preset Office
```

接続先や認証情報などを個別に指定する場合も、同じ `connect` オプションを併用できます。

```sh
strata connect opencode --preset Office --url http://127.0.0.1:8080
```

`connect` はプリセットを読んでアプリ向け設定を表示するだけです。`--write` を付けた場合はアプリ設定ファイルを書き込み、既存ファイルはバックアップされます（`strata_cli/launch/cmd.py:166-179, 1146-1163`）。

## 値と既定値

- `NAME` は通常の文字列で、parser では候補一覧や空文字を検証しません（`strata_cli/launch/cmd.py:174`）。名前の検索には小文字化、英数字・`-`・`_` 以外の連続部分の `-` 化、長さ 48 文字への切り詰めを行った slug を使います（`strata_cli/launch/settings.py:371-376`）。
- `--preset` を省略した場合は名前付き preset を選びません。`connect` の既定 URL は、検出した起動中 launch、または `http://127.0.0.1:8080` です（`strata_cli/launch/cmd.py:1080-1084`）。
- 指定名の保存ファイルがない場合、`launch_info` は preset を「見つからない」として扱います。エラーにせず、他の明示値または既定値で接続情報を作ります（`strata_cli/launch/cmd.py:752-758`、`strata_cli/launch/store.py:88-95`）。ただし同名で読めない・壊れたファイルは `PresetError` になります（`strata_cli/launch/store.py:96-103`）。
- 空文字を明示した場合は、`launch_info` の `if name` 判定で名前なしと同じ経路になります（`strata_cli/launch/cmd.py:741-744, 752`）。

## 実行時の動作

名前を指定すると、Strata は稼働中 launch の一覧から slug が一致するものを探し、同名の保存 preset も読み込みます（`strata_cli/launch/cmd.py:739-754`）。起動中の一致があれば、その launch の URL・port と設定ファイル由来の API key、model、context が使われます。API key が設定ファイルで文字列 `none` の場合は使わず、保存 preset の key にフォールバックします（`strata_cli/launch/cmd.py:745-758`）。

保存 preset はあるが対応する launch が起動していない場合、preset の port から `http://127.0.0.1:<port>` を作り、preset の API key を候補にします。一方、`launch_info` が返す model は `strata`、context は未設定です。このため最終的には model `strata`、context `32768` が使われます。保存 preset 内の model/context が接続設定に採用されるわけではありません（`strata_cli/launch/cmd.py:752-758, 1080-1085`）。

同じコマンドで個別指定した値の優先順位は次の通りです。

1. URL: `--url` → 解決した launch/preset → `http://127.0.0.1:8080`
2. API key: `--key` → `--key-env NAME` で指定された環境変数の値 → 解決した launch/preset → 空文字
3. model: `--model` → 解決した起動中 launch → `strata`
4. context: `--context` → 起動中 launch の設定 → `32768`

この解決後の値で app 用 target を作り、設定内容を描画します（`strata_cli/launch/cmd.py:1080-1086`）。`--context` の値は整数 token 数または `32k` などの形式で、最低 1024 tokens に変換・検証されます（`strata_cli/launch/cmd.py:48-52`、`strata_cli/launch/settings.py:78-88`）。

## 適用条件と副作用

- 起動中 launch との照合は指定名の slug を使います。保存 preset の場所は既定では profiles ディレクトリの隣の `launch-presets/` で、`STRATA_LAUNCH_PRESET_DIR` があればそちらを使います（`strata_cli/launch/cmd.py:741-744`、`strata_cli/launch/store.py:27-36`）。
- preset の読み込み自体は接続設定の生成であり、launch を開始しません。ファイルへの書き込みは `--write` を指定したときだけ行われます（`strata_cli/launch/cmd.py:1080-1086, 1138-1152`）。
- API key は通常の出力ではマスクされます。human 出力では `--show-key` を指定すると実値を表示します。JSON 出力では key を含む文字列をマスクします（`strata_cli/launch/cmd.py:1085-1092, 1119-1126`）。
- parser に `--preset` 固有の名前 validation はありません。slug 化後に別名へ正規化される名前や、該当 preset のない名前は、上記の検索・fallback 経路になります（`strata_cli/launch/settings.py:371-376`、`strata_cli/launch/cmd.py:741-758`）。

## 出力とエラー

- 不正な app 名は stderr に候補付きメッセージを出して終了コード `2` になります（`strata_cli/launch/cmd.py:1073-1079`）。
- preset ファイルが破損・読取不能なら `store.load` が `ValueError` 系のエラーを送出し、CLI 共通処理が human 出力では stderr に `strata: ...`、`--output json` では JSON error を出して終了コード `2`（例外に個別コードがなければ既定値）を返します（`strata_cli/launch/store.py:96-103`、`strata_cli/cli.py:527-532, 2167-2174`）。
- `--write` で端末対話できないのに `--yes` がない場合は stderr に案内を出し終了コード `2` です。対話で拒否した場合は書き込みせず終了コード `0` です（`strata_cli/launch/cmd.py:1138-1152`）。

## 根拠

- parser と option scope: `strata_cli/launch/cmd.py:163-180`
- preset と起動中 launch の情報解決: `strata_cli/launch/cmd.py:736-758`
- connect での値の優先順位と target 作成: `strata_cli/launch/cmd.py:1073-1086`
- preset の配置・読み込み・失敗経路: `strata_cli/launch/store.py:27-36, 88-103`
- 名前の slug 化: `strata_cli/launch/settings.py:371-376`
- context の書式と下限: `strata_cli/launch/settings.py:78-88`
- CLI 共通 error 出力と終了コード: `strata_cli/cli.py:527-532, 2167-2174`
