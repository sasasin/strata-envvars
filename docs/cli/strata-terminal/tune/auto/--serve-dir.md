# `--serve-dir`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--serve-dir` |
| 別名 | なし |
| 値 | `serve/` パッケージを含むディレクトリのパス |

## 役割

自動チューニング中に測定用 worker を起動する際の作業ディレクトリを指定します。チューナーはこの場所を subprocess の `cwd` にして `serve.server` を起動するため、指定先には `serve/` が必要です。エンジン実行ファイルの場所や、チューニング結果の作業ディレクトリを指定するオプションではありません。

## 使い方

```sh
strata tune auto "My profile" --serve-dir /opt/strata
```

`/opt/strata` は `serve/` を含むディレクトリを表す例です。相対パスも指定できます。その場合は `strata` プロセスの現在の作業ディレクトリから解決されます。

## 値と既定値

parser は値を文字列として受け取り、既定値は `None` です。パスの存在、ディレクトリであること、`serve/` の有無を parser 段階では検証しません。値が空文字列なら未指定と同じ既定経路になります。

未指定または空文字列の場合、`strata_cli/tune_commands.py` の配置から計算したインストール側のルート（`Path(__file__).resolve().parent.parent`）を使います。指定値は `Path` に変換されますが、絶対パスへの変換や正規化は行われません。

## 実行時の動作

`strata tune auto` は `_serve_dir(a)` の戻り値を `WorkerSession` に渡します。各測定では現在の設定をコピーした JSON と worker / engine log を作業ディレクトリに用意し、現在の Python interpreter で `-m serve.server` を起動します。subprocess の `cwd` に `--serve-dir` の値を設定し、標準出力と標準エラーは worker log にまとめます。したがって、指定先は Python が `serve.server` を import する基点になります。

この値は `--work-dir` とは独立です。`--work-dir` は run config とログなどを置く場所であり、`--serve-dir` は worker 起動時のカレントディレクトリです。

## 適用条件と副作用

このオプションは `strata tune auto` の測定 worker 起動に適用されます。指定先から各測定用 worker が起動し、測定後に終了処理されます。`strata_cli/tune_commands.py` にはパスの事前検査がないため、存在しないディレクトリでは subprocess 起動時の `OSError` が worker の `FAIL_BOOT` として扱われます。ディレクトリは存在しても `serve/` が見つからない場合は、worker の起動後に import に失敗する可能性があります。

同名の `--serve-dir` は別コマンド `strata presets recheck` にも定義されていますが、この文書の対象は索引上の `strata tune auto` スコープです。

## 出力とエラー

パーサ段階でパス不正を理由に拒否する処理は確認できません。worker の起動時に `OSError` が発生した場合は `StartFailed("FAIL_BOOT", ...)` に変換され、チューナーの測定失敗として記録されます。worker が起動後に終了した場合は worker / engine log と終了コードから失敗種別を判定します。最終的な人間向けまたは JSON の結果出力は `strata tune auto` の通常結果経路に従います。

## 根拠

- Strata `strata_cli/cli.py:486,1652-1653` — `tune auto` の parser 登録と dispatcher。
- Strata `strata_cli/tune_commands.py:20-47` — `--serve-dir` の宣言と既定値。
- Strata `strata_cli/tune_commands.py:126-130,217-219` — 未指定時の既定ディレクトリ、値の `Path` 化、`WorkerSession` への受け渡し。
- Strata `strata_control/tune_session.py:420-435,463-484` — `WorkerSession` のディレクトリ設定、測定用ファイル、`serve.server` の argv と `cwd`。
- Strata `strata_control/tune_session.py:485-507` — 起動 `OSError` の `FAIL_BOOT` 化、起動後の worker 終了・ready timeout の扱い。
- Strata `strata_control/autotune.py:303-338` — `StartFailed` を失敗 run として記録する処理。
