# `--help`（`strata runtime status`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime status` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプを表示して終了する |

## 役割

`strata runtime status` の利用方法を表示します。`runtime status` は `--profile` で指定した profile に属するローカル管理対象 instance の状態を調べるコマンドです。この文書の `--help` は、その status コマンド parser に対するヘルプです。トップレベルの `strata --help` や `strata runtime --help` とは対象範囲が異なります。

## 使い方

```sh
strata runtime status --help
strata runtime status -h
```

## 値と既定値

値は不要です。`argparse.ArgumentParser` と `add_parser()` は通常の `--help` / `-h` action を自動追加し、この parser では `add_help=False` による無効化もありません（`strata_cli/cli.py:40-46,202-215`）。同じ status parser には `--profile`（必須）と `--output {human,json}`（既定値 `human`）が定義されています。また one-shot parser 群への共通処理で `--json` と `--quiet` も追加されます（`strata_cli/cli.py:508-515`）。これらはヘルプ出力に列挙されますが、`--help` 自体の引数ではありません。

## 実行時の動作

`--help` を指定すると、argparse がこの parser の usage と option 説明を標準出力に表示し、終了コード `0` で終了します。同一 revision の `bin/strata runtime status --help` で表示内容を確認し、ソースの parser 定義と照合しました。表示には `-h, --help`、必須の `--profile PROFILE`、`--output {human,json}`、`--json`、`--quiet` が含まれます。

ヘルプ action は通常の必須引数チェックより先に終了するため、`--profile` を付けなくても上記コマンドは成立します。status handler には進まず、profile の解決や runtime instance への状態問い合わせは行いません。通常の status 実行では `_runtime()` から management 層を経由して `runtime.status(profile)` を呼びます（`strata_cli/cli.py:1331-1356`、`strata_control/management.py:231-235`、`strata_control/runtime.py:444-455`）。

## 適用条件と副作用

この option は `strata runtime status` の parser に属し、コマンド階層上の他の `--help` とは別スコープです。`--help` 表示のために instance の状態確認や停止などの runtime 操作は実行されません。

ただし CLI の `main()` は parser を作って引数を解析する前に `private_files.adopt_user_defaults()` を呼びます（`strata_cli/cli.py:2217-2224`）。この関数は Windows でプロセス token の既定 owner と既定 DACL を現在のユーザー向けに設定することを試み、他 OS では何もしません（`strata_control/private_files.py:349-358`）。そのため Windows ではヘルプ表示だけでもこのプロセス設定が試行されます。runtime status の handler が実行されることを意味するものではありません。

## 出力とエラー

正常なヘルプ表示では usage と option 一覧を標準出力へ出し、終了コード `0` で終了します。引数解析で不正な引数がエラーになる通常経路では argparse がエラーを標準エラーへ表示し、終了コード `2` で終了します（`strata_cli/cli.py:2223-2231`）。ただし `--help` を含む複合的な不正引数の順序ごとの挙動は調査していません。

## 根拠

- `strata_cli/cli.py:40-46,202-215` — parser 作成、runtime 階層、および `status` の `--profile` / `--output` 定義。
- `strata_cli/cli.py:508-515` — `runtime_status` parser への共通 `--json` / `--quiet` 追加。
- `strata_cli/cli.py:1331-1356`、`strata_control/management.py:231-235`、`strata_control/runtime.py:444-455` — 通常実行時の status handler と問い合わせ経路。
- `strata_cli/cli.py:2217-2231` — 引数解析前の初期化、argparse 呼び出し、未認識引数の失敗経路。
- `strata_control/private_files.py:349-358` — Windows における `adopt_user_defaults()` の適用条件と目的。
- 同一 checkout の `bin/strata runtime status --help` — 表示された usage と `-h` alias を確認。補助確認であり、option 定義の根拠は上記 parser ソース。

## 調査範囲

調査対象は記載した commit のソースと、その checkout の Terminal CLI help 表示です。別の配布 revision、Windows 上での実際の token 設定結果、argparse の全ての複合引数順序は確認していません。
