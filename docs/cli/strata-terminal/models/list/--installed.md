# `--installed`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--installed` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。既定値は `false` |

## 役割

parser の説明は「ローカルの setup run config に discovery を限定する」ですが、この revision では通常の `strata models list` も同じローカル一覧処理を実行します。`--installed` は受理されるものの、処理分岐で値が参照されず、指定の有無による実行結果の違いはありません。コマンド概要ページの予定リンクは [索引](../../../README.md) にあります。

## 使い方

```sh
strata models list --installed
```

この呼び出しは `strata models list` と同じローカル一覧処理になります。JSON 出力が必要なら、別の出力指定として `--output json`（または共通 alias の `--json`）を加えます。

## 値と既定値

- 値は指定しません。`argparse` の `action="store_true"` により、未指定時は `false`、指定時は `true` です。
- `--installed` と `--served` は同じ相互排他グループにあります。両方を同時に指定すると parser が拒否します。
- parser の後に `models list` を処理する `_models` は `a.served` を確認しますが、`a.installed` は参照しません。`--installed` の値を変換・検証する追加処理もありません。

## 実行時の動作

`--installed` を指定しない場合も、`--served` がなければ `models.list_installed(a.install_dir)` が呼び出されます。したがって `--installed` はローカル一覧への切り替えに使われず、その経路では実効上の no-op です。ローカル一覧処理は run config のあるインストール先を探索し、同一 ID が複数箇所にあれば先に見つかったものを採用します。設定ごとに component 状態を調べ、実行互換性は `unverified` として報告します。

`--install-dir` がある場合は明示したディレクトリだけが対象です。ない場合、`STRATA_INSTALL_DIR` があればそこだけを対象とし、なければ Terminal 自身のフォルダ、ユーザー設定に記録された過去のインストール先、Desktop app のインストール先などを順に探索します。発見候補と優先順は `strata_control/discovery.py` に実装されています。

ローカル経路は設定ファイルと component 状態を読む処理です。`--installed` による設定変更、ファイル生成・削除、ネットワーク接続はありません。なお、コマンド共通の起動処理として Windows では `main` が `private_files.adopt_user_defaults()` を呼びます。これは昇格実行時のプロセストークンの既定 owner/DACL を調整する処理で、`--installed` 固有ではありません。

## 適用条件と副作用

- `--served` と同時には使えません。`--served` は現在 serve 中のモデルを照会する別スコープです。
- `--url`、`--connection`、`--credential-env`、`--timeout` は `--served` がないローカル経路ではエラーになります。`--installed` 自体はこれらの接続オプションを有効化しません。
- ローカル一覧はディレクトリあたり最大128件の config を扱います。config は通常ファイルで1 MiB以下である必要があり、読み取り可能なJSONで engine・tokenizer・文字列引数を含むことも検査されます。
- このオプション自体が行う追加の副作用はソース上で確認できません。実装上、一覧処理は設定・コンポーネント情報を読み取ります。

## 出力とエラー

- 既定の human 出力はモデル ID、component status、モデル名（またはエラー）を行ごとに表示します。一覧が空なら、探索先と `--install-dir` の案内を表示します。
- `--output json` または `--json` では、`scope: local_run_configs`、探索先、モデル一覧、件数、discovery limit などを含む結果を JSON で出力します。`--quiet` は one-shot 共通オプションですが、JSON 出力との併用時に JSON を抑止しません。
- `--installed --served` のような構文エラーは `argparse` の usage/error 経路です。ローカル一覧で `--install-dir` が既存の絶対ディレクトリでない場合や config 数が上限を超える場合は `ProfileError`（終了コード5）となり、通常は stderr に `strata: ...` を出力します。JSON モードでは `{schema_version, ok: false, error: {code, message}}` 形式です。設定が読み取り中に変化した場合は終了コード6のエラー経路があります。

## 根拠

- parser、相互排他関係、他の `models list` オプション: `strata_cli/cli.py:141-152`。one-shot 共通の `--json` / `--quiet` 追加: `strata_cli/cli.py:508-515`。
- 実行経路と `--installed` が分岐条件に使われないこと: `strata_cli/cli.py:564-596`。この範囲では `a.served` を分岐に使い、通常経路で `models.list_installed(a.install_dir)` を呼びます。
- ローカル一覧の探索、重複 ID の扱い、検査結果と返却値: `strata_control/models.py:185-210`。
- config の列挙上限、読み取り制約と検証、検査中の変更検出: `strata_control/models.py:96-129`, `strata_control/models.py:173-182`。
- 明示 install dir と `STRATA_INSTALL_DIR`、自動探索の候補: `strata_control/models.py:62-82`, `strata_control/discovery.py:160-203`。
- `--installed` は parser 定義以外に Python の実行コード上の参照がなく、指定有無で効果を変える処理は確認できません（`strata_cli/cli.py:145`, `strata_cli/cli.py:564-596`）。
- 出力と例外の整形: `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2166-2188`。Windows の起動時 token defaults 処理: `strata_cli/cli.py:2217-2222`, `strata_control/private_files.py:349-385`。
