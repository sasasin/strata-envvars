# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済みプロファイル ID（必須）。小文字英字で始まり、小文字英字・数字・`_`・`-`を使う1〜64文字 |

## 役割

再起動する管理対象サーバーと、再起動時に読み込む保存済みプロファイルを指定する。プロファイル ID は `strata profile` が管理するプロファイルを特定し、現在のインスタンス状態の照会と候補起動計画の生成に使われる。`runtime restart` は稼働中の所有済みインスタンスを drain して候補設定で起動し直す操作であり、停止中のインスタンスを新規起動する用途ではない（parser: `strata_cli/cli.py:238-240`; dispatch: `strata_cli/cli.py:1345-1356`; host: `strata_control/runtime.py:1049-1059`）。

## 使い方

```sh
strata runtime restart --profile four-gpu
```

実行前に計画を確認する場合:

```sh
strata runtime restart --profile four-gpu --plan --output json
```

`four-gpu` は構文例であり、同名プロファイルが保存済みである必要がある。`--profile` は `restart` parser で必須指定されている（`strata_cli/cli.py:238-240`）。

## 値と既定値

- 値を1つ取る。parser に `required=True` があり、既定値はない（`strata_cli/cli.py:238-240`）。
- parser 自体では文字列を受け取り、実行時に `runtime._name()` が形式を検証する。ID は `[a-z][a-z0-9_-]{0,63}` に一致しなければならない（`strata_control/runtime.py:199`; `strata_control/profiles.py:25,48-51`）。大文字、空白、64文字超、先頭が小文字英字以外の値は拒否される。
- ID はプロファイルディレクトリ内の `<ID>.json` に対応する。明示的な `STRATA_PROFILE_DIR` があればそこを使い、なければ Windows は `%APPDATA%/Strata/profiles`、それ以外は `${XDG_CONFIG_HOME:-~/.config}/strata/profiles`（`strata_control/profiles.py:38-55`）。
- 指定ファイルは通常ファイルである必要があり、1 MiBを超えるファイル、読めないファイル、JSON/スキーマが無効なプロファイルは利用できない。未保存 ID は `profile '<ID>' is not saved; use strata profile create` で失敗する（`strata_control/profiles.py:120-166`）。

## 実行時の動作

CLI は `--profile` を `management.runtime_action()` に渡し、そこで ID を検証してから runtime host へ要求を送る。実行時には保存済みプロファイルから候補の起動引数、source config、revision を読み出す（`strata_cli/cli.py:1345-1356`; `strata_control/management.py:188-200,292-333`; `strata_control/runtime.py:787-791`）。

通常の再起動では、対象 profile の所有 host が現在 `ready` であることを確認する。現在の owner/instance ID の条件指定があれば照合し、候補プロファイルを事前検査した後、必要な drain を行って候補で起動する。起動後の readiness 確認に失敗すると、保持できる元の設定でロールバックを試みる（`strata_control/runtime.py:1049-1073,1074-1117`）。`--profile` 自体は再起動の設定値や待ち時間を変えず、対象プロファイルの選択だけを行う。

`--plan` は同じ profile の現在状態と保存済み候補を比較するプレビューで、drain/start は行わない。プレビュー成功時は profile revision、owner/instance ID、候補 source の digest などを返す（`strata_control/management.py:299-304`; `strata_control/runtime.py:1132-1164`）。プロファイルの保存内容を変えた後に実行する場合、`--if-profile-revision` などの実行前提条件をプレビュー結果に合わせて指定できる。source config の切り替え・編集を伴う場合は対応する明示フラグと `--if-source-sha256` が必要となる（`strata_control/management.py:299-326`; `strata_control/runtime.py:793-811,1060-1068`）。

## 適用条件と副作用

- 対象 profile に対してローカル owner host が管理する ready なインスタンスが必要。状態が ready でない場合は `runtime_not_ready` で終了し、別プロファイルや任意の PID を指定して操作するものではない（`strata_control/runtime.py:1049-1059`）。
- 通常の source config 切り替えは拒否される。`--allow-source-switch` を付ける場合、候補 source の SHA-256 を `--if-source-sha256` で確認する必要がある。実行中に使った同一 source ファイルが編集されている場合も、migration の明示許可と候補 digest が必要になる（`strata_control/management.py:305-310`; `strata_control/runtime.py:793-811,1239-1246`）。migration 時は drain 前に元の設定 bytes を owner 専用の rollback snapshot に保存し、成功後に不要な snapshot の削除を試みる（`strata_control/runtime.py:813-819,1074-1084,1094-1102`）。
- 通常の再起動では対象 server を drain/stop し、新しい server を起動するため、処理中のサービスに停止時間が生じる。失敗時は旧起動を再試行するが、元の source が利用可能で元の bytes を保つ場合に限られる（`strata_control/runtime.py:1085-1117`）。
- `--profile` のほか、restart は `--wait`（既定1000秒）、`--startup-wait`（既定300秒）、source変更許可、revision/owner/instance/digest 条件、`--plan` を受け付ける。`--profile` に別名はない。共通の `--json` は `--output json` の別名（`strata_cli/cli.py:238-254,508-515`）。

## 出力とエラー

- 人向け出力では `PROFILE: state` と、結果に応じて instance ID、API URL、readiness 状態、error を表示する。restart/verify の失敗時には取得できる範囲で engine log の場所と末尾3行を stderr に追加する（`strata_cli/cli.py:1360-1373,1376-1388`）。
- `--output json` または `--json` は結果オブジェクトを JSON で stdout に出す。共通エラー処理は JSON モードでは `{ok:false,error:{code,message}}`、人向けモードでは `strata: ...` を stderr に出す（`strata_cli/cli.py:527-532,1360-1373,2166-2188`）。
- profile の形式エラーなど `ProfileError` は通常終了コード2、保存ファイル欠落・不正などは5、再起動失敗や stale 条件などの実行失敗は主に6を返す。具体的な状態により戻り値が異なる（`strata_control/profiles.py:30-35,160-166`; `strata_control/runtime.py:1049-1068,1123-1130`; `strata_cli/cli.py:1370-1373`）。
- `--profile` 省略時は argparse が必須引数エラーを出す（`strata_cli/cli.py:238-240`）。

## 根拠

- parser と restart 専用引数: `strata_cli/cli.py:197-254`
- `--profile` の転送および出力/終了コード: `strata_cli/cli.py:1331-1373`
- profile ID と保存先・読み込み検証: `strata_control/profiles.py:25,38-55,120-166`
- restart の前提条件、journal 記録、runtime 呼び出し: `strata_control/management.py:188-200,292-336`
- restart、plan、drain/起動/rollback と snapshot: `strata_control/runtime.py:702-740,787-819,1043-1164`

調査範囲は上記 commit の checkout に含まれる Terminal CLI とローカル runtime 管理実装。異なる OS での実行や配布済み Release の動作は実行確認していない。
