# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし（フラグ） |

## 役割

`runtime verify` parser の使い方と、その parser に登録された引数を表示します。対象はトップレベルや `runtime` 親コマンドのヘルプではなく、`strata runtime verify` 固有のヘルプです。索引もこのコマンド階層に個別文書を割り当てています。[`docs/cli/README.md:412-425`](../../../README.md)

## 使い方

```sh
strata runtime verify --help
```

短縮形は `strata runtime verify -h` です。ヘルプ表示では `--profile` などの通常実行用引数は不要です。

## 値と既定値

値を取りません。`runtime verify` は `argparse.ArgumentParser` の標準 help を無効化せず生成されているため、`--help` と `-h` が同じ help action として登録されます。parser 作成時に `add_help=False` を指定する箇所はありません。`strata_cli/cli.py:40-45` `strata_cli/cli.py:197-202` `strata_cli/cli.py:216-225`

## 実行時の動作

`strata runtime verify` parser は `runtime` の subparser として登録されています。表示内容には同 parser の `--profile`、`--wait`、`--load`、`--plan`、`--if-owner-id`、`--if-instance-id`、`--output` のほか、後から one-shot parser 群へ追加される `--json` と `--quiet` が含まれます。`strata_cli/cli.py:197-225` `strata_cli/cli.py:508-515`

通常の `main()` は parser に引数を渡す前に `private_files.adopt_user_defaults()` を呼びます。これは Windows 以外では `False` を返して何もしません。Windows では、以後プロセスが作成するファイルの既定 owner と DACL をユーザー向けに設定する処理を試みます。したがってヘルプ表示でもこの呼び出し自体は通りますが、runtime の検査・モデル生成を行う `_runtime()` には進みません。`strata_cli/cli.py:2217-2224` `strata_control/private_files.py:349-389` `strata_cli/cli.py:1331-1358`

## 適用条件と副作用

ヘルプは `runtime verify` parser のみを対象にします。ヘルプ action により解析が終了するため、runtime の API 確認や一トークン生成は呼び出されません。通常処理へ進む分岐は `parse_known_args()` の後にあり、`_runtime()` が `management.runtime_action()` を呼ぶのは `_run()` が選ばれた場合です。`strata_cli/cli.py:2217-2237` `strata_cli/cli.py:1331-1358`

ただし前述のとおり、CLI 共通の `adopt_user_defaults()` は parser の実行前に呼ばれます。Windows では現在のプロセスの既定 owner/DACL を変更し得ますが、Strata の runtime やモデルファイルを変更する処理ではありません。`strata_control/private_files.py:349-389`

## 出力とエラー

標準 `argparse` help action が選択 parser の usage と説明・引数一覧を標準出力へ表示し、正常終了します。ヘルプ以外の不正な引数は `parse_known_args()` 後に `ap.error()` で扱われ、usage とエラーを表示して終了コード 2 になります。独自の `--help` validation やエラー処理はありません。`strata_cli/cli.py:2223-2231`

## 根拠

- `strata_cli/cli.py:40-45` — ルート `ArgumentParser` と subparser の生成。
- `strata_cli/cli.py:197-202` — `runtime` の subparser 階層。
- `strata_cli/cli.py:216-225` — `verify` parser と固有引数。
- `strata_cli/cli.py:508-515` — verify parser を含む one-shot parser 群への `--json` / `--quiet` 追加。
- `strata_cli/cli.py:2217-2237` — parser 実行前の共通処理、引数解析、通常処理への分岐。
- `strata_cli/cli.py:1331-1358` — runtime action の呼び出し箇所。
- `strata_control/private_files.py:349-389` — Windows の既定 owner/DACL 設定処理。

確認範囲は上記 revision の Terminal CLI parser とその起動経路です。ヘルプ文字列を実行して取得することはせず、parser 定義から説明しています。
