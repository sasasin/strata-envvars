# `--help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし |

## 役割

`strata update` の usage と、その parser に登録された引数の説明を表示する。トップレベルの `strata --help`、および `strata components update --help` とは別の parser scope である。

## 使い方

```sh
strata update --help
```

短縮形も使える。

```sh
strata update -h
```

## 値と既定値

値は取らない。CLI は標準の `argparse.ArgumentParser` と subparser を使い、`update_cmd.add_parsers` がトップレベルに `update` parser を登録する。独自の help action、型変換、validation、既定値は定義されていないため、`argparse` 標準の `-h` / `--help` action が使われる（`strata_cli/cli.py:40-45,139-140`; `strata_cli/update_cmd.py:42-49`）。

## 実行時の動作

指定すると argparse が現在の `update` parser のヘルプを標準出力へ出し、正常終了する。表示対象には `update_cmd.py` の共通引数（`--feed`、`--components-dir`、`--backend`、`--wait`、`--force`、`--model-config`、`--output`）、update 固有引数（`--check`、`--app`、`--app-version`、`--no-engine`、`--no-control`）、および上位 CLI が後から追加する `--json` と `--quiet` が含まれる（`strata_cli/update_cmd.py:30-48`; `strata_cli/cli.py:508-515`）。

ヘルプ action は引数解析中に終了するので、通常の dispatch と `update_cmd.run()` に到達せず、フィードの読込、更新確認、ダウンロード、インストールは行わない（`strata_cli/cli.py:2223-2237,2135-2137`; `strata_cli/update_cmd.py:163-200`）。ただし共通 CLI 初期化では引数解析の前に `private_files.adopt_user_defaults()` が呼ばれる。依存モジュールがない場合は `ImportError` を捕捉して続行する（`strata_cli/cli.py:2217-2224`）。この呼び出しの内部動作はここでは追跡していない。

`--json` と `--quiet` はこのコマンド用 parser にも登録されるが、`--help` で終了する場合は `main()` の後段にある実行時出力モード処理には進まない（`strata_cli/cli.py:508-515,2224-2237`）。

## 適用条件と副作用

`update` の位置で指定する。この parser に対して `strata update` の usage が表示される。オプション自体は値の検証や設定変更をせず、更新処理も起動しない。共通初期化中の `adopt_user_defaults()` が呼ばれる点は上記のとおりで、その具体的な副作用は本調査では確認していない。

## 出力とエラー

表示内容は Python `argparse` が parser 定義から生成するため、ソース上では固定のヘルプ全文や折返し幅は定められていない。標準 help action は usage/説明を出力して終了する。誤ったオプション名など help action に至らない parser エラーの文面・終了コードは `argparse` 標準の処理であり、このオプション固有の validation error はない。

## 根拠

- `strata_cli/cli.py:40-45,139-140` — ルート parser とトップレベル `update` parser の生成・登録。
- `strata_cli/update_cmd.py:30-49` — 共通引数と `strata update` 固有引数の定義。
- `strata_cli/cli.py:508-515` — one-shot parser 群（`update_parsers` を含む）への `--json` / `--quiet` 追加。
- `strata_cli/cli.py:2217-2237,2135-2137` — 初期化、引数解析、通常 dispatch との順序。
- `strata_cli/update_cmd.py:163-200` — update 実処理の入口と実行経路。
