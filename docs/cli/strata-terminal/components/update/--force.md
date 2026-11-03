# `--force`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。調査時の Strata checkout は `main` が `origin/main` と一致し、作業ツリーは clean。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らない boolean flag。省略時 `False`、指定時 `True`。 |

## 役割

エンジン更新で、同じ feed 上のエンジンが以前の test start に失敗したため再試行対象から除外されている場合に、その除外を越えて再試行します。コマンドの説明にある通常の test start と切り替えの手順は引き続き適用されます。

## 使い方

```sh
strata components update --force
```

これは更新を実行します。feed を読むだけの確認には `--check` を使いますが、`--force --check` は実際の更新を行わず、状態の表示だけです。

## 値と既定値

`argparse` の `action="store_true"` で宣言されており、値を指定しません。未指定では無効、指定すると有効です。`--force=true` のように値を付ける形式は parser の定義にありません。

## 実行時の動作

- `strata components update` と `strata update` は共通 parser helper `_common()` から `--force` を受け取り、実行時に `Context.force` へ渡します（`strata_cli/update_cmd.py:47-56,70-79,244-256`）。
- feed が提示するエンジンがインストール済み版より新しく、同一 version と manifest hash の失敗記録があり、その記録が24時間以内の場合、通常は engine status を `failed-before` にして再試行を抑止します。`--force` がある場合はこの抑止を適用せず、通常の `available` として更新候補にします。失敗記録は version ごとに保持され、24時間を超えると `--force` なしでも古い記録として無視されます（`strata_control/updater.py:619-642,1434-1440`）。
- update 処理では `failed-before` と `skipped` を force 時の実行可能 status に含めます。ただし、この revision の `_choose_engine()` は `skipped` status を返さず、確認した現行経路で `--force` が解除するのは `failed-before` 抑止です。通常の feed 選択や GPU/backend 適合判定を置き換えるものではありません（`strata_control/updater.py:590-642,1098-1118`）。
- 適合する engine package は引き続き取得・検証・test start され、成功後に切り替わります。test start が失敗したときは旧 engine を維持し、busy 起因でない失敗は version・manifest hash・理由・時刻を記録します。成功時にはその version の failure 記録を消します（`strata_control/updater.py:1164-1175,1209-1224`）。
- `--check` は `updater.check()` を呼びます。force は状態判定に渡りますが、この経路は feed を読んで報告・cache 保存するだけで package のダウンロードや更新をしません（`strata_cli/update_cmd.py:290-296`、`strata_control/updater.py:663-674`）。

## 適用条件と副作用

このフラグが主に変えるのは Terminal CLI の engine 更新判定です。Control 更新、DeepSeek engine 判定、app installer の失敗抑止を解除する処理は確認できません。`--no-engine` を併用した場合は engine 更新自体が無効です（`strata_cli/update_cmd.py:65-79,299-301`、`strata_control/updater.py:1677-1693`）。

署名・hash・PC との package 適合性の検証、および test start を飛ばす機能ではありません。force があっても取得や検証に失敗すれば通常の失敗経路になります（`strata_control/updater.py:1114-1124,1164-1175`）。実際の更新ではネットワーク取得、stage 作成、engine の切替が発生し得ます。読み取り確認だけなら `--check` を使います。

## 出力とエラー

再試行対象の更新が失敗した場合、通常の update 結果またはエラー経路で失敗が報告されます。test start の失敗では、engine log は `.updates/logs/test-start-<version>.log` に保存され、busy でない失敗の案内は再試行に `strata update --force` を提示します（`strata_control/updater.py:933-955`）。CLI の機械可読出力では `--output json` / `jsonl` により event・error の形式が変わります（`strata_cli/update_cmd.py:98-120,237-242`）。

## 根拠

- parser 宣言と両 update command への適用: `strata_cli/update_cmd.py:47-79`
- parser flag から Context への伝達、`--check` と更新の分岐: `strata_cli/update_cmd.py:233-256,284-306`
- 失敗記録による抑止、manifest hash と24時間期限: `strata_control/updater.py:619-642,1434-1440`
- force 時に許可される engine status と更新開始: `strata_control/updater.py:1098-1118`
- test start 失敗の記録、成功時の記録削除: `strata_control/updater.py:1164-1175,1209-1224`
- check が更新を実行しないこと、pending change における force 判定: `strata_control/updater.py:663-674,1677-1693`
- test start の案内と log path: `strata_control/updater.py:933-955`
