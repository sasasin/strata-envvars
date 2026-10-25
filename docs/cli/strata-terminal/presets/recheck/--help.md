# `--help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。help action として登録される |

## 役割

`strata presets recheck` の使い方、位置引数、同コマンドで受理されるオプションを表示する。`--help` はトップレベルや他の `presets` サブコマンドの help と別スコープであり、このコマンドの parser に対する組み込み help である。

## 使い方

```sh
strata presets recheck --help
strata presets recheck -h
```

通常の `preset` と `target` を指定しなくても help を表示できる。help 表示だけなら preset の再計測は開始しない。

## 値と既定値

値は不要で、`--help=value` のような値付き指定はこの parser の help 構文ではない。`-h` は同じ help action の短縮別名である。`presets recheck` parser で明示的に `--help` を追加するコードはなく、親・子 parser が `argparse.ArgumentParser` の既定設定で作成されるため、`argparse` が `--help` と `-h` を自動登録する。

この help に含まれる同一 parser の引数は、位置引数 `preset` と `target`、および `--output {human,json}`、`--gpu-lock GPU_LOCK`、`--serve-dir SERVE_DIR`、`--work-dir WORK_DIR`、`--status-file STATUS_FILE`、`--boot-timeout BOOT_TIMEOUT`、`--no-quiet-check`。位置引数の説明は `target` が profile 名または run configuration であることを示す。標準 help formatter は既定値を一覧に付けないため、値の既定値を確認する場合は parser 定義を参照すること。

## 実行時の動作

help action は parser の解析中に usage と引数説明を標準出力へ書き、成功 status で終了する。したがって `main()` の後続の `_run()` と `presets_command()`、`_recheck()` には到達せず、プリセット検索、エンジン情報確認、計測用 worker 起動、recheck 結果の記録は行わない。

ただし、エントリポイント `strata.py` は `main()` の前に Control の handover 判定と `serve`/`bench` 専用 preflight を実行する。`presets recheck` はその preflight 対象ではない。`main()` 自体は parser を作る前に `private_files.adopt_user_defaults()` を呼ぶ。この関数は Windows 以外では何もせず、Windows では現在のプロセス token の既定 owner/DACL を設定しようとする。設定できない場合も例外を送出しない。よって help は再計測や preset state の変更を起こさないが、Windows ではこのプロセスレベルの初期化が先に試みられる。

## 適用条件と副作用

- help は `presets recheck` の parser に対して適用される。コマンド階層を含む例は `strata presets recheck --help`。
- 出力先を切り替える `--output` は help 自身の出力形式を変える指定ではなく、recheck 実行時の通常 parser option として表示される。
- `--help` による計測、worker/process 起動、進捗 status file の書き込み、preset の recheck 記録はない。前述の Windows token 初期化は parser 呼び出しより前に行われる。

## 出力とエラー

通常は usage と各引数の説明を標準出力へ表示し、終了 status `0` で終了する（標準 `argparse` help action）。help action が実行されると必須位置引数 `preset` と `target` の不足による parser error には進まない。ソース checkout 上で同 revision の help CLI を別途実行して出力を採取することはしていないため、端末幅や Python 版による折り返しを含む実表示は確認していない。

## 根拠

- `strata_cli/cli.py:40-45` — トップ parser を標準 `argparse.ArgumentParser` で作成し、サブコマンド parser 群を登録する。
- `strata_cli/cli.py:486-489` — `presets` parser 群の登録箇所。
- `strata_cli/tune_commands.py:49-55` — `presets` parser とその子 parser を作成。`add_help=False` は指定されておらず、`common()` が `--output` を追加する。
- `strata_cli/tune_commands.py:82-90` — `recheck` の説明、位置引数、および help に列挙される同一スコープのオプション。
- `strata_cli/cli.py:2217-2237` — `main()` の初期化、引数解析と dispatch の順序。引数解析が正常終了した後に `_run()` へ進む。
- `strata_cli/cli.py:2151-2153` — `presets` が `tune_commands.presets_command()` へ委譲される箇所。
- `strata_cli/tune_commands.py:411-447` — recheck 実行時の preset/target 読み込み、worker と計測の呼び出し、結果記録。help action は parse 中に終了するためここには到達しない。
- `strata.py:30-42` — CLI entry point の handover/preflight と `main()` 呼び出し順。preflight は `serve` / `bench` のみ。
- `strata_control/private_files.py:349-389` — Windows での user-default token 設定と、非 Windows での no-op、失敗時に例外を出さない動作。
- 索引の照合: `docs/cli/README.md:912-923` は `strata presets recheck` の配下に `--help`（alias `-h`）を掲載。

調査範囲は上記 checkout の Python CLI source である。同 revision の配布 archive や Windows 実行環境での表示・handover 条件は実行確認していない。
