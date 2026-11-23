# `--batch-groups`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--batch-groups` |
| 別名 | なし |
| 値 | `auto` または 1〜1024 の正の10進整数 |

## 役割

layer split したエンジンで batch slot を複数の group に分け、各 GPU stage に別 group の処理を重ねて流す数を指定します。`1` は全 slot を一つの group にまとめ、group 間の pipeline を使いません。値は `strata serve` が起動するエンジンに渡されます。

## 使い方

```sh
# エンジンが slot 数と layer split に応じて group 数を決める計画を表示する
strata serve --profile /path/to/run.json --batch-groups auto --plan

# 4 group を要求して既存の推論サーバーを起動する
strata serve --profile /path/to/run.json --batch-groups 4

# group pipeline を使わず、一つの serial group にする
strata serve --profile /path/to/run.json --batch-groups 1
```

## 値と既定値

- `auto` はエンジンに group 数の決定を任せます。layer split があり batch slot が2以上なら、stage 数を超えず slot 数を割り切る最大の group 数が選ばれます。layer split がない場合は1 groupです（`engine/include/strata/program/batch_groups.hpp:113-120,122-137`）。
- 整数は1〜1024です。`1` は pipeline を無効にします。2以上は layer split があり、slot 数を割り切れる場合に pipeline の要求として使われます。
- このオプションを省略した場合、engine config 内の設定があればそれが使われます。設定がなければ、layer split かつ batch slot が2以上のとき engine が `auto` 相当を選びます。それ以外は1 groupです。`--adapt-async 1` などの条件で、省略時の自動選択が1 groupになる場合があります（`engine/include/strata/program/batch_groups.hpp:126-145`）。
- `strata serve` の parser は値を文字列で受け、実行前に `auto` または10進数字かを確認してから1〜1024の範囲を検証します。`02` のような10進表記も受理されます（`terminal/strata_cli/cli.py:75,970-974`; `terminal/strata_control/profiles.py:98-117`）。

## 実行時の動作

指定値は起動時の server 引数に渡され、server がメモリ上の engine config `args` に追加してエンジンを起動します。plan でも同じ有効 engine 引数を組み立てます。元の run config ファイルはこの処理では書き換えません。CLI 引数または保存済み profile に値があるとき、run config の `args` にすでに `--batch-groups` がある場合は競合として拒否されます。run config 内の既存値を使う場合は、この CLI オプションを省略してください（`terminal/strata_cli/cli.py:783-818,821-864`; `terminal/serve/server.py:8789-8796`）。

エンジンでは `--batch-groups` を数値または `auto` として読み、実行 slot 数・layer split の stage 数・`--batch-mtp` などの状態と合わせて解決します（`engine/src/program/generate.cpp:1016-1025,4035-4045,7732-7749`; `engine/include/strata/program/batch_groups.hpp:122-145`）。2以上の group が有効なら各 group の slot 数を `batch / groups` とし、複数 stage に処理を重ねる pipeline を実行します（`engine/src/program/generate.cpp:17423-17427`）。

engine config に `--batch`（または同等の slot 数）がある構成で、指定 group 数が slot 数を割り切れない場合や layer split がない場合、エンジンは stderr に警告を出し、1 group に戻して続行します。slot 数自体が実行可能数へ縮小されることもあり、その後の group 解決と妥当性確認は調整後の値に対して行われます（`engine/src/program/generate.cpp:7866-7897,7904-7928`）。

## 適用条件と副作用

- 複数 group の pipeline は `--serve`、2以上の batch slot、各 stage が別 GPU にある layer split を必要とします。複数 group の engine 経路は `batch > 0`、group 数が2以上、layer split の stage が存在する場合に選択されます（`engine/src/program/generate.cpp:7883-7890,17423-17427`）。
- `--batch-mtp` との併用では、通常の pipeline は slot ごとの MTP draft を実行しません。pipeline が選ばれ draft が実行されない場合、engine は stderr に警告を出します。`--batch-groups 1` なら serial windows のままです。特定条件で pipeline 側も draft を使う実装はありますが、適用可否は engine の設定・行数条件に依存します（`engine/src/program/generate.cpp:7724-7731,17428-17441`; `engine/include/strata/program/batch_groups.hpp:139-145`）。
- `--adapt-async 1` は serial windows を前提とするため、オプションを省略したときの自動 group 選択は1 groupになります。一方、明示した数値または `auto` は group 要求として処理され、pipelined path は `--adapt-async` の適応 tier を実行しません（`engine/include/strata/program/batch_groups.hpp:126-145`; `engine/src/program/generate.cpp:7728-7749,15148-15160`）。
- `strata serve --plan` と組み合わせると、effective engine arguments を含む計画を出力するだけでサーバーを起動しません（`terminal/strata_cli/cli.py:979-980,850-864`）。

## 出力とエラー

- `auto` 以外の非10進値、0、または1024超は `strata serve` の入力検証で拒否され、通常の CLI エラー経路になります（`terminal/strata_cli/cli.py:970-978,2194-2255`; `terminal/strata_control/profiles.py:113-114`）。オプション自体は省略できます。
- run config に engine `args` がなくオプションを適用できない場合、または CLI/profile の指定と run config の同名 engine argument が競合する場合は拒否されます（`terminal/strata_cli/cli.py:810-818`; `terminal/serve/server.py:8792-8796`）。
- layer split がない、または group 数が slot 数を割り切れない場合はエンジンが警告して1 groupで続行します。`auto` の選択結果はエンジンの stderr に group 数と各 group の slot 数として出力されます（`engine/src/program/generate.cpp:7904-7928`）。

## 根拠

- `terminal/strata_cli/cli.py:67-88` — `strata serve` parser と `--batch-groups` の宣言。
- `terminal/strata_cli/cli.py:783-818,821-864,970-980` — CLI/profile/config の優先・競合、エンジン引数への追加、入力検証、plan-only 経路。
- `terminal/strata_control/profiles.py:98-117` — batch group 値の型と範囲検証。
- `engine/src/program/generate.cpp:1016-1025,4035-4045,7728-7749,7866-7928,17423-17441` — engine parser、値の解決、slot 条件、警告、pipeline と MTP の処理。
- `engine/include/strata/program/batch_groups.hpp:113-145` — `auto` の算出と省略時の既定・相互作用。
- `terminal/serve/server.py:960-982,2490-2514` — engine が報告する実 group 数を読み、server の slot 配置・要求配分に反映する処理。
