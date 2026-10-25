# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

成功時の人間向け出力を抑え、終了コードで検証結果を扱う場合に使います。`--quiet` は表示を制御するだけで、runtime の確認や API probe を省略しません。

## 使い方

```sh
strata runtime verify --profile PROFILE_NAME --quiet
```

JSON 結果を取得する場合は、`--quiet` と併せて `--output json`（または `--json`）を指定します。

```sh
strata runtime verify --profile PROFILE_NAME --quiet --output json
```

## 値と既定値

値を取らない `store_true` フラグです。省略時は quiet ではありません。同じ `runtime verify` parser には個別宣言されず、`runtime_verify` を含む one-shot parser 群へ共通に追加されます。値を付ける形式はありません（`strata_cli/cli.py:216-225,508-515`）。

## 実行時の動作

`main()` は `--quiet` が有効で `output` が `human` の場合、`_run()` の間だけ stdout を最大 64 KiB の捕捉先へ向けます。`runtime verify` は例外扱いのコマンド一覧に含まれないため、人間向け stdout は成功時に破棄され、非ゼロ終了時には捕捉内容が stderr に再出力されます。捕捉量が上限を超えた場合は、末尾の内容に加えて省略通知も stderr に出ます（`strata_cli/cli.py:2196-2214,2236-2248`）。

`runtime verify --plan` の既定 human 出力は整形 JSON ですが、`--quiet` では成功時にこれも抑制されます。plan の結果が失敗なら、捕捉した human 出力は stderr に戻ります（`strata_cli/cli.py:1357-1373,2241-2248`）。

`--output json` または `--json` では `output=json` が quiet 判定より先に確定し、捕捉経路に入らないため、JSON は stdout に出力されます（`strata_cli/cli.py:2232-2237,1357-1373`）。

quiet の有無にかかわらず、通常の verify は `management.runtime_action()` から `runtime.verify()` に進みます。verify は処理結果を `runtime.verify` operation として journal に記録し、ready な owned instance に対する検証を行います。検証では API telemetry を照会し、モデルがロード済みなら最大1 token の生成 probe を送ります。未ロードモデルは通常ロードせず、`--load` 併用時はロードを伴う生成 probe を行います。`--quiet` はこの処理に渡されるオプションではありません（`strata_cli/cli.py:1345-1356`、`strata_control/management.py:255-270`、`strata_control/runtime.py:687-699,1172-1208`、`strata_control/readiness.py:101-143`）。

## 適用条件と副作用

- この `--quiet` は `runtime verify` の one-shot parser に適用されます。サーバーが ready でない場合や probe が失敗した場合も、verify の失敗自体は抑止されず、終了コードが返ります。
- `--quiet` 単独では runtime を起動・停止しません。ただし通常の verify は runtime host への制御要求、telemetry の HTTP GET、ロード済みモデルへの生成 HTTP POST を行い、結果を journal に記録します。未ロード状態で `--load` を付けるとモデルロードも起こり得ます。
- `--plan` は verify そのものを実行せず、現在の runtime 状態と計画を返します。quiet はこの plan 出力だけを抑制し、状態確認は行われます（`strata_control/management.py:239-254`）。
- `--output json` / `--json` との併用時には JSON を抑制しません。

## 出力とエラー

- human 出力の成功時: stdout の出力を破棄します。
- human 出力の失敗時: `_runtime()` が stdout に書いた結果表示は stderr に再出力されます。stderr に直接出るエラーやエンジンログ案内は quiet の stdout 捕捉対象外です（`strata_cli/cli.py:1362-1373,527-532,2241-2248`）。
- JSON 出力時: `--quiet` を指定しても JSON は stdout に出ます。結果が失敗なら JSON の `ok` / `exit_code` 等と非ゼロ終了コードで伝えます（`strata_cli/cli.py:1359-1373`）。
- 必須の `--profile` 欠落や不正な引数は parser 段階で拒否され、usage とエラーが stderr に出ます。`--quiet` は引数解析前のエラーを抑止しません（`strata_cli/cli.py:216-225,2223-2231`）。

## 根拠

- `strata_cli/cli.py:216-225` — `runtime verify` 固有の parser 引数。`--quiet` はここには宣言されません。
- `strata_cli/cli.py:508-515` — one-shot parser 群に対する `--json` / `--quiet` の追加。
- `strata_cli/cli.py:1331-1373` — verify の実行委譲、人間向け・JSON 出力、plan 経路と終了コード。
- `strata_cli/cli.py:2196-2214,2223-2248` — 捕捉上限、引数解析後の quiet 判定、JSON の例外、失敗時の stderr 再出力。
- `strata_control/management.py:235-270` — verify の plan / 実行分岐と operation journal への記録。
- `strata_control/runtime.py:687-699,1172-1208` — verify の待ち時間・ID 検証と runtime host 側の状態確認・検証。
- `strata_control/readiness.py:101-143` — telemetry GET、未ロード時の分岐、最大1 token の生成 probe。

調査範囲は指定 revision の checkout 内にある Terminal CLI、Control、readiness の Python 実装です。同一 revision の CLI help、Release 配布物、各 OS での実行結果は確認していません。
