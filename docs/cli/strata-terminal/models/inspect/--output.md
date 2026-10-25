# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models inspect` |
| オプション | `--output` |
| 別名 | なし（同じ parser に `--json` フラグもある） |
| 値 | `human` または `json` |

## 役割

ローカルのモデル run config と関連コンポーネントの検査結果を、人向け表示または JSON で stdout に出します。ファイルへ保存するオプションではありません。

## 使い方

```sh
strata models inspect qwen3-27b --output json
```

`model_id` は必須の位置引数です。実際の config ID に置き換えてください。人向け表示が必要なら `--output human` を指定します（省略時と同じです）。

## 値と既定値

- parser は `human` と `json` のみを受け付け、既定値は `human` です。ほかの値は argparse の引数エラーになります。
- 同じ parser には `--json` も追加されており、指定時は実行前に出力形式を `json` にします。`--output human --json` を併記した場合も `--json` が優先します。
- `--quiet` を併用した場合、人向けの成功出力は抑制されます。JSON 出力時は quiet の抑制処理を通らず JSON が出ます。

## 実行時の動作

`human` はモデル ID、コンポーネント状態、実行互換性が未検証である旨、config のパス、検出コンポーネント数と issue 数を1行ずつ表示します。`json` は共通の成功 envelope（`schema_version: 1`, `ok: true`）に、`scope: local_run_config`、install directory、モデル要約、コンポーネント report を含めて1行の JSON として出します。

`--output` 自体は検査対象や探索範囲を変えません。`--install-dir` を指定した場合はそのディレクトリだけが調査対象になり、省略時は環境変数 `STRATA_INSTALL_DIR`、Terminal 側のインストール、記憶済みインストール、Desktop アプリ側などの run config を持つ場所が探索されます。検査は run config と参照先コンポーネントを読み取り、engine・tokenizer・引数で指定されたファイル等の存在状態を報告します。モデル engine の起動やモデルロードは行わず、実行互換性は未検証のままです。

## 適用条件と副作用

成功時の検査は読み取り専用です。run config はシンボリックリンクでない通常ファイルで、サイズは最大1 MiB、必要な `exe`・`tokenizer`・文字列 `args` を含む JSON である必要があります。モデル ID は `strata-<model_id>.json` の `<model_id>` 部分に対応し、`[a-z0-9][a-z0-9_-]{0,127}` に合致する必要があります。検査中に config が変化した場合は再試行を促す失敗になります。

標準の inspection は GPU/driver の実動作互換性を検証せず、driver probe は未検証として扱います。`--output` はこの検査条件を変えません。

## 出力とエラー

- 成功時は終了コード `0`。`human` は上記の要約を stdout に、`json` は成功 envelope を stdout に出します。
- 引数値が `human` / `json` 以外なら parser が拒否します。
- 不正な model ID はエラーとなり、通常は終了コード `2`。対象 config が見つからない場合や config が読めない・形式不正の場合は終了コード `5`、検査中に config が変更された場合は `6` です。
- `json` の失敗時は `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式を stdout に出します。人向けの場合は `strata: ...` を stderr に出します。
- `--quiet` と人向け出力を併用して成功した場合、stdout の人向け出力は抑制されます。失敗時には捕捉済み出力があれば stderr に戻されます。

## 根拠

- parser の `--output` 値・既定値と必須 ID: `strata_cli/cli.py:153-156`。
- `--json` の追加と `--output json` への変換: `strata_cli/cli.py:508-515`, `strata_cli/cli.py:2232-2237`。
- inspect の実行、human 表示、JSON 成功出力: `strata_cli/cli.py:550-603`, `strata_cli/cli.py:535-542`。
- install directory の優先・validation と探索先: `strata_control/models.py:62-81`, `strata_control/discovery.py:160-203`。
- model ID、config の安全性・形式、summary、変更検出: `strata_control/models.py:30-33`, `strata_control/models.py:88-129`, `strata_control/models.py:158-182`, `strata_control/models.py:213-229`。
- コンポーネント確認と driver/実行互換性の未検証範囲: `strata_control/doctor.py:146-179`, `strata_control/doctor.py:181-234`。
- CLI のエラー形式と終了コード処理: `strata_cli/cli.py:527-533`, `strata_cli/cli.py:2166-2188`; `ProfileError` は `ValueError` 系で終了コードを保持します: `strata_control/profiles.py:30-35`。
- 調査範囲: 上記 checkout のソースコードを確認しました。同一 revision の CLI help や Release 配布物は別途確認していません。
