# `strata bench report --quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench report` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ |
| 既定値 | 無効 |

## 役割

成功したときの人間向け標準出力を抑制します。レポートの読み込み、検証、要約や Markdown の生成を省略するものではありません。`strata bench report` は保存済みベンチマーク結果を読み取り、要約を表示するコマンドです。入力は run ディレクトリまたは結果ファイルを位置引数 `path` に指定します（`strata_cli/cli.py:339-342, 1134-1162`）。

## 使い方

```sh
strata bench report ./bench-results/run-01 --quiet
```

## 値と既定値

`--quiet` は `store_true` で定義された値なしのフラグです。`bench_report` を含む one-shot parser 群に共通して追加され、`default=argparse.SUPPRESS` のため省略時には Namespace に属性がありません。実行時は `getattr(a, "quiet", False)` で参照されるので、省略時は無効です。値を指定する形式や追加の値検証はありません（`strata_cli/cli.py:339-342, 508-515, 2236-2243`）。

## 実行時の動作

quiet が有効で出力形式が `json` / `jsonl` でない場合、CLI は `_run()` 中の標準出力を最大64 KiBの捕捉領域にリダイレクトします。処理の戻り値が成功（終了コード0）なら捕捉した標準出力は表示しません。既定の `--output human` では通常の要約が抑制され、`--output markdown` でも Markdown 本文が標準出力に出る経路と、`--out` の成功確認行が抑制されます（`strata_cli/cli.py:1134-1162, 2196-2214, 2236-2248`）。

`--output json` または alias の `--json` を併用した場合は機械可読出力を維持するため quiet の捕捉経路に入りません。`--out NEW_FILE` は `--output markdown` と併用する必要があり、quiet でも Markdown ファイルは作成されます（`strata_cli/cli.py:341-342, 508-515, 1131-1133, 2232-2237`）。

読み込み対象が標準ベンチマーク形式なら標準形式用の検証・要約を使い、それ以外は serving benchmark report として読み込みます。どちらの形式でも quiet は読み込みや検証の選択・結果を変えません（`strata_cli/cli.py:1134-1162`; `strata_cli/bench_standard.py:1256-1265`; `strata_cli/bench.py:891-949`）。

## 適用条件と副作用

- この `--quiet` は `strata bench report` parser に追加される共通 one-shot オプションです。ベンチマークを実行する `strata bench run` の出力・測定には関与しません（`strata_cli/cli.py:315-342, 508-515`）。
- quiet は標準出力を捕捉するだけです。`--out` 指定時の Markdown 書き込みは継続します。書き込み先が既存ファイルまたは symlink の場合は上書きせず失敗し、出力内容の上限は64 KiBです（`strata_cli/cli.py:1153-1160`; `strata_cli/bench.py:1301-1308`）。
- 捕捉領域を超える標準出力があった場合、保持されるのは末尾64 KiBです。コマンド失敗時に捕捉内容があれば stderr に戻され、切り詰めがあった場合は省略メッセージも stderr に出ます（`strata_cli/cli.py:2196-2208, 2241-2248`）。

## 出力とエラー

- 成功時: `--output human`（既定）と `--output markdown` の標準出力は抑制されます。`--output json` / `--json` の JSON 出力は抑制されません（`strata_cli/cli.py:1131-1162, 2232-2248`）。
- `--out` を使う場合、生成 Markdown は指定ファイルへ書かれます。成功確認の `Markdown report: ...` は標準出力なので quiet で抑制されます（`strata_cli/cli.py:1138-1145, 1153-1159`）。
- serving report は通常ファイルで4 MiB未満であることが必要です。読み込み不能や形式不正はエラーになり、形式不正は終了コード5、I/O エラーは終了コード6です（`strata_cli/bench.py:891-900, 902-949`; エラーの stderr/JSON 化: `strata_cli/cli.py:527-532, 2166-2188`）。標準形式と判定された入力は専用 validator に渡され、64 MiBを超える場合や不正な場合は `ProfileError`（終了コード5）になります（`strata_cli/bench_standard.py:1241-1253, 1256-1265`）。
- `--out` が `--output markdown` と併用されていない場合は終了コード2です。出力先の既存ファイル拒否は終了コード2、生成 Markdown が64 KiBを超える場合は終了コード6です。quiet はエラーを無効化せず、人間向けエラーは stderr に出ます（`strata_cli/cli.py:1131-1133, 2166-2188`; `strata_cli/bench.py:1301-1308`）。

## 根拠

- 索引上のコマンド階層と配置: `docs/cli/README.md:652-660`。
- `report` parser と位置引数、出力形式: `strata_cli/cli.py:339-342`。
- one-shot parser への `--quiet` / `--json` 追加: `strata_cli/cli.py:508-515`。
- report の標準形式・serving 形式の分岐、Markdown と JSON / human 出力、`--out` 制約: `strata_cli/cli.py:1129-1162`。
- quiet 捕捉、上限64 KiB、成功時の破棄と失敗時の stderr 出力: `strata_cli/cli.py:2196-2214, 2232-2248`。
- serving report の読み込み、サイズ・形式検証: `strata_cli/bench.py:891-949`。
- 標準 report の形式判別と専用読み込み: `strata_cli/bench_standard.py:1250-1265`。
- Markdown 出力のサイズ制限、既存ファイル拒否、新規作成: `strata_cli/bench.py:1301-1308, 668-677`。
- エラー出力と終了コード処理: `strata_cli/cli.py:527-542, 2166-2188`。

調査時の Strata checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。確認したのは指定 revision のソースと索引です。同一 revision の CLI help、Release 配布物、他 platform の実行結果との照合は行っていません。ソースの parser 定義と実際の report / quiet 処理を根拠にしています。
