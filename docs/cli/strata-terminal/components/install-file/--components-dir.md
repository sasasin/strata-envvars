# `--components-dir`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | ディレクトリパスを表す文字列 |

## 役割

エンジン package の導入先となる Strata components root を指定します。インストール済み engine だけでなく、更新状態や staging など updater が使うデータもこの root に置かれます。省略した場合は通常のユーザー別 root（または `STRATA_COMPONENTS_DIR`）を使います。オフラインで取得済みの package を別の components root に導入したい場合に使います。

## 使い方

```sh
# カレントディレクトリ配下の Strata データ領域へ、取得済み package を導入する
strata components install-file ./engine-package.tar.gz --components-dir ./strata-components
```

`file` は必須位置引数です。`--components-dir` は `install-file` の共通オプションで、位置引数の前後どちらにも置けます（parser 定義: `terminal/strata_cli/update_cmd.py:92-94`）。

## 値と既定値

値は parser では単なる文字列として受け取り、専用の形式・存在確認・書き込み可否検証は行いません（`terminal/strata_cli/update_cmd.py:47-56`）。`run()` は値が空でなければ `Path(a.components_dir)` を root にし、空文字または未指定なら既定 root を選びます（`terminal/strata_cli/update_cmd.py:314`）。相対パスは絶対化されず `Path` として利用されるため、呼び出し時の作業ディレクトリからの相対パスです。

未指定時、`STRATA_COMPONENTS_DIR` があればその値を使用します。なければ Windows は `%LOCALAPPDATA%/Strata/components`（`LOCALAPPDATA` がなければユーザー home 配下）、その他の OS は `$XDG_DATA_HOME/strata/components`（未設定なら `~/.local/share/strata/components`）です。ソース checkout に同梱 engine store があり、ユーザー別 root に engine が見つからない場合には checkout 側 store が選ばれる分岐もあります（`terminal/strata_cli/update_cmd.py:252-280`; `terminal/strata_control/engine_component.py:179-190`）。

明示した `--components-dir` は `run()` が直接 root として使うため、環境変数や通常の既定値より優先します（`terminal/strata_cli/update_cmd.py:314`）。

## 実行時の動作

`install-file` の処理は `ctx.components` に選択した root を設定し、その root に対する updater lock を取得します。空き容量を確認した後、package を `<root>/.s/<識別子>/engine/` に展開し、manifest の署名と全ファイルの hash を検証し、この PC に適合する engine か確認します。その後 test-start に成功した場合に限って root 配下の `engine/` へ移し、状態を記録して次回起動から使う engine を切り替えます。古い engine はこの処理では削除しません（`terminal/strata_cli/update_cmd.py:314,341-350`; `terminal/strata_control/updater.py:1638-1695,1538-1627`）。

このコマンド経路は feed を読まず、package archive をネットワークから取得しません。入力ファイルは呼び出し元が指定した場所に残します。検証用 staging と `.updates/` 配下の lock・state などは指定 root に作成されます（`terminal/strata_control/updater.py:1638-1649,1695`; `terminal/strata_control/updater.py:196-214,227-232`）。

`--backend` を併用すると、その backend を基にした hardware 情報で package の適合性を判定します。`--force` は、既に導入済みの engine より archive の version が古い場合の「何もしない」判定を通過させます（`terminal/strata_cli/update_cmd.py:314-320`; `terminal/strata_control/updater.py:1675-1695`）。engine が稼働中の場合は `--wait SECONDS` の値が待機動作に関係します。対話端末では未指定時に待つか確認し、機械出力または非対話時には待機せず busy として拒否されます（`terminal/strata_cli/update_cmd.py:500-515`; `terminal/strata_cli/update_cmd.py:341-345`）。

## 適用条件と副作用

- root が存在しなければ、空き容量確認時に親を含めて作成します。書き込み権限がない、または容量不足の場合は導入できません（`terminal/strata_control/updater.py:550-569`）。
- 同じ root で別 updater が実行中なら lock 取得に失敗し、終了コード `7` の更新拒否になります（`terminal/strata_control/updater.py:196-214`）。
- 稼働中 engine があり処理を継続できない場合も busy として終了コード `7` になります。既存の Strata launch が GPU を使用中の場合、エラーは先に model を停止するよう案内します（`terminal/strata_cli/update_cmd.py:500-515`; `terminal/strata_control/updater.py:72-83`）。
- archive の拡張子が `.tar.gz`、`.tgz`、`.tar.xz`、`.zip` のいずれでもない場合、ファイルでない場合、読み取り・展開に失敗する場合、署名やファイル hash が不正な場合、または PC に適合しない場合は拒否されます。拒否・test-start 失敗時には staging は削除され、通常、稼働中の engine は切り替わりません（`terminal/strata_control/updater.py:1630-1635,1642-1673,1695-1698,1538-1627`）。
- 実行開始時、クラッシュ等で残った `<root>/.s/` staging と旧形式の `<root>/.updates/staging/` は掃除対象です。導入成功時は engine の切り替え・状態更新が行われ、以前の engine は保持されます（`terminal/strata_control/updater.py:792-802,1600-1627`）。

## 出力とエラー

成功時、通常出力では導入結果の note または engine 状態を表示し、`--output json` / `jsonl` では成功結果を JSON として標準出力に出します（`terminal/strata_cli/update_cmd.py:345-350`）。確認した `UpdateError` は、通常出力では `strata: ...` を標準エラーに出し、機械出力では error object を標準出力へ出して、そのエラーの終了コードを返します（`terminal/strata_cli/update_cmd.py:303-312,374-380`）。

実装で明示されている例では、ファイル不在・形式不正・package の安全性または適合性拒否は終了コード `5`、空き容量不足や install 後の engine 解決失敗は `6`、稼働中 engine または同一 root の lock 競合は `7` です（`terminal/strata_control/updater.py:1635,1643-1645,1671-1682,1690-1691`; `terminal/strata_control/updater.py:565-566,1595-1599,208-214`; `terminal/strata_cli/update_cmd.py:307-312,374-380`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser の定義。値は文字列で、default は `None`。
- `terminal/strata_cli/update_cmd.py:92-94` — `install-file` に位置引数 `file` と共通 options を登録。
- `terminal/strata_cli/update_cmd.py:303-320,341-350` — 選択 root から context を作り、install-file 処理と出力へ進む。
- `terminal/strata_cli/update_cmd.py:252-280`; `terminal/strata_control/engine_component.py:179-190` — 未指定時の root 選択とユーザー別既定パス。
- `terminal/strata_control/updater.py:1630-1698,1538-1627` — archive 形式、検証、staging、install・switch・cleanup。
- `terminal/strata_control/updater.py:196-232,550-569` — root 単位の lock、状態ファイル、root 作成と容量判定。
- 配置と scope は索引 `docs/cli/README.md:177-188` の `strata components install-file` 節と一致します。
