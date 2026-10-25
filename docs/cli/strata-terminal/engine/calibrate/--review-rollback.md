# `--review-rollback`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。調査対象 checkout は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--review-rollback REPORT.json` |
| 別名 | なし |
| 値 | 適用済み calibration report のファイルパス |
| 既定値 | なし。このアクションを選ぶ場合は値が必要 |

## 役割

`--review-rollback` は、指定した calibration report に対応する適用記録とバックアップを照合し、設定を適用前の状態へ戻せるかを表示します。確認だけを行い、復元はしません。復元操作は [`--rollback-result`](--rollback-result.md) です。どの calibration アクションを実行するかは相互排他で必須のため、`--plan`、`--measure`、`--review-result`、`--apply-result`、`--rollback-result` と同時には指定できません。

## 使い方

```sh
strata engine calibrate --profile local --review-rollback ./calibration-report.json
```

`--profile` は必須です。保存済みプロファイル名、または run config JSON のパスを指定します。`REPORT.json` は `--measure --out` で作成し、`--apply-result` で適用した calibration report を指定します。相対パスは実行時の作業ディレクトリから解決されます。

## 値と既定値

parser は値を `REPORT.json` として受け取り、`Path` に変換して review 処理へ渡します。パスの存在や report の形式は parser では検証せず、処理側が読み込み時に検証します。`--review-rollback` 自体に既定値はありません。通常出力は `--output human`（既定）で、`--output json` または alias の `--json` を指定すると機械可読 JSON になります。`--quiet` も parser で受理されますが、JSON 出力時は通常の JSON 応答を返します。

## 実行時の動作

review 処理は、まず `--profile` の対象を解決し、calibration report と適用記録を読みます。report は通常ファイルで 2 MiB 以下、schema・kind・suite・report ID・設定値・内容ハッシュが期待形式に合う必要があります。適用記録と report の ID／ハッシュ、対象 config、profile revision、バックアップの SHA-256 なども照合します。

その後、次の状態を確認して `applicable` と `reasons` を返します。

- report の source config と現在の対象が一致するか。
- config と setup settings のバックアップ、および現在の両ファイルが適用記録のハッシュと一致するか。
- エンジン、モデル、ハードウェア、プロファイル revision などの identity が適用時と一致するか。
- profile のポートに応答するサービスがないか。

人向け出力は結果オブジェクトの JSON 表示です。JSON モードでは `schema_version: 1`、`ok`（`applicable` と同値）、`rollback_review` を含む JSON オブジェクトを出力します。`ok` が false の場合も確認結果を出力し、終了コード 6 を返します。true の場合は終了コード 0 です。

## 適用条件と副作用

この操作は config や setup settings を書き換えず、エンジンや GPU も起動しません。ただし、保存済みの report、owner-only の適用記録・バックアップ、対象 config などの読み取りが必要です。report と適用記録は通常ファイルであること、report と rollback ファイルは 2 MiB 以下であることを要求し、POSIX では適用記録・バックアップの owner-only 条件も確認します。

identity の確認には `setup.py` と `tools/calibrate.py` を含む完全な Strata folder が必要です。Terminal archive にそれらが含まれない場合、`STRATA_INSTALL_DIR` でその folder を指定しないと identity を確認できず、エラーになります。モデル integrity はファイル内容の完全検証ではなく metadata のみと結果に明記されます。

ポート確認では対象 profile の host/port に最大 0.2 秒の TCP 接続を試みます。接続できると `profile_port_is_active` が不適用理由になります。その他の stale 状態は、たとえば config/settings の変更、バックアップの変更、profile・engine・hardware identity の変化として `reasons` に記録されます。`--exclusive` はこの review には使えず、parser 上も `--measure`、`--apply-result`、`--rollback-result` にだけ許可されています。

## 出力とエラー

- 通常の確認結果は stdout に JSON 形式で表示されます。JSON モードでは一行の JSON 応答です。
- report／適用記録／backup がない、形式が不正、owner-only 条件を満たさない、読み取れない場合はエラーになります。共通エラー処理は人向けでは `strata: ...` を stderr に、JSON モードでは `ok: false` と `error` を含む JSON を stdout に出します。
- 確認自体が成立しても `applicable: false` なら終了コード 6 です。report や記録の読み取り・形式エラーでは処理に応じて 5、一般的な引数・profile エラーでは既定で 2 などの終了コードが返ります。

## 根拠

- `strata_cli/cli.py:174-189` — `engine calibrate` parser、必須 `--profile`、アクションの相互排他、引数と出力形式。
- `strata_cli/cli.py:508-515` — one-shot parser に対する `--json` alias と `--quiet` の追加。
- `strata_cli/cli.py:1059-1064, 1096-1103` — `--review-rollback` の呼び出し、JSON/human 出力、`applicable` による終了コード。
- `strata_cli/cli.py:2119-2173, 527-542` — CLI の例外処理、エラー出力と戻り値。
- `strata_control/calibration.py:339-360` — report のファイル形式・サイズ・内容ハッシュ検証。
- `strata_control/calibration.py:456-523, 629-643` — owner-only の適用記録とバックアップの読み込み・検証。
- `strata_control/calibration.py:646-681` — rollback review の照合項目、結果、読み取り専用 preview。
- `strata_control/calibration.py:90-92, 142-166, 192-202` — 対象解決、identity 検証、ローカルポート確認。
- `strata_control/calibration.py:41-64` — 完全な Strata folder を要求する条件と `STRATA_INSTALL_DIR` の扱い。

調査範囲は上記 revision の Terminal CLI と `strata_control.calibration` のソースです。別 OS 上の権限判定やネットワーク環境での実行結果は実測していません。
