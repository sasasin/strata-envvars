# `strata timeskip apply --dry-run`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip apply` |
| オプション | `--dry-run` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時 `false` |

## 役割

run が保持するチェックポイント（または `--attempt` で選んだ試行）を workspace に適用する前に、変更予定の相対パスを表示します。通常の `--dry-run` 経路は workspace のファイルを書き換えません。ただし state directory の作成は別途行われ、また `--restore` と併用すると dry-run にはなりません（後述）。

## 使い方

```sh
strata timeskip apply RUN_ID --dry-run
strata timeskip apply RUN_ID --workspace ./work-copy --attempt 1 --dry-run --output json
```

`RUN_ID` は `timeskip run` が記録した run ID です。`--workspace` を省略すると run に記録された workspace が対象になります。`--attempt` を付けると、選択済みチェックポイントではなく指定した revision attempt の内容をプレビューします（parser: `strata_cli/cli.py:380-393`）。

## 値、既定値、相互作用

- `--dry-run` は `argparse` の `store_true` です。引数値を受け取らず、省略時は実適用経路です（`strata_cli/cli.py:388-389`）。
- `--attempt` は任意の整数として解析され、parser で許容範囲は指定されていません。指定値に対応する attempt が run に記録され、その候補ディレクトリが存在する必要があります（`strata_cli/cli.py:385-387`、`strata_control/time_skip.py:612-615`）。
- 変更予定は baseline と選択内容のファイル inventory を比較して算出します。異なる、または新しいファイルは `would_write`、選択内容に存在しない baseline のファイルは `would_remove` に列挙されます。比較 inventory は相対パス、サイズ、SHA-256 を使い、`.git`、`__pycache__`、`.strata` ディレクトリとシンボリックリンクを対象外にします（`strata_control/time_skip.py:241-260,621-632`）。
- 実行前に destination の inventory digest が run 開始時の baseline digest と一致するかを確認します。workspace が変わっていれば、予定一覧を出さず競合として拒否します（`strata_control/time_skip.py:621-627`）。
- `--restore` も同時に指定した場合、CLI は `--dry-run` を確認する前に `restore_original()` を呼びます。このため元の baseline を実際に復元し、run の選択 checkpoint を更新・保存します。`--restore --dry-run` は安全なプレビューとして使えません（`strata_cli/cli.py:1531-1538`、`strata_control/time_skip.py:654-664`）。
- `--output` は `human`（既定）または `json` です（`strata_cli/cli.py:393`）。

## 実行時の動作と副作用

CLI は先に state directory を開き、run record を読み込んでから `TimeSkipRun` を再構成します。state directory の既定値は `$STRATA_TIMESKIP_DIR`、なければ `state_base()/time-skip` です。`--state-dir` を指定した場合はそのパスを使います。store と run の初期化ではディレクトリを `mkdir(..., exist_ok=True)` するため、未作成の場合は `--dry-run` でも state 側にディレクトリが作られます（`strata_cli/cli.py:1476-1485,1524-1530,1605-1610`、`strata_control/time_skip.py:321-326,341,695-700`）。

dry-run と判定された後は `would_write` / `would_remove` を返して終了し、通常適用で行う rollback copy の作成、workspace からの削除・コピーは行いません（`strata_control/time_skip.py:629-645`）。したがって「何も書かない」は workspace の適用処理についての説明であり、state directory 等を含む全ファイルシステム副作用がないという意味ではありません。

## 出力と失敗

- 人向け出力は `would write: PATHS`。削除予定があれば続けて `would remove: PATHS` を表示します。各一覧が空なら `(nothing)` と表示し、成功終了コードは `0` です（`strata_cli/cli.py:1546-1552`）。
- `--output json` は成功時に `schema_version: 1`、`ok: true`、`apply` を含む JSON を標準出力に出します。`apply` 内のプレビュー結果は `applied: false`、`dry_run: true`、`would_write`、`would_remove` です（`strata_cli/cli.py:631-632,1546-1547`）。
- run record が読めない場合や、選択された attempt が存在しない、baseline がない場合はエラーコード `2` です。通常の人向けエラーは `strata: ...` を標準エラーへ出し、JSON モードはエラー JSON を標準出力へ出します（`strata_cli/cli.py:1525-1540`、`strata_control/time_skip.py:612-619`）。
- destination が baseline 取得後に変わった場合は上書きを拒み、エラーコード `6` になります。人向けでは理由を標準エラーへ出し、JSON モードではコードと理由を含むエラー JSON を出します（`strata_cli/cli.py:1541-1545,527-532`、`strata_control/time_skip.py:621-627`）。

## 根拠

- `strata_cli/cli.py:380-393` — `timeskip apply` parser、`--dry-run` の型・既定値、同コマンドの関連 option。
- `strata_cli/cli.py:1476-1485,1524-1555,1605-1618` — state directory の決定、適用・dry-run・restore の分岐、表示と終了経路、run の再構成。
- `strata_cli/cli.py:527-542` — 人向け/JSON エラーと成功出力。
- `strata_control/time_skip.py:241-268,597-652` — inventory 対象、baseline 照合、差分計算、dry-run の早期 return、通常適用と rollback。
- `strata_control/time_skip.py:341,654-664,695-716` — run directory の作成、restore の保存動作、state store のディレクトリ作成と run record 読み込み。

調査対象 checkout は `main` が `origin/main` と一致し、`git status --short --branch` で未コミット変更はありませんでした。CLI help は実行せず、同一 revision の parser と実装を根拠にしています。ビルド済み/Release 版との比較は行っていません。
