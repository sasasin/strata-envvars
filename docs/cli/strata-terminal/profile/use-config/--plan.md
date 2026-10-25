# `strata profile use-config --plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile use-config` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は `false` |

## 役割

保存済み profile の参照先 run config を切り替える場合に、変更前後のパスと対象 config の `model_name` を確認します。`--plan` を指定した呼び出しは profile を保存せずに終了します。これは `strata serve --plan` や他コマンドの同名オプションとは別の parser scope です。

## 使い方

```sh
strata profile use-config local --from-config ./strata-run.json --plan
```

`local` は保存済み profile 名、`--from-config` は確認する run config のパスです。出力形式を JSON にする場合は `--output json` を追加できます。

## 値と既定値

- `--plan` は `argparse` の `store_true` フラグです。引数値は受け取らず、省略時は計画表示ではなく保存処理へ進みます（`strata_cli/cli.py:89-95`）。
- `--from-config CONFIG.json` は必須です。ファイルパスは `expanduser()` の後に存在するパスとして解決され、通常ファイルであることを確認します。JSON はオブジェクトで、`args` は文字列だけの配列、`exe` と `tokenizer` は空でない文字列でなければなりません（`strata_control/profiles.py:135-147,252-263`）。
- 出力は `--output human|json` で選び、省略時は `human` です（`strata_cli/cli.py:95`）。

## 実行時の動作

`--plan` の有無にかかわらず、まず profile を読み込み、指定 config を使う候補を作ります。読み込み時の profile revision が候補作成時の revision と異なる場合は中止します。また `--if-revision REVISION` が指定されている場合、候補の revision と一致しなければ中止します。これにより、事前に確認した profile から変更があった状態で適用することを防ぎます（`strata_cli/cli.py:968-975`）。`--if-revision` を省略した場合はこの追加の事前確認値との比較はありません。

`--plan` では `source_config` の変更前後、profile 名、revision、候補 config の `model_name`、パスが変わるかを示す `would_save` を返します。人向け出力は `Config: <変更前> -> <変更後>`、JSON 出力は成功応答の JSON です。通常保存時の分岐は実行せず、profile や run config の内容を変更しません。またこの処理は稼働中インスタンスを再起動しません（`strata_cli/cli.py:975-985`）。

## 適用条件と副作用

- 参照先 config の検証は計画表示でも実行されます。存在しないパス、通常ファイルでないパス、読み込めない JSON、必須フィールドの欠落は計画表示を拒否します（`strata_control/profiles.py:135-147,252-263`）。
- profile 読み込みは `read_bytes_repairing()` を使います。このヘルパーは権限を修復する場合があるため、`--plan` の経路でも profile ファイルに対するアクセス権の修復が起きる可能性があります（`strata_control/profiles.py:150-166`）。したがって、フラグが抑止するのは profile の設定保存であり、あらゆるファイルシステム上の副作用ではありません。
- 計画表示は `would_save` を前後の `source_config` パスの文字列比較から計算します。同じパスなら `false` ですが、保存処理自体は行いません（`strata_cli/cli.py:975-980`）。
- 保存先 profile の永続化は `--plan` を付けない場合にだけ行われます。通常保存は profile の履歴も記録し、保存後も稼働中インスタンスは変更されない旨を表示します（`strata_cli/cli.py:981-985`、`strata_control/profiles.py:266-295`）。

## 出力とエラー

- 成功時は終了コード `0` です。`--output human` では変更前後の config パスを表示し、`--output json` では `schema_version`、`ok`、`profile`、`revision`、`source_config`、`model_name`、`would_save` を含む JSON を標準出力へ出します（`strata_cli/cli.py:975-980,535-542`）。
- profile が未作成・不正、config を読めない、config の構造が不適切などの `ProfileError` は、通常の人向けエラーなら `strata: ...` を標準エラーへ出し、JSON 出力ならエラー JSON を標準出力へ出します。エラーコードは個々の検証により異なり、config 読み込み・未作成 profile などは `5`、既定の入力検証は `2` です（`strata_control/profiles.py:30-36,135-147,150-166,252-263`、`strata_cli/cli.py:527-532,2166-2173`）。
- profile が読み込み後に変化した場合、または `--if-revision` が一致しない場合は再計画を求めるエラーとなり、コード `6` で終了します（`strata_cli/cli.py:971-974`）。

## 根拠

- `strata_cli/cli.py:89-95` — `use-config` parser、必須 `--from-config`、`--plan` の真偽動作、revision 条件、出力形式。
- `strata_cli/cli.py:958-985` — profile 読み込み、revision 照合、計画結果、保存分岐と人向けメッセージ。
- `strata_cli/cli.py:527-542,2166-2173` — 成功・失敗の出力先、JSON 形式、終了コード処理。
- `strata_control/profiles.py:30-36,135-166` — `ProfileError`、run config 検証、profile 読み込みと権限修復ヘルパー。
- `strata_control/profiles.py:252-295` — 参照先 config の解決・検証と、通常保存時の revision 照合・履歴記録。

調査時点の Strata checkout は `main` が `origin/main` と一致し、`git status --short --branch` に未コミット変更はありません。CLI help は補助資料として実行しておらず、上記は同一 commit の parser と実装を根拠にしています。
