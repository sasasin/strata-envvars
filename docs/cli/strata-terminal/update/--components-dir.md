# `strata update --components-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネント格納先のパス |

## 役割

更新処理が engine、Control、取得した Desktop installer と updater の状態を扱うルートディレクトリを指定します。`strata update` の共通 parser で定義され、同じ定義・実装は `strata components update` と `strata components rollback` にも使われます。この文書は索引のスコープどおり `strata update` を説明します（`strata_cli/update_cmd.py:30-59`; dispatcher は `strata_cli/cli.py:139-140,2135-2137`）。

## 使い方

```sh
strata update --components-dir /srv/strata/components --check
```

`--check` を付けると、指定した components root にある engine と updater state を基準に更新候補を確認します。実際に更新するときは `--check` を省略します。

## 値と既定値

- 値は必須で、parser は文字列として受け取ります。`default=None` で、`type` 変換やパス存在・絶対パスの検証は登録されていません（`strata_cli/update_cmd.py:30-40`）。
- 値を省略すると `strata_control.engine_component.components_dir()` が選ばれます。非空の `STRATA_COMPONENTS_DIR` があればそのパス、なければ Windows は `%LOCALAPPDATA%/Strata/components`（環境変数がなければホーム配下）、それ以外は `$XDG_DATA_HOME/strata/components`（環境変数がなければ `~/.local/share/strata/components`）です（`strata_cli/update_cmd.py:174`; `strata_control/engine_component.py:176-186`）。環境変数の説明は [`STRATA_COMPONENTS_DIR`](../../../STRATA_COMPONENTS_DIR.md) を参照してください。
- 明示値が空文字列なら `a.components_dir` が偽となり、既定先の解決へ進みます。空白だけの値は空文字列ではないため、そのまま `Path` に渡されます（`strata_cli/update_cmd.py:174`）。
- 相対パスを拒否したり、この箇所で絶対パスへ変換したりする処理はありません。相対パスはプロセスの作業ディレクトリを基準とする `Path` として使われます（`strata_cli/update_cmd.py:174`）。

## 実行時の動作

選ばれたパスは `updater.Context.components` に設定され、feed の既定値解決時に保存済み feed を読むほか、更新状態、engine/Control の配置、staging に使われます（`strata_cli/update_cmd.py:87-95,174-184`; `strata_control/updater.py:129-130,165-171,643-659,1145-1157`）。したがって異なる値を指定すると、既定先とは異なるコンポーネントと更新履歴を対象にし得ます。

選択した root の `.updates/` に `update.lock` と `state.json` が置かれます。`--check` もロックを取得し、feed を確認した後に `last_check` を state に保存します。通常の更新では root 配下で staging を作成し、選択された engine/Control を更新します。`--app` を併用して installer を取得する場合、その検証済みファイルも `.updates/app/` に保存されます（`strata_control/updater.py:129-152,165-205,624-640,643-653,1145-1178,1226-1257,1274-1295`）。

## 適用条件と副作用

- 指定先の事前検証はありません。存在しない場合でも、後続のロックや状態保存で親ディレクトリを作成します。作成・書き込みできない場合は処理が失敗します（`strata_cli/update_cmd.py:174`; `strata_control/updater.py:133-138,193-205`）。
- `--check` は feed 取得以外の更新 package は取得しませんが、`.updates/` とロックファイルを作成し、`state.json` に最終確認情報を書きます（`strata_control/updater.py:624-640`）。
- 通常の update は同じルートの state を読み書きし、engine/Control や、`--app` 指定時の installer を取得・検証・配置します。更新先の誤指定は別のインストール状態を参照・変更する可能性があります（`strata_control/updater.py:1274-1295`）。
- 同じ root に対する別の updater 実行はファイルロックで排他されます。engine serving 中の扱いは `--wait` 等に依存し、このオプション自体は serving 状態を変えません（`strata_control/updater.py:133-153`; `strata_cli/update_cmd.py:237-252`）。

## 出力とエラー

このオプション単独の成功出力はありません。通常出力は更新結果を表示し、`--output json` または `jsonl` では machine 出力になります（`strata_cli/update_cmd.py:62-84,203-224`）。

選択した root のロック競合は `UpdateError`、終了コード 7 です。`UpdateError`、feed/signature エラーなどは human 出力なら `strata: ...` を stderr に、machine 出力なら JSON error を stdout に出します。ディレクトリ作成・書き込み等の `OSError` が出る具体的な箇所と表示は状況によるため、このオプションに固有の単一メッセージや終了コードはありません（`strata_control/updater.py:133-153`; `strata_cli/update_cmd.py:163-172,225-234`）。

## 根拠

- `strata_cli/update_cmd.py:30-59,163-184` — parser、既定先の選択、Context への設定。
- `strata_cli/update_cmd.py:87-95` — `--feed` 省略時に選択 root の保存済み feed を参照。
- `strata_control/engine_component.py:176-186` — `STRATA_COMPONENTS_DIR` と per-user root の解決。
- `strata_control/updater.py:129-205,624-640` — root 配下のロック・state、`--check` の保存処理。
- `strata_control/updater.py:643-659,1145-1178,1226-1257,1274-1295` — staging、components の更新、installer 配置と更新処理。
- `strata_cli/cli.py:139-140,2135-2137` — parser 登録と `strata update` の dispatcher。
- `docs/cli/README.md:244-262` — `strata update` の階層とこの文書への索引リンク。
