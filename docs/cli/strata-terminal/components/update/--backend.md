# `--backend`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | エンジン backend 名を1つ取る。parser は値候補を制限しない |

## 役割

更新対象 PC の backend 自動検出を指定値で置き換え、署名付き feed から更新対象エンジンを選ぶための指定です。`strata components update` と `strata update` は同じ `_common` parser 定義を使います（`strata_cli/update_cmd.py:30-59`）。

## 使い方

```sh
strata components update --backend cuda --check
```

`--check` を付けると、指定 backend に対してエンジン更新候補を確認します。実際に更新する場合は `--check` を外します。

## 値と既定値

- `--backend` は文字列引数で、既定値は `None`（未指定）です。`choices`、型変換、独自の値検証は parser にありません（`strata_cli/update_cmd.py:30-40`）。
- 未指定なら `updater.detect_hardware()` が `STRATA_ENGINE_BACKEND` またはプラットフォーム・GPU 検出に基づく backend を使います。CLI に空文字列を渡した場合も `if a.backend` が偽になるため、CLI 指定による上書きは行われません（`strata_cli/update_cmd.py:174-180`、`strata_control/updater.py:249-270`）。
- 実装上の backend family は `metal`、`cuda`、`hip`、`sycl`、`cpu` です（`strata_control/targets.py:20-29`）。feed にその backend と現在の platform の組み合わせがなければ、その組み合わせのエンジン候補は選ばれません。
- 指定値は正規化されず、そのまま backend として照合されます。未知の値や大文字小文字の異なる値も parser では拒否されず、feed package と一致しなければエンジンは `none-for-this-pc` になります（`strata_cli/update_cmd.py:177-179`、`strata_control/feed.py:372-395`、`strata_control/updater.py:566-590`）。

## 実行時の動作

`run()` はまず検出済み hardware を作り、指定値が truthy の場合に `hardware["backend"]` を置き換え、出所を `requested` と記録します。その値は `Context` を通って `_choose_engine()` と `feed.select_engine()` に渡され、feed のエンジン package の platform・backend・対応 GPU architecture・必要な driver/runtime との照合に使われます（`strata_cli/update_cmd.py:174-184`、`strata_control/updater.py:566-590`、`strata_control/feed.py:372-416`）。

上書きされるのは backend と出所で、検出時に収集した GPU architecture・driver 情報は再取得されません。architecture/driver の適合確認は、それらの検出情報が存在するときだけ行われます（`strata_control/updater.py:249-270`、`strata_control/feed.py:387-394`）。

明示指定は、検出 backend とインストール済みエンジンの GPU make が異なる場合に通常働く `make_guard()` を通過させます。別 make の GPU を搭載した PC では、指定値に対応するエンジンを選択・更新対象にできるため、指定値が実機に適合することを利用者が確認してください（`strata_control/updater.py:539-563`）。

`--backend` は Control や desktop app の platform 別更新を切り替えません。`--no-engine` を併用するとエンジン更新工程自体が省略されますが、Control は通常どおり更新され、`--app` を付けた場合は app の installer も処理されます（`strata_cli/update_cmd.py:45-56`、`strata_control/updater.py:1274-1297`）。`--check` の場合は候補を報告します。check は feed 以外の package をダウンロードしませんが、確認結果を `last_check` として component state に保存します（`strata_cli/update_cmd.py:203-209`、`strata_control/updater.py:624-640`）。

## 適用条件と副作用

- backend の指定が有効なのはエンジン package の選択・適合判定です。backend と OS platform が一致しない、または選択値に合う package が feed にない場合は、エンジンを変更せず `none-for-this-pc` と理由を返します（`strata_control/feed.py:372-416`、`strata_control/updater.py:581-590`、`strata_control/updater.py:926-937`）。
- 明示値は検出結果を上書きし、GPU make guard を通過させます。選んだ package の試験起動が失敗した場合、エンジン切替は行われず、更新失敗として扱われます。したがって、backend 名の指定だけでその backend の GPU が実機にあることや、package が動作することは検証されません（`strata_control/updater.py:539-563`、`strata_control/updater.py:926-941`、`strata_control/updater.py:953-976`）。
- 実際に更新するときは feed を読み、エンジン・Control・指定時の app の更新処理に進みます。エンジン候補のダウンロード、検証、試験起動、切替を伴うのは選択された更新 package がある場合です（`strata_cli/update_cmd.py:197-224`、`strata_control/updater.py:1274-1297`）。

## 出力とエラー

- `--check` は human 出力で選択された package を `selected for this PC` として表示し、選択できない場合は status と理由を表示します。JSON/JSONL 系出力では report が JSON として返ります（`strata_cli/update_cmd.py:132-160`、`strata_cli/update_cmd.py:203-209`）。
- 通常更新で候補がない場合は engine の状態と理由を結果に含めます。これは parser validation error ではありません（`strata_control/updater.py:926-937`、`strata_cli/update_cmd.py:213-224`）。
- 更新中に `UpdateError`、feed error、署名エラー、取得拒否が起きた場合は、human 出力では `stderr` に `strata: ...`、machine 出力では error JSON を出し、該当 exit code を返します（`strata_cli/update_cmd.py:163-172`、`strata_cli/update_cmd.py:225-234`）。

## 根拠

- parser と `strata update` との共有: `strata_cli/update_cmd.py:30-59`
- CLI 値の適用と更新 context: `strata_cli/update_cmd.py:163-184`
- backend 自動検出と環境変数: `strata_control/updater.py:249-270`、`strata_control/engine_component.py:439-460`
- 候補適合・選択: `strata_control/feed.py:372-416`
- GPU make guard と明示指定の扱い: `strata_control/updater.py:539-563`
- check と state 保存: `strata_control/updater.py:624-640`
- engine update の未選択・失敗・切替経路: `strata_control/updater.py:926-976`
- 更新工程と出力・例外経路: `strata_control/updater.py:1274-1297`、`strata_cli/update_cmd.py:203-234`

調査は上記 commit の checkout にあるソースに限定しました。CLI `--help`、Release 配布物、各 OS/backend 実機での動作は確認していません。
