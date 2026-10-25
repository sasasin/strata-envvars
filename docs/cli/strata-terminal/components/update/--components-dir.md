# `--components-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネント格納先のパス（文字列） |

## 役割

この更新処理がエンジンや Control を探し、更新状態を読み書きするコンポーネントルートを指定します。`strata components update` と `strata update` は共通の parser・実装を使いますが、この文書のコマンドスコープは索引どおり `strata components update` です（`strata_cli/update_cmd.py:42-56,163-184`）。

## 使い方

```sh
strata components update --components-dir /srv/strata/components --check
```

`--check` はこのディレクトリを使って署名付き feed と更新候補を確認します。実際の更新を行う呼び出しでは `--check` を省きます。

## 値と既定値

- 値は必須です。parser は `default=None` で、型変換、パス存在確認、絶対パス必須などの追加 validation は定義していません（`strata_cli/update_cmd.py:30-40,50-56`）。
- 値が `None` または空文字列なら `strata_control.engine_component.components_dir()` が使われます。したがって空文字列も未指定と同じ扱いです（`strata_cli/update_cmd.py:174`; `strata_control/engine_component.py:176-186`）。
- 既定先は `STRATA_COMPONENTS_DIR` が設定されていればその値、そうでなければ Windows では `%LOCALAPPDATA%/Strata/components`（LOCALAPPDATA がなければホーム配下）、それ以外では `$XDG_DATA_HOME/strata/components`（XDG_DATA_HOME がなければ `~/.local/share/strata/components`）です（`strata_control/engine_component.py:176-186`）。
- 相対パスを拒否する処理は見当たりません。明示値は `Path(a.components_dir)` になり、絶対化はこの箇所では行いません（`strata_cli/update_cmd.py:174`）。相対パスの実際の基準はプロセスの作業ディレクトリです。

## 実行時の動作

明示値は `updater.Context.components` に格納されます。以降、feed/state の参照、コンポーネント検索、stage や更新処理がこのルートを使います（`strata_cli/update_cmd.py:174-184`; `strata_control/updater.py:624-639,1274-1285`）。このため、同じ `--components-dir` を指定しない更新とは別のインストール状態・更新履歴を扱い得ます。

ロックと状態ファイルは選択したルートの `.updates/` 配下です。実更新では `update.lock` を作成して排他し、`state.json` を読み書きします。`--check` もロックを取得し、候補結果の `last_check` を状態へ保存します（`strata_control/updater.py:129-150,165-200,624-639`）。実更新の staging も同じルート下に置かれます（`strata_control/updater.py:50,643-658`）。

## 適用条件と副作用

- オプション自体はパス文字列を受け取るだけで、パスの安全性や書き込み可能性を事前確認しません。ディレクトリ作成やファイル書き込みは後続処理で発生します（`strata_cli/update_cmd.py:30-40,174`; `strata_control/updater.py:134-138,193-200`）。
- `--check` でも `.updates/` の作成、ロックファイルの作成、`state.json` の `last_check` 更新が起こり得ます。従って読み取り専用の操作ではありません（`strata_control/updater.py:134-138,624-639`）。
- 更新先を切り替えると、その場所にある engine/Control と updater 状態が対象になります。`STRATA_COMPONENTS_DIR` は CLI の非空な明示値より優先されません。明示値が空の場合にだけ既定先解決が呼ばれます（`strata_cli/update_cmd.py:174`; `strata_control/engine_component.py:176-186`）。
- 相対パスの実際の解決先、空白のみの値の後続処理、Windows/Unix 以外のプラットフォームでの既定先は、この調査範囲では実行環境ごとの確認をしていません。空白のみは値としてそのまま `Path` に渡されます。

## 出力とエラー

このオプション単独の成功メッセージはありません。処理結果は通常出力または `--output json/jsonl` によって出力形式が変わります（`strata_cli/update_cmd.py:62-84,203-224`）。

選択ディレクトリの `.updates/` を作成できない、ロックを取得できないなどの失敗は updater の実行経路で発生します。別の更新が同じコンポーネントフォルダを使っている場合、ロック取得失敗は exit code 7 の `UpdateError` です（`strata_control/updater.py:133-150`）。`run()` は updater/feed/signature 系例外を捕捉し、human 出力では `strata: ...` を stderr に、machine 出力では JSON の error を stdout に出します（`strata_cli/update_cmd.py:163-172,225-234`）。ディレクトリ書き込みエラーの個別文言・終了コードは、該当箇所で捕捉される例外の詳細に依存するため、ここでは一律の値を断定しません。

## 根拠

- 索引上のコマンド階層とリンク: `docs/cli/README.md`（調査対象 strata-envvars リポジトリ）。
- parser、値の選択、Context への引き渡し: `strata_cli/update_cmd.py:30-59,163-184`。
- update と `components update` の dispatcher: `strata_cli/cli.py:139-140,2135-2137`。
- 既定コンポーネントルート: `strata_control/engine_component.py:176-186`。
- 選択ルート配下のロック・状態・check 保存・更新: `strata_control/updater.py:129-150,165-200,624-639,1274-1295`。
