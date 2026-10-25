# `--no-engine`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update`（同じ parser 動作を `strata update` も持つ） |
| オプション | `--no-engine` |
| 別名 | なし |
| 値 | 取らないフラグ。省略時は `false`、指定時は `true` |

## 役割

更新処理から推論エンジンの更新だけを省きます。Control の更新は既定で残り、`--app` を併用すれば Desktop アプリのインストーラー取得・検証も行えます。エンジンを更新せず Control だけを更新する場合などに使えます。

## 使い方

```sh
strata components update --no-engine
```

Control も更新対象から外す場合は `--no-control` を併用します。Desktop アプリのインストーラーも取得する場合は `--app` を併用します。

```sh
strata components update --no-engine --no-control --app
```

## 値と既定値

値を取りません。parser は `action="store_true"` で定義しており、省略時は偽、指定時は真になります。繰り返し指定を拒否する独自 validation はありません。値を後置すると別の引数として解析され、受理可能な位置引数でなければ argparse の usage エラーになります。

## 実行時の動作

- 通常実行では `--no-engine` の真偽を反転して `run_update(..., engine=...)` に渡します。`engine=False` のとき、更新手順の engine 項目は作られず、engine の選択、取得、検証、切り替え、旧 engine の整理を行う `update_engine` は呼ばれません。
- Control は `--no-control` を付けない限り既定で更新対象です。`--app` を付けた場合はアプリ項目も処理対象になります。`--no-engine` 単独ではこれらを無効にしません。
- engine を省いても、通常の更新処理は update lock を取り、署名付き feed を読み、feed の確認状態を保存します。したがって、このフラグはオフライン化や feed 確認の省略を意味しません。
- `--check` と併用した場合、実行経路は `run_update` ではなく `updater.check` です。この経路は engine / Control / app の更新見込みをすべて作るため、`--no-engine` は engine の見込み表示を抑止しません。check は feed 以外をダウンロードしませんが、`last_check` を保存します。
- `--wait` の指定がない対話端末では、engine が稼働中だと更新前に待機確認が出る場合があります。`--no-engine` でもこの事前確認関数は呼ばれます。一方、`--wait` による実際の稼働終了待ちは engine 更新関数内にあるため、engine を省いた場合、Control / app の処理自体はその待機処理を通りません。

## 適用条件と副作用

`strata update` と `strata components update` の両方に同じフラグが定義されます。索引上の本書は後者のコマンド階層に配置されています。

フラグ単独では engine のファイルや engine 更新履歴を変更しません。ただし、feed の取得・状態記録は行われ、既定の Control 更新や明示した `--app` によるインストーラーの取得・保存は別途発生し得ます。`--no-control` も指定し、`--app` も指定しない通常実行では、feed の読込・保存を行った後、コンポーネント更新ステップなしで正常終了し得ます。

## 出力とエラー

通常の人間向け出力では `run_update` が返した結果ごとに行を表示するため、engine の結果行は出ず、実行された Control / app の結果が表示されます。`--output json` / `jsonl` では同じく engine 結果項目がありません。

`--no-engine` は署名確認、feed 読込、取得禁止 (`STRATA_NO_ACQUIRE`) などの共通前提を回避しません。これらの失敗は共通エラー経路で報告されます。省略していない Control / app の処理が失敗した場合も結果に失敗を記録し、そのエラーコードを全体の終了コードにします。更新コマンドの実装コメントには一般的な終了コードとして、拒否 `5`、更新失敗 `6`、稼働中 engine による拒否 `7`、中断 `130` が記載されています。ただし `7` は engine 更新時の稼働チェックに対応し、`--no-engine` では engine 更新関数が呼ばれないため、このフラグの実行経路では通常該当しません。

## 根拠

- `strata_cli/update_cmd.py:42-59` — `strata update` と `strata components update` の parser 定義。両方で `--no-engine` は値なしの `store_true`。
- `strata_cli/update_cmd.py:163-184,197-224` — hardware / context の準備、取得禁止確認、`--check` 分岐、通常実行で `engine=not a.no_engine` として渡す処理、出力と終了コード。
- `strata_cli/update_cmd.py:237-252` — 稼働中 engine に対する待機確認。通常更新の前にフラグによらず呼ばれる。
- `strata_control/updater.py:624-640` — `check` が engine / Control / app の判定を作り、`last_check` を保存する処理。
- `strata_control/updater.py:1274-1297` — `engine` / `control` / `app` の各更新ステップを条件付きで組み立て、feed と状態を保存する処理。
- `strata_control/updater.py:926-946,978-979` — `update_engine` の実体と、稼働中 engine を待つ処理。`engine=False` ならこの関数に到達しない。
- `strata_cli/update_cmd.py:1-11,225-234` — 更新の説明および共通の失敗報告・終了コード。
- `docs/cli/README.md` — `strata components update` 配下に本オプションのリンクがあることを確認。索引自体は変更していない。

調査は指定 revision のソースを対象としました。別途インストール済み CLI の `--help` や Release 配布物との照合は行っていません。
