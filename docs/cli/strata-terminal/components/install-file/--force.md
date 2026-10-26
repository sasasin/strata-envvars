# `--force`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `False`、指定時 `True` |

## 役割

指定したローカル engine package が現在インストール済みの engine より古い場合でも、インストール処理へ進めます。通常は古い package を `current` として扱い、ファイルを変更しません。

このサブコマンドでの `--force` は、更新 feed が記録した「test start に失敗した version」や手動 rollback で飛ばした version の再試行抑止を解除するものではありません。そうした抑止は feed を使う更新経路の判定で、ローカルファイル経路では version の新旧だけを確認します（根拠: `strata_control/updater.py:609-620`, `strata_control/updater.py:1088-1092`, `strata_control/updater.py:1138-1145`）。

## 使い方

```sh
strata components install-file ./strata-engine.tar.gz --force
```

位置引数 `file` には手元にダウンロードした engine package を指定します。parser の説明は `.tar.gz` または `.zip` を示しますが、実装は `.tgz` と `.tar.xz` も形式名として受け付けます（`strata_cli/update_cmd.py:59-61`, `strata_control/updater.py:1080-1085`）。

## 値と既定値

`argparse` の `action="store_true"` で宣言されるため値は不要です。既定値は偽で、フラグを付けると真になります（`strata_cli/update_cmd.py:30-39`, `strata_cli/update_cmd.py:59-62`）。

## 実行時の動作

CLI はこの値を `updater.Context.force` に渡し、`install_engine_file()` を呼びます（`strata_cli/update_cmd.py:193-195`, `strata_cli/update_cmd.py:208-216`）。インストール済み engine の version がローカル package より新しいとき、`--force` なしでは `status="current"` を返して処理を終えます。`--force` があればこの比較による早期終了をせず、通常の install 経路へ進みます（`strata_control/updater.py:1138-1145`）。

`--force` を付けても、package の展開、manifest の読み込み、信頼済み鍵による署名確認、全ファイルの整合性確認、現在の PC との適合性確認は行われます。その後も stage 上の engine を test start し、成功してから切り替えます。従ってこのフラグはこれらの検証や test start を省略しません（`strata_control/updater.py:1102-1132`, `strata_control/updater.py:994-1006`）。

## 適用条件と副作用

- 作用する条件は、インストール済み engine があり、その version が指定ファイルの version より新しい場合です。同じ version または新しい package について、この比較を理由にした拒否はありません（`strata_control/updater.py:1138-1145`）。
- install は components directory の update lock を取得して行われます。稼働中 engine があれば `_maybe_wait()` の確認後に idle を待ち、待ち時間内に停止しなければ `Busy` で失敗します。`--force` は稼働中 engine の置換を許可しません（`strata_cli/update_cmd.py:208-212`, `strata_cli/update_cmd.py:258-273`, `strata_control/updater.py:306-317`, `strata_control/updater.py:71-81`）。
- 成功時は新しい engine を active にし、以前の engine を rollback 用に保持し、更新履歴と state を保存します。必要な tuning preset は再確認対象としてマークされます。指定した archive 自体は削除されません（`strata_control/updater.py:1023-1077`, `strata_control/updater.py:1088-1092`, `strata_control/updater.py:1142-1148`）。
- 検証や test start に失敗した場合は切替を完了せず、stage directory を片付けます。test start 失敗は busy に起因しない限り失敗理由を state に記録します（`strata_control/updater.py:1001-1022`, `strata_control/updater.py:1076-1077`, `strata_control/updater.py:1146-1148`）。

## 出力とエラー

成功時、既定の human 出力は結果の note または engine 更新結果を表示します。`--output json` は結果を JSON で出力し、`--output jsonl` は処理 phase 等の event と最終結果を JSON Lines で出力します（`strata_cli/update_cmd.py:65-87`, `strata_cli/update_cmd.py:208-216`）。

`UpdateError` は human 出力では `strata: ...` を stderr に出し、JSON/JSONL 指定時は error object を出します。package 不在、形式不正、署名・整合性・PC 適合性の拒否は終了コード 5、稼働中 engine 等による busy は 7 です。test start の失敗は終了コード 6 です（`strata_cli/update_cmd.py:174-183`, `strata_cli/update_cmd.py:246-255`, `strata_control/updater.py:60-81`, `strata_control/updater.py:85-128`, `strata_control/updater.py:1080-1085`, `strata_control/updater.py:1092-1132`）。

## 根拠

- parser と共通 option 宣言: `strata_cli/update_cmd.py:30-39`, `strata_cli/update_cmd.py:57-62`
- 引数から context への伝搬、install-file の dispatch と出力: `strata_cli/update_cmd.py:174-195`, `strata_cli/update_cmd.py:208-216`
- install-file における force の実際の判定: `strata_control/updater.py:1088-1145`
- 検証と検証失敗の扱い: `strata_control/updater.py:1102-1132`
- test start、切替、state 保存、stage cleanup: `strata_control/updater.py:994-1077`
- test start 失敗の説明と終了コード: `strata_control/updater.py:85-128`
- engine 稼働中の待機と busy 経路: `strata_control/updater.py:71-81`, `strata_control/updater.py:306-317`, `strata_cli/update_cmd.py:258-273`
- feed 更新側の失敗済み・rollback 済み version 判定との違い: `strata_control/updater.py:609-620`, `strata_control/updater.py:964-975`

調査範囲は指定 revision の Terminal CLI parser と、それが呼び出す updater 実装です。実際の archive を用いたインストールや各 OS/backend での動作確認は行っていません。
