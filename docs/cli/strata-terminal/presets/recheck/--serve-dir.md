# `strata presets recheck --serve-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--serve-dir` |
| 別名 | なし |
| 値 | `serve/` ディレクトリを含むディレクトリのパス |

## 役割

保存済みチューニング preset の再測定で起動する一時 worker が、`serve.server` をどの場所から実行するか指定します。インストール先以外の Strata checkout にある `serve/` を使う場合などに指定します。索引上の `strata tune auto --serve-dir` とは別スコープのオプションです。

## 使い方

```sh
strata presets recheck <preset> <profile-or-config.json> --serve-dir /path/to/Strata/terminal
```

指定先は `serve/` 自体ではなく、それを含む親ディレクトリです。

## 値と既定値

値は任意のパス文字列で、parser は `default=None` として受け取ります。別名、型変換、choices、パスの存在確認やディレクトリ検証は定義されていません（`terminal/strata_cli/tune_commands.py:88-93`）。

省略時は `Path(__file__).resolve().parent.parent`、すなわちこのコマンド実装ファイルの配置を基準にした Terminal 側ディレクトリが使われます。明示値は `Path(a.serve_dir)` に変換され、そのまま worker の `cwd` に渡されます。空文字列は parser では受理されますが、truthy 判定により既定の場所へ戻ります（`terminal/strata_cli/tune_commands.py:179-182`）。

## 実行時の動作

`strata presets recheck` は preset と対象 profile / JSON 設定を読み、測定用 `WorkerSession` を作ります。その `serve_dir` が worker 起動に使われ、worker は現在の Python で `-m serve.server` を実行します（`terminal/strata_cli/tune_commands.py:615-644`; `terminal/strata_control/tune_session.py:563-569`）。再チェックは保存済み設定を測定し、必要に応じて prompt 速度を再測定します（`terminal/strata_control/autotune.py:937-946, 970-1007`）。

指定パスが worker 起動に適さない場合、起動失敗は再チェック結果 `retune` として扱われます。コマンドはその結果を preset に記録し、通常の human / JSON 結果を出力します。再チェック結果の記録は preset の `recheck.last_result` を更新します（`terminal/strata_cli/tune_commands.py:652-662`; `terminal/strata_control/presets.py:441-458`）。worker 起動時には設定・ログファイルが作業ディレクトリに作られます。`--work-dir` がなければ一時ディレクトリを使い、終了時に削除します（`terminal/strata_cli/tune_commands.py:640-644`; `terminal/strata_control/tune_session.py:545-569`）。

## 適用条件と副作用

この値が使われるのは `presets recheck` の worker 起動時です。値の検査や自動補正はなく、誤った場所では `serve.server` を開始できず再チェックが `retune` になり得ます。worker は `--host 127.0.0.1` で起動し、再チェック終了時には停止されます（`terminal/strata_control/tune_session.py:563-569, 583-592, 598-610`）。GPU ロックなど別の再チェックオプションの仕様は本書の対象外です。

## 出力とエラー

通常の再チェック結果は stdout に human または JSON 形式で出力されます。 worker が開始できない、または起動タイムアウトになった場合は `StartFailed` として再チェック処理に渡され、失敗理由を含む `retune` 結果になります（`terminal/strata_control/tune_session.py:570-592`; `terminal/strata_control/autotune.py:964-975`）。その結果は保存され、コマンドは結果表示の経路を通ります。preset や対象の解決など、再チェック開始前のエラーは CLI の `_fail` 経由で stderr（human）または JSON（machine）に出力されます（`terminal/strata_cli/tune_commands.py:527-530`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:88-93` — `presets recheck` parser と `--serve-dir` の定義。
- `terminal/strata_cli/tune_commands.py:179-182` — 明示値と既定値の選択。
- `terminal/strata_cli/tune_commands.py:615-644, 652-662` — 再チェックでの値の受け渡し、再チェック結果の保存と出力。
- `terminal/strata_control/tune_session.py:563-592, 598-610` — worker の起動ディレクトリ、起動失敗・timeout、worker 停止。
- `terminal/strata_control/autotune.py:937-946, 964-1007` — worker 起動失敗を含む再チェック判定。
- `terminal/strata_control/presets.py:441-458` — 再チェック結果の preset への記録。
