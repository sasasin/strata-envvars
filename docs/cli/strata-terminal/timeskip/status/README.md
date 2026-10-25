# `strata timeskip status`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip status RUN_ID` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/time_skip.py` |

## 役割

保存済み Time-skip run の記録を読み、run の状態、チェックポイント、試行、判定を確認します。新しい run の開始や workspace への反映は行いません。run の開始は [`strata timeskip run`](../run/README.md)、反映・復元は [`strata timeskip apply`](../apply/README.md) の役割です（`strata_cli/cli.py:1500-1522,1524-1555`）。

## 使い方

```sh
# run コマンドが表示した ID で詳細を確認
strata timeskip status RUN_ID

# run を別の保存場所に記録した場合は、その場所を指定
strata timeskip status RUN_ID --state-dir ./timeskip-state

# 機械処理向けの JSON
strata timeskip status RUN_ID --output json
```

`RUN_ID` は必須の位置引数です。サブコマンドは `strata timeskip` の下に登録されており、`strata timeskip` だけでは実行できません（`strata_cli/cli.py:348-350,371-374`）。このページのオプション scope は `status` に限られます。個別の値と動作は [`--state-dir`](--state-dir.md)、[`--output`](--output.md)、[`--help`（`-h` alias）](--help.md) を参照してください。

## 表示と実行時の動作

- 既定の human 出力では、run ID、状態、workspace、prompt を表示し、各 checkpoint の ID・digest の先頭12文字・チェック outcome、各 attempt の番号・decision・reason を続けて表示します。decision が記録されている場合は outcome、reason、保持対象を表示し、証拠から自動選択できず利用者の確認が必要なら、その旨も表示します（`strata_cli/cli.py:1507-1522`）。
- `--output json` は保存された run 全体を `run` に含め、共通の成功 envelope `{ "schema_version": 1, "ok": true, "run": ... }` として出力します。記録には workspace、prompt、状態、check 定義と結果、checkpoint、attempt、decision などが含まれるため、JSON には人向け表示より詳細なデータが含まれます（`strata_cli/cli.py:1500-1506,535-542`、`strata_control/time_skip.py:349-367`）。
- 保存場所は `--state-dir` が指定されていればそのパス、なければ `STRATA_TIMESKIP_DIR`、それもなければ OS のユーザー状態領域にある `strata/time-skip` です。POSIX の基点は `$XDG_STATE_HOME/strata`（未設定時は `~/.local/state/strata`）、Windows は `%LOCALAPPDATA%\Strata`（未設定時はユーザープロファイル下の `AppData\Local\Strata`）です（`strata_cli/cli.py:1476-1485`、`strata_control/paths.py:13-21`）。
- `status` は state store から `RUN_ID/run.json` を読み取ります。CLI 起動時に store を初期化するため、保存ディレクトリが存在しない場合は作成されます（`strata_control/time_skip.py:695-700,715-716,374-379`）。

## 主な副作用と注意点

run 記録や workspace は変更しませんが、既定または指定された state directory が未作成ならディレクトリを作ります。人向け表示には prompt と workspace のパスが含まれ、JSON 出力には保存された詳細な記録が含まれます。出力先やログの扱いに注意してください（`strata_cli/cli.py:1476-1485,1507-1522`、`strata_control/time_skip.py:349-367,695-700`）。

status の表示は保存時点の durable record に基づくもので、処理中の run を別プロセスに問い合わせて最新状態を取得する実装ではありません（`strata_control/time_skip.py:695-716,374-379`）。保存先や run ID を誤らないよう、`run` の完了表示または `strata timeskip list` で ID を確認してください（[`strata timeskip list`](../list/README.md)）。

指定した ID の `run.json` が見つからない場合は `TimeSkipError` を捕捉し、human では標準エラーに `strata: ...`、JSON では `ok: false` のエラー envelope を出して終了コード `2` を返します。ファイルアクセスなどの `OSError` は共通処理でエラーとして扱われ、終了コード `6` になります（`strata_cli/cli.py:1500-1505,527-532,2176-2183`、`strata_control/time_skip.py:374-379`）。

## 関連文書

- [`strata timeskip` コマンド概要](../README.md)
- [`strata timeskip run`](../run/README.md)
- [`strata timeskip list`](../list/README.md)
- [`strata timeskip apply`](../apply/README.md)
- [`STRATA_TIMESKIP_DIR` 環境変数](../../../../STRATA_TIMESKIP_DIR.md)
- [CLI 文書索引](../../../README.md)

## 根拠

- Strata `strata_cli/cli.py:348-350,371-374` — `timeskip status` の階層、必須位置引数、オプション。
- Strata `strata_cli/cli.py:1467-1485,1500-1522` — 保存場所の選択、run の読込、human / JSON 表示と missing-run error。
- Strata `strata_cli/cli.py:527-542,2176-2183` — 共通のエラー・成功出力とファイル操作エラー。
- Strata `strata_control/time_skip.py:349-379,695-716` — 永続 run 記録のフィールド、`run.json` の読込、state directory の初期化。
- Strata `strata_control/paths.py:13-21` — POSIX / Windows のユーザー状態ディレクトリ。
- `docs/cli/README.md:692-698` — `strata timeskip status` の索引リンクとオプション scope。

調査は上記 commit の checkout 内ソースに基づきます。同一 revision の CLI `--help` と Release 配布物は確認していないため、配布版の表示や OS ごとの実動作は調査範囲外です。
