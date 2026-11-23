# `strata components engines --feed`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | 文字列を1つ取る。parser に型・URL/ディレクトリ形式の検証はない |

## 役割

このコマンドでは `--feed` は受理されますが、処理に使われません。`strata components engines` はこの PC にインストール済みの engine をローカルから一覧表示するコマンドで、指定した feed の読み込みやネットワークアクセスは行いません。`--feed` が feed の選択に使われるのは `strata update` など別の処理経路です。

## 使い方

```sh
# engines 一覧はローカルから取得される。ここで指定した feed は参照されない。
strata components engines --feed https://updates.example.invalid/strata-feed.json
```

feed を切り替えて更新内容を確認する場合は `strata update --check --feed URL` のように `update` で指定します。

## 値と既定値

parser は `--feed` を値なしの `None` を既定値として登録し、値を文字列として受け取ります。`URL|DIR` という形式や存在確認をこの parser で検証する処理はありません。繰り返し指定時を含め、`engines` の一覧処理は保存された値を読みません。そのため、このコマンドでは値の内容や省略の有無によって一覧結果は変わりません。 (`terminal/strata_cli/update_cmd.py:47-49`, `terminal/strata_cli/update_cmd.py:445-465`)

## 実行時の動作

`components engines` の parser は共通引数群から `--feed` を登録します (`terminal/strata_cli/update_cmd.py:82-83`, `terminal/strata_cli/update_cmd.py:47-49`)。実行時には CLI dispatcher が `update_cmd.run` に渡し (`terminal/strata_cli/cli.py:2210-2212`)、`run` は `engines` を `_engines_command` に分岐します (`terminal/strata_cli/update_cmd.py:337-338`)。この分岐は `lib.list_engines(ctx)` の結果を human または JSON 形式で出力して終了します (`terminal/strata_cli/update_cmd.py:445-465`)。feed source の解決 (`_feed_source`) はこの分岐より後にある更新処理でのみ呼ばれ、`--feed`、`STRATA_UPDATE_FEED`、記憶済み feed、既定 feed の順に選びます (`terminal/strata_cli/update_cmd.py:142-151`, `terminal/strata_cli/update_cmd.py:351-355`)。

一覧処理はインストール済み engine のファイルを走査し、適合性や使用中状態などをまとめます。`list_engines` は「読み取りのみ、変更・ダウンロードなし」と定義され、engine 一覧を作ります (`terminal/strata_control/engine_library.py:152-167`)。従って `--feed` の指定はこのコマンドのファイル・ネットワーク・プロセスへの作用を増やしません。

## 適用条件と副作用

`--feed` は `components engines` で常に無視されます。feed が無効な URL、存在しないディレクトリ、空文字列であっても、このオプション自体による feed 検証・取得はありません。コマンドが読む engine の保存先や検出対象は `--components-dir` / `STRATA_COMPONENTS_DIR` と `--backend` 等、別の共通引数や実行環境に依存しますが、`--feed` はそれらを変更しません (`terminal/strata_cli/update_cmd.py:47-53`, `terminal/strata_cli/update_cmd.py:314-321`, `terminal/strata_control/engine_library.py:98-122`)。

## 出力とエラー

成功時、通常出力では engine の一覧・合計サイズと「変更なし」の案内を表示し、`--output json` または `jsonl` では一覧データを JSON として出力します (`terminal/strata_cli/update_cmd.py:56`, `terminal/strata_cli/update_cmd.py:450-465`)。この一覧分岐は feed の解析・検証をしないため、feed の接続失敗や feed 署名エラーは `--feed` が原因では発生しません。その他の一覧処理・ローカル環境に由来する失敗の全ての経路と終了コードは、この調査では網羅していません。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-49` — 共通 parser における `--feed` の宣言、既定値と他の共通引数。
- `terminal/strata_cli/update_cmd.py:82-83` — `components engines` が共通引数を登録する箇所。
- `terminal/strata_cli/cli.py:2210-2212` — `components engines` を `update_cmd.run` へ委譲する dispatch。
- `terminal/strata_cli/update_cmd.py:303-321`, `337-338`, `445-465` — 実行時の context 作成、engine 一覧への分岐、human/JSON 出力。
- `terminal/strata_cli/update_cmd.py:142-151`, `351-355` — feed 解決が更新経路で呼ばれることと選択順。
- `terminal/strata_control/engine_library.py:98-134`, `152-167` — ローカル engine の走査と、読み取り専用の一覧生成。
