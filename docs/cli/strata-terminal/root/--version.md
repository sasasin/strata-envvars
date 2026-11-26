# `--version`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata`（トップレベル） |
| オプション | `--version` |
| 別名 | なし |
| 値 | 取らない（`nargs=0`） |

## 役割

Terminal の製品表示版、Terminal の build 版、実行中の Python の版と実行ファイルパスを1行で表示する。parser に登録された root オプションであり、サブコマンドを付けずに実行できる。`strata-engine` など別ツールの同名オプションとはスコープが異なる。

## 使い方

```sh
strata --version
```

## 値と既定値

`--version` は値を受け取らない。parser は `_VersionAction` を `nargs=0` で登録しており、別名や既定値は設定していない（`terminal/strata_cli/cli.py:30-37,62-66`）。製品表示版は `PRODUCT_VERSION` 定数（この revision では `0.2.21`）。build 版は `strata_cli.version()` が決める。まず `terminal/VERSION` を UTF-8 で読み、空または読めない場合は Terminal または隣接する `engine/CMakeLists.txt` の `project(... VERSION ...)` を探し、それも読めない・見つからない場合は `unknown` を返す（`terminal/strata_cli/__init__.py:13-33`）。

## 実行時の動作

action は stdout に `strata <製品表示版> (build <build版>; python <Python版> at <実行ファイルパス>)` と改行を出し、`parser.exit()` を呼ぶ。argparse の既定により終了コードは 0 で、通常のサブコマンド処理には進まない（`terminal/strata_cli/cli.py:30-37,64-66`）。

インストール済み Terminal でより新しい Control が有効なら、入口は parser より前に同じ引数をその Control に渡すため、表示される版と Python は引き継ぎ先のものになる。引き継ぎは無効化環境変数がなく、新しい Control が検出され、起動ファイル一式がそろう場合に限られる。対象が壊れている場合や起動に失敗した場合は警告を stderr に出して現在の Control で続行する。ソース checkout からの起動では通常この引き継ぎを行わない（`terminal/strata.py:35-48`; `terminal/strata_cli/handover.py:27-29,126-158`）。

## 適用条件と副作用

`strata.py` の入口は parser に入る前に親プロセス監視、Control の引き継ぎ判定、Windows の古い `strata.ps1` launcher の修復、RAM budget 設定の一回限りの移行を試みる。後二者は該当条件でファイルを変更し得る。launcher 修復は Windows で Strata 所有の古い `strata.ps1` が `strata.cmd` と並んでいる場合に名前変更とログ追記を行い、RAM budget 移行は対象設定を移行してバックアップを残し、確認済み folder に marker を書く（`terminal/strata.py:35-62`; `terminal/strata_cli/launcher_heal.py:55-76`; `terminal/strata_cli/ram_budget_move.py:55-70`）。従って、オプション action 自体は表示のみだが、起動前処理まで含めてファイル変更が絶対にないとは言えない。

旧 updater が staging folder の新 Control を `STRATA_NO_ACQUIRE=1` で単独起動し、引数が `--version` だけで、引き継ぎ guard が未設定の場合は、通常の版表示をせず旧 Terminal の更新方法を案内して終了コード 7 を返す（`terminal/strata.py:43-48`; `terminal/strata_cli/handover.py:167-185`）。また、POSIX launcher は利用可能な Python がなければ起動前に stderr へ案内を出し、終了コード 5 で終了する（`terminal/bin/strata:90-102`）。

## 出力とエラー

通常経路の1行は stdout に出力される。parser action の終了コードは 0。起動前処理の Control 引き継ぎ失敗は stderr の警告後に通常表示へ fallback し、旧 updater 例外は stderr ではなく案内文を stdout に出して終了コード 7。launcher が Python を見つけられない場合は stderr と終了コード 5（`terminal/strata_cli/cli.py:30-37`; `terminal/strata_cli/handover.py:142-158,174-185`; `terminal/bin/strata:90-102`）。

## 根拠

- `terminal/strata_cli/cli.py:30-37,62-66` — 独自 action の出力・終了と root parser への登録、引数なしの定義。
- `terminal/strata_cli/__init__.py:13-33` — 製品表示版定数と build 版のファイル・fallback 順。
- `terminal/strata.py:35-62` — parser 起動前の引き継ぎ、launcher 修復、RAM budget 移行、起動 preflight。
- `terminal/strata_cli/handover.py:27-29,126-158,167-185` — checkout 判定、Control 引き継ぎ、旧 updater の例外経路。
- `terminal/strata_cli/launcher_heal.py:55-76` — Windows launcher の修復条件とファイル変更。
- `terminal/strata_cli/ram_budget_move.py:55-70` — 一回限りの設定移行と marker 書き込み。
- `terminal/bin/strata:90-102` — POSIX launcher で Python が見つからない場合の失敗経路。
