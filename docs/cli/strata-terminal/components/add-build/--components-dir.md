# `--components-dir`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components add-build` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | directory path（文字列。型・存在条件の parser validation はない） |

## 役割

ローカル build を engine package として登録する component directory を指定する。build 元 folder は位置引数で別に指定し、この option の directory の `engine/` 以下へ build の実行ファイル・対象ライブラリ・補助プログラム・`BUILD.json` をコピーする。登録後は、その package を今後使う engine に切り替える（`terminal/strata_cli/update_cmd.py:97-99, 314, 339-340, 425-441`、`terminal/strata_control/local_engine.py:127-130, 153-178`）。

## 使い方

```sh
# build 元を指定した component directory に登録する
strata components add-build ./build --components-dir "$HOME/.local/share/strata-dev/components"
```

`--components-dir` は `strata components add-build` に共通 option 群の一つとして登録されている。`--output json` または `--output jsonl` を同時指定すると、成功・失敗を機械可読形式で出力する（`terminal/strata_cli/update_cmd.py:47-56, 95-99, 303-315`）。

## 値と既定値

- 値は必須の directory path 文字列で、parser では `default=None`。`choices`、型変換、パス存在確認は parser 定義にない（`terminal/strata_cli/update_cmd.py:47-50`）。
- 指定値が空でない場合は `Path(a.components_dir)` が component directory として使われ、相対パスはプロセスの作業 directory 基準で解決される。空文字列は条件式で偽となるため、省略時と同じ既定 directory 解決に進む（`terminal/strata_cli/update_cmd.py:314`）。
- 省略時は `default_components_dir()` が選ぶ。まず `STRATA_COMPONENTS_DIR` があればその値を使う。なければユーザー用 directory（Windows は `LOCALAPPDATA` または home の `AppData/Local/Strata/components`、それ以外は `XDG_DATA_HOME` または `~/.local/share/strata/components`）を使う。ただし、Strata source checkout の `engine-feed` に engine package があり、ユーザー用 directory に package が見つからない場合は checkout 側の `engine-feed` を選ぶ（`terminal/strata_cli/update_cmd.py:252-262, 265-280`、`terminal/strata_control/engine_component.py:179-193`）。
- 非空の `--components-dir` 指定は環境変数より優先する（`terminal/strata_cli/update_cmd.py:314`）。

## 実行時の動作

1. 決定した component directory を update context に渡す（`terminal/strata_cli/update_cmd.py:314-321`）。
2. `add-build` はその directory を登録先として `local_engine.add_build()` に渡す。登録先の `engine/` を必要に応じて作成し、build 元から選別したファイルを一時 directory にコピーし、manifest を作って全ファイルを検証した後、完成した package directory に移動する。build 元は移動・削除しない（`terminal/strata_cli/update_cmd.py:425-434`、`terminal/strata_control/local_engine.py:109-116, 153-176`）。
3. 続けて同じ context directory 内で登録 package を選択し、以後の起動で使う engine に切り替える。成功時は human 出力に登録先の folder 名を表示し、JSON/JSONL 出力では登録情報と切替情報を出力する（`terminal/strata_cli/update_cmd.py:434-441`、`terminal/strata_control/engine_library.py:211-228`）。

この option は登録・選択先を指定し、build 元の位置は変更しない。build 元が不正、互換 backend でない、または同名 package がすでに登録済みなら拒否される。directory の書き込み権限がない場合などの OS file error は CLI の OSError 経路で処理される（`terminal/strata_control/local_engine.py:131-157`、`terminal/strata_cli/cli.py:2258-2265`）。

## 適用条件と副作用

- 指定先がまだない場合、`<components-dir>/engine/` を作成する。既存の同名 local package は上書きせず、削除してから再登録するようエラーにする（`terminal/strata_control/local_engine.py:153-159`）。
- `add_build` による package 登録の後で engine 切替を行う。切替処理は実行中モデルがある場合に拒否する（終了コード 7）。その場合、先行して登録された package はこの呼出し内では取り消されない（`terminal/strata_cli/update_cmd.py:431-434`、`terminal/strata_control/engine_library.py:211-228`）。
- これはローカル unsigned build を明示的に使うための登録先である。Strata はその build を自動選択しない。既定のリリース engine に戻す案内は `strata components use newest`（`terminal/strata_cli/update_cmd.py:95-96, 438-441`）。

## 出力とエラー

- local build 検査の `AddBuildError` は `UpdateError` に変換される。代表例として directory 不在・engine 実行ファイル不在・backend 情報不足・同名 package は終了コード 2、実行非対応 backend は終了コード 5 で拒否される（`terminal/strata_cli/update_cmd.py:431-433`、`terminal/strata_control/local_engine.py:41-46, 131-157`）。
- `--output human`（既定）ではエラーを stderr に `strata: ...` と出力し、JSON/JSONL 指定では `schema_version`、`ok: false`、エラー code/message を含む JSON を stdout に出力する（`terminal/strata_cli/update_cmd.py:303-312, 374-384`）。
- component directory への作成・書き込みなどで OSError が起きた場合、CLI は file error を出力して終了コード 6 を返す（`terminal/strata_cli/cli.py:2258-2265`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56, 95-99` — 共通 parser 定義、値と default、`add-build` への option 適用。
- `terminal/strata_cli/update_cmd.py:252-280, 303-321, 339-340` — 既定 directory の選択、context への渡し、実行分岐。
- `terminal/strata_cli/update_cmd.py:425-441` — 登録から切替、human/JSON 出力までの処理。
- `terminal/strata_control/engine_component.py:179-193` — 環境変数と platform 別 per-user directory、`engine/` 配下の構造。
- `terminal/strata_control/local_engine.py:127-178` — build 元の検査、package directory 作成・ファイルコピー・manifest 検証・確定。
- `terminal/strata_control/engine_library.py:211-228` — 登録後の engine 選択と実行中モデルによる拒否。
- `terminal/strata_cli/cli.py:2258-2265` — OSError のエラー出力・終了コード。
