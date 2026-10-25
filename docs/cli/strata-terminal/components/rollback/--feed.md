# `strata components rollback --feed`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。調査時の状態は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されなかった。

索引では `strata components rollback` の option として掲載されている（`docs/cli/README.md:227-238`）。この文書は `strata components rollback` parser の `--feed` を扱う。

## 値と既定値

- `--feed URL|DIR` は値を1つ取る。parser は `strata_cli/update_cmd.py:30-32` の共通定義で `default=None` として登録され、rollback parser にも `strata_cli/update_cmd.py:57-59` で適用される。
- parser に `type`、`choices`、独自 validator はなく、URL やディレクトリの形式を parser 段階で検証しない。help 文は「URL または folder」と説明している（`strata_cli/update_cmd.py:31`）。
- update 系で通常の feed source を選ぶ順序は、真の値の `--feed`、`STRATA_UPDATE_FEED`、コンポーネント状態に保存された feed、既定 GitHub feed である（`strata_cli/update_cmd.py:87-95`）。既定値は `https://github.com/Niko1221/Strata/releases/latest/download/strata-feed.json`（`strata_cli/update_cmd.py:23-26`）。

## rollback での実行時の動作

`--feed` は rollback parser に存在しますが、`strata components rollback` の実行では使われない。`run()` は最初に `source=""` の context を作り、rollback の分岐で `updater.rollback_engine(ctx)` を呼び、その後に通常更新向けの `_feed_source(a, root)` を呼ぶ経路へ進む（`strata_cli/update_cmd.py:182-200`）。したがって、このコマンドに `--feed` を渡しても feed URL/ディレクトリの選択、feed の読み込み、ネットワーク取得、署名検証には影響しない。`STRATA_UPDATE_FEED` もこの rollback 分岐では参照されない。

rollback が調べるのは feed ではなく、選択中の components directory に保存された update state の `engine.previous` である。既定 directory は `--components-dir` がなければ `ec.components_dir()`（`strata_cli/update_cmd.py:174`）。rollback 処理は前回版の engine をローカルから読み、manifest と全ファイルを検証し、現在の PC で起動対象として選択できるか確認してから pin/active/previous state を更新する。ダウンロードは行わない（`strata_control/updater.py:1033-1078`）。

## 適用条件と副作用

- rollback では `--feed` の値は空でないかどうかも含めて参照されず、形式検証もされない。値を受け取る parser 上の option ですが、rollback の効果・適用条件には関与しない（`strata_cli/update_cmd.py:30-32, 57-59, 182-200`）。
- rollback には利用可能な `engine.previous` が必要。存在しなければ `UpdateError`（終了コード 2）になる（`strata_control/updater.py:1036-1042`）。前回版の manifest またはファイル検証が失敗した場合は終了コード 5（同: `1043-1049`）。
- rollback 対象がすでに使用中の previous 版であれば、変更するものがないとして終了コード 2（`strata_control/updater.py:1050-1054`）。前回版が現在の PC に適合しない場合は pin を戻し、終了コード 5（同: `1057-1066`）。
- 成功すると engine の選択状態を前回版へ切り替え、旧版を `pinned` / `active` として記録し、tuning preset を短い再確認の対象として印付けする場合がある。preset は削除しない（`strata_control/updater.py:1055-1078`、CLI 表示: `strata_cli/update_cmd.py:188-196`）。
- engine serving 中の待機判断には `--wait` が関係する。rollback も `_maybe_wait` の後で処理される（`strata_cli/update_cmd.py:185-188`）。

## 出力と失敗経路

成功時の human 出力は切替元・切替先、tuning preset の状態、より新しい版を再試行する案内を表示する。`--output json` または `jsonl` は共通 parser で受理され（`strata_cli/update_cmd.py:39`）、rollback 成功時は JSON オブジェクトを出力する（`strata_cli/update_cmd.py:188-195`）。

`UpdateError` は human mode で stderr に `strata: <message>`、machine mode で JSON error にして例外の終了コードを返す（`strata_cli/update_cmd.py:167-172, 225-226`）。rollback 中に feed を参照しないため、`--feed` の不正・到達不能な参照先や feed の署名・内容による失敗は、この option に起因する rollback の失敗経路にはならない。

## 根拠

- parser と共通 option: `strata_cli/update_cmd.py:30-59`
- feed source の選択（通常 update 経路）: `strata_cli/update_cmd.py:87-95`
- rollback の分岐順、出力、例外処理: `strata_cli/update_cmd.py:163-234`
- rollback の state 読み込み、ローカル検証、切替と失敗条件: `strata_control/updater.py:1033-1078`
- CLI の command dispatch: `strata_cli/cli.py:2135-2137`
