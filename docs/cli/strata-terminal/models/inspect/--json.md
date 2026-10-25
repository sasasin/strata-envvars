# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models inspect` |
| オプション | `--json` |
| 別名 | `--output json` |
| 値 | 値を取らない真偽フラグ。JSON 出力を選ぶ |

## 役割

モデル設定と必要コンポーネントの検査結果を機械可読な JSON で出力します。`--output json` の alias です。JSON 指定は結果の形式を変えます。設定ファイルやコンポーネントを修復・変更する指定ではありません。

## 使い方

```sh
strata models inspect my-model --json
```

`my-model` は設定ファイル名 `strata-my-model.json` の ID 部分です。別のインストール先を調べる場合は `--install-dir /absolute/path/to/install` を併用できます。

## 値と既定値

`--json` は値なしの `store_true` フラグで、既定値は false です。指定すると共通 CLI 処理が出力形式を `json` に設定します。`--output` は `human` または `json` を受け付け、既定値は `human` です。したがって `--json` を省略した場合は人間向け表示、指定した場合または `--output json` を指定した場合は JSON になります。複数回の `--json` 指定も単に true のままです。

`--json` と `--output json` の組み合わせは同じ出力形式を選びます。`models inspect` の `--output` は `jsonl` を選べません。

## 実行時の動作

- `--json` は全 one-shot parser に共通の引数として `models_inspect` に追加されます。`--output` の選択肢と既定値は `models inspect` parser 側で定義されています。
- JSON 指定時は検査成功結果を `schema_version: 1`, `ok: true`, `scope`, `install_dir`, `model`, `components` を含む JSON object として stdout に出します。モデル要約には設定ファイルの SHA-256、コンポーネント状態、問題コード、実行互換性が含まれます。JSON は UTF-8 の日本語をエスケープせず出力します。
- ID に対応するローカル run config を選び、設定とその参照先を検査します。インストール先を省略した場合、現在のインストール・設定に記録された過去のインストール・Desktop app のインストール先などの候補を探索します。`--install-dir` または `STRATA_INSTALL_DIR` が指定されるとその既存の絶対ディレクトリだけを対象にします。`--install-dir` は環境変数より優先されます。
- コンポーネント検査は `live=False` で呼ばれるため、このコマンドはエンジンを実行せず、GPU の live probe も実行しません。GPU/エンジン互換性は `unverified` として報告されます。コンポーネント検査は実行ファイル、tokenizer、設定で参照されたファイルやディレクトリ等の存在・状態を確認します。
- モデル ID は `[a-z0-9][a-z0-9_-]{0,127}` に一致する必要があります。設定ファイルはシンボリックリンクを拒否し、通常ファイルであること、1 MiB 以下であること、有効な JSON と必須フィールドを持つことを検査します。検査中に設定が変化した場合も失敗します。
- オプションおよびモデル検査経路はモデル設定・コンポーネントを読み取り専用で扱います。なお CLI の共通起動処理は Windows ではプロセスの既定 owner/DACL を現在ユーザー向けに設定しようとします（失敗しても起動を止めません）。これは `--json` 固有の処理ではありません。

## 出力とエラー

成功時は stdout に 1 個の JSON object を出し、終了コード 0 です。`--json` を付けて処理に失敗すると、共通例外処理が stdout に `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式の JSON を出します。主な失敗は次のとおりです。

- 不正なモデル ID はコード 2。
- 指定 ID の設定が見つからない、設定が不正、読み取り不能、または必要な調査対象を特定できない場合は通常コード 5。
- 検査中に run config が変更または無効化された場合はコード 6。
- `--install-dir` が絶対パスでない、または既存ディレクトリでない場合はコード 5。

引数構文の誤りや未知の引数は parser が処理するため、通常の argparse usage/error を stderr に表示して終了コード 2 になります。`--json` を付けても parser 自体のエラー表示は JSON 化されません。

## 根拠

- `strata_cli/cli.py:141-156` — `models inspect` の位置引数、`--install-dir`、`--output` の parser 定義。
- `strata_cli/cli.py:508-515` — `models_inspect` を含む one-shot parser 群へ `--json`（`store_true`）を共通追加。
- `strata_cli/cli.py:2232-2237` — `--json` から `output="json"` への変換と JSON 時の dispatch。
- `strata_cli/cli.py:527-542` — JSON 成功・失敗出力と終了コード。
- `strata_cli/cli.py:550-603` — `models.inspect` の呼び出し、JSON 成功 payload と人間向け表示。
- `strata_cli/cli.py:2166-2188` — `ValueError` / `OSError` 等の例外を JSON エラーにする経路。
- `strata_control/models.py:31-33, 62-72, 75-85` — ID 制約、`--install-dir` / `STRATA_INSTALL_DIR` とインストール解決。
- `strata_control/models.py:106-129, 173-182, 213-229` — 設定ファイルの検査、変更検出、inspect 結果・失敗コード。
- `strata_control/doctor.py:146-179, 181-235` — 読み取り専用コンポーネント検査、live probe の既定無効、互換性情報。
- `strata_control/private_files.py:349-389` — Windows 共通起動時の既定 owner/DACL 設定。
- 索引 `docs/cli/README.md:286-294` — `strata models inspect` のコマンド階層と `--json` の予定リンク。
