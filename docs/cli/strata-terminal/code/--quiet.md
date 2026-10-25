# `strata code --quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値なしのフラグ。指定すると真になる |

## 役割

人向けの標準出力を通常時に表示せず、処理が失敗した場合は捕捉した標準出力を診断情報として表示する共通の quiet 処理を有効にします。`strata code` の parser では `action="store_true"` で定義され、既定値は `False` です（`strata_cli/cli.py:494-498`）。

## 使い方

```sh
strata code --quiet
```

この checkout では `strata code` の実処理が利用できず、現在の実行結果はエラー終了になります（下記「出力とエラー」参照）。

## 値と既定値

`--quiet` 自体は値を取りません。省略時は `False`、指定時は `True` です。別名や追加の範囲・値検証は parser に定義されていません（`strata_cli/cli.py:494-498`）。値を続けて指定した場合は通常の未認識引数として parser が拒否します（`strata_cli/cli.py:2223-2231`）。

## 実行時の動作

`main()` は `--quiet` が真で、出力形式が `json` / `jsonl` でない場合、`status`、`monitor`、`logs`、`connection`、`config`、通常の `serve` 以外のコマンドについて標準出力を `_QuietCapture` にリダイレクトして `_run()` を呼びます。成功時は捕捉内容を出力せず、失敗時は捕捉した内容を標準エラーへ戻します。捕捉容量は末尾 64 Ki文字で、超過して失敗した場合は省略を知らせる行も標準エラーに出します（`strata_cli/cli.py:2196-2214,2236-2248`）。

この設定は人向け標準出力に対するものです。標準エラーはリダイレクトされず、そのまま表示されます。`json` / `jsonl` 出力では quiet 捕捉を行わず、機械可読出力を保ちます（`strata_cli/cli.py:2236-2243`）。

`strata code run` にも同名の `--quiet` が別 parser action としてあります。また `code run` は `--output jsonl` を既定にしているため、その出力形式では共通の quiet 捕捉分岐は適用されません。`strata code --quiet`（`code` parser のオプション）と `strata code run --quiet`（`run` parser のオプション）はコマンド階層上の別スコープです（`strata_cli/cli.py:494-504`）。

## 適用条件と副作用

このオプションはコマンド実行時の標準出力をメモリー上に一時捕捉します。コード上の上限は 64 Ki文字で、上限を超えると古い内容を捨てて末尾を保持します（`strata_cli/cli.py:2196-2208`）。ファイルや設定を書き換える副作用は、このオプションの処理にはありません。

ただし、対象 revision の `_run()` は `command == "code"` を受けると、常に共有 Desktop harness component が未インストールで coding sessions は利用不可というエラーを返し、終了コード `5` を指定しています。`--quiet` でこのエラーは抑制されません。人向け形式のエラーは `_error()` により標準エラーへ書かれるためです（`strata_cli/cli.py:527-532,2162-2165`）。CLI 文書もこの revision で `strata code` は利用不可と説明しています（`docs/TERMINAL.md:277`）。

## 出力とエラー

この revision で `strata code --quiet` を実行すると、人向けエラー `strata: the shared Desktop harness component is not installed; coding sessions are unavailable` が標準エラーに出て、終了コード `5` になります。quiet は標準出力だけを捕捉するため、このエラー表示を隠しません（`strata_cli/cli.py:2162-2165,527-532,2236-2248`）。

## 根拠

- `strata_cli/cli.py:494-504` — `code` parser と `--quiet`、および `code run` 側の別オプションと既定出力形式。
- `strata_cli/cli.py:2196-2214,2236-2248` — quiet 時の標準出力捕捉、失敗時の再出力、上限超過時の通知、機械可読出力との分岐。
- `strata_cli/cli.py:2162-2165,527-532` — `code` コマンドの未対応エラーと、人向けエラーの出力先・終了コード。
- `strata_cli/cli.py:2223-2231` — 引数解析と未認識引数の失敗経路。
- `docs/TERMINAL.md:277` — この revision で `strata code` が利用不可である旨。
