# `strata profile --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 値を取らないフラグ |

## 役割

`strata profile` グループの使い方を表示します。この階層には `create`、`list`、`show`、`validate`、`set`、`use-config`、`edit`、`history`、`rollback` が登録されています。`profile` 自体にはさらに必須のサブコマンドがあるため、グループのヘルプ表示はその一覧を確認する用途です。各サブコマンド固有の引数やオプションを確認するには、そのサブコマンドの `--help` を使います。

## 使い方

ソース checkout のルートで:

```sh
python strata.py profile --help
```

`-h` は同じ help action の短縮表記です。配布済み CLI では `strata profile -h` も同じスコープを表示します。

## 値と既定値

`--help` / `-h` は `argparse.ArgumentParser` が標準で提供するヘルプ action です。parser は `add_help=False` を指定せず作成されているため、別の値、既定値、値の検証規則はありません。`profile` parser には `required=True` のサブパーサーが設定されていますが、`--help` は引数解析中に表示して終了するので、サブコマンドの指定は不要です。

## 実行時の動作

この parser の help action は `strata profile` の概要と登録済みサブコマンドを表示し、通常の profile 処理へ進まずに終了します。`strata profile` の create/list/show などの処理へ分岐するのは、引数解析後に `main()` が `_run()` を呼び、その後 `_profile_command()` に到達した場合です。

CLI の `main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows ではプロセストークンの既定 owner と DACL の設定を試み、設定できたかどうかにかかわらず profile データを作成・変更しません。Windows 以外では直ちに `False` を返します。従って通常の POSIX 実行では help 表示に伴うこの関数の作用はありません。

## 出力とエラー

`argparse` の標準 help action によりヘルプを標準出力へ表示し、処理を成功として終了します。ヘルプ表示のために profile を読み書きする処理へは進みません。CLI 独自のエラー出力や profile 操作の終了コードは、この help action には適用されません。

## 適用条件と調査範囲

この文書は `strata profile` グループの help に限ります。トップレベルの `strata --help` と、各子コマンドの help は別スコープです。調査したのは指定 commit のソース parser と呼び出し経路で、別の Release binary の出力は確認していません。`argparse` 自体の表示書式は Python 標準ライブラリに委ねられ、実行環境の端末幅や Python バージョンによって折り返しが異なる場合があります。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser を `argparse.ArgumentParser` で作成し、サブコマンドを登録。
- `strata_cli/cli.py:69-105` — `profile` parser、必須の子 parser、および子コマンドの登録。
- `strata_cli/cli.py:2217-2231` — CLI が parser を作成して引数を解析する経路。
- `strata_cli/cli.py:2127-2128`, `strata_cli/cli.py:958-968` — 通常解析後に `profile` 処理へ進む分岐。
- `strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-389` — 引数解析前の既定 owner/DACL 設定呼び出しと、その Windows 限定動作。
- `strata.py:30-43` — source checkout のエントリーポイントから CLI `main()` を呼び出す箇所。
