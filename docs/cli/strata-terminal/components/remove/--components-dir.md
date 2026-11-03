# `--components-dir`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネント格納先のパス（文字列） |

## 役割

導入済み engine を検索・削除する際のコンポーネントルートを指定します。対象の engine は位置引数 `engine` で版番号または folder 名を指定します。`--components-dir` は `strata components remove` に共通 parser から登録されています（`strata_cli/update_cmd.py:47-58,88-95`）。

## 使い方

```sh
strata components remove 0.1.54 --components-dir /srv/strata/components
```

この例は指定したルートで engine を探し、該当する engine を削除します。削除対象とルートを `strata components engines --components-dir /srv/strata/components` で確認してから指定してください。

## 値と既定値

- 値は必須です。parser は文字列を受け取り、`default=None` です。パスの存在・絶対パス・書き込み可能性を事前検査する型変換や validation はありません（`strata_cli/update_cmd.py:47-58,88-95`）。
- 省略時、または空文字列のときは `strata_control.engine_component.components_dir()` が使われます。環境変数 `STRATA_COMPONENTS_DIR` が設定されていればそのパス、そうでなければ Windows は `%LOCALAPPDATA%/Strata/components`（未設定時はホーム配下）、それ以外は `$XDG_DATA_HOME/strata/components`（未設定時は `~/.local/share/strata/components`）です（`strata_cli/update_cmd.py:244`; `strata_control/engine_component.py:176-186`）。
- 非空の明示値は環境変数より優先され、`Path(a.components_dir)` として使われます。相対パスを拒否・絶対化する処理はなく、相対値はプロセスの作業ディレクトリを基準に解決されます（`strata_cli/update_cmd.py:244`）。

## 実行時の動作

指定ルートは updater context の `components` に渡されます。Qwen 系 engine はそのルートの `engine/` を走査します（`strata_cli/update_cmd.py:244-255`; `strata_control/engine_component.py:933-946`）。engine の版番号・folder 名の照合は、そのルートから得た一覧に対して行われ、該当なしは exit code 2 になります（`strata_cli/update_cmd.py:378`; `strata_control/engine_library.py:180-211`）。

DeepSeek engine は保存済み設定や `STRATA_INSTALL_DIR` から見つかる配置も一覧対象です。加えて、指定コンポーネントルートの親にある `engine-dsv41/` も探索候補になります。そのため、このオプションだけで DeepSeek の探索範囲が指定ルート配下だけに限定されるわけではありません（`strata_control/updater.py:1444-1455`; `strata_control/engine_library.py:128-162`）。

削除時は指定ルートの updater lock を作成・取得し、対象 engine の folder を一時名へ rename してから削除します。Qwen engine の場合は updater state の pin/previous 情報を更新し、履歴を保存します（`strata_control/engine_library.py:294-334`; `strata_control/updater.py:136-157`）。

## 適用条件と副作用

- 使用中の engine、および実行中プログラムが使っている engine は削除できません。別 engine に切り替えてから、または利用中のプログラムを停止してから実行します。モデルと設定ファイル、反対側の engine family は削除処理の対象外です（`strata_control/engine_library.py:13-17,167-177,294-309`）。
- 実行にはコンポーネントルートと対象 folder への必要なファイル操作権限が要ります。lock 用 `.updates/` と `update.lock` を作成し、engine folder を rename・削除します。Qwen 側では `.updates/state.json` 相当の updater state も更新します（`strata_control/updater.py:136-145`; `strata_control/engine_library.py:301-334`）。
- rename 後に開いたままのファイルがあれば、その一時 folder は残ることがあります。処理後および次回削除時に `.deleting-*` folder の掃除を試みます（`strata_control/engine_library.py:311-318,341-348`）。
- `--family` を併用すると検索対象を `qwen` または `deepseek` に絞れます。family を絞らず同じ指定が複数 engine に一致した場合は、folder 名を使うようエラーになります（`strata_cli/update_cmd.py:88-91`; `strata_control/engine_library.py:198-211`）。

## 出力とエラー

- 成功時は人向け出力で削除した版と解放容量を表示します。`--output json` / `jsonl` または共通 `--json` 指定時は JSON 結果を出力します（`strata_cli/update_cmd.py:358-400`; `strata_cli/cli.py:508-515`）。
- 指定ルート内に一致する engine がない場合、または指定が曖昧な場合は `UpdateError` の code 2 です。使用中・実行中で削除できない場合も code 2 です（`strata_control/engine_library.py:198-211,301-309`）。
- 対象 folder を rename できない場合は「使用中の可能性」を示すエラーに変換され、code 6 で何も変更していない旨を返します。human 出力では `strata: ...` を stderr に、machine 出力では失敗 JSON を stdout に出します（`strata_control/engine_library.py:310-316`; `strata_cli/update_cmd.py:237-242,307-319`）。lock 取得中に別 updater がいる場合は code 7 です（`strata_control/updater.py:141-157`）。

## 根拠

- parser 定義と共通オプション付与: `strata_cli/update_cmd.py:47-58,88-95`。
- 明示値・既定ルートの選択と updater context: `strata_cli/update_cmd.py:233-255`。
- `STRATA_COMPONENTS_DIR`、XDG/Windows 既定先: `strata_control/engine_component.py:176-186`。
- engine の走査、一覧、指定解決: `strata_control/engine_component.py:933-946`; `strata_control/engine_library.py:91-123,128-162,180-211`。
- 削除制約、lock、rename・削除、state 更新と失敗経路: `strata_control/engine_library.py:167-177,294-348`; `strata_control/updater.py:136-157`。
- 索引上のコマンド階層と option scope: `docs/cli/README.md:309-325`（strata-envvars リポジトリ）。
