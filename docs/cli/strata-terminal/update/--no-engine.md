# `strata update --no-engine`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--no-engine` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時は真になる |

## 役割

署名済み feed を使う `strata update` の更新対象からエンジンを外す。通常の更新経路でエンジンを更新せず、Control は既定どおり更新対象に残る。`--app` も指定した場合はアプリのインストーラー取得・検証も別途行われる。エンジンを更新せず Control だけを更新したいときなどに使う。

## 使い方

```sh
# エンジンを除外して、Control の更新を行う
strata update --no-engine

# エンジンを除外したときの更新候補を確認する（この場合も --no-engine は候補表示を絞らない）
strata update --no-engine --check
```

## 値と既定値

`argparse` の `store_true` フラグで、値は不要。省略時は偽でエンジンを含む通常の更新経路になり、指定時は真になる。同じフラグを複数回指定しても真のままで、値の変換や追加の範囲 validation はない（`terminal/strata_cli/update_cmd.py:59-66`）。

## 実行時の動作

`strata update` の実行分岐は `a.no_engine` を反転して更新処理へ渡す（`terminal/strata_cli/update_cmd.py:370-372`）。更新処理ではエンジン更新ステップを作らず、モデル形状別エンジンの更新ステップも作らない。一方、Control は `--no-control` がない限り更新ステップに残り、`--app` があればアプリ更新も行う（`terminal/strata_control/updater.py:2099-2106,2109-2122`）。そのため、このオプション単独では「更新全体を無効化」したり「Control も除外」したりしない。

更新前の稼働モデル確認は、選択された更新対象の候補がある場合に行われる。エンジンを除外すると、エンジンのみが候補だった場合はそのエンジン更新を理由にモデル停止を求めないが、Control など他の選択対象に更新があれば確認経路は残る（`terminal/strata_control/updater.py:2066-2079,2082-2096`）。

`--check` は通常更新処理より先に分岐し、`updater.check(ctx)` の全コンポーネントの判定を表示する。この経路では `a.no_engine` を参照しないため、`strata update --no-engine --check` でもエンジン候補自体は表示対象である（`terminal/strata_cli/update_cmd.py:361-367`、`terminal/strata_control/updater.py:778-789`）。通常更新では feed を読み、状態を保存してから、選択された更新ステップを順に実行する（`terminal/strata_control/updater.py:2112-2122`）。

## 適用条件と副作用

- 通常更新では feed の読み込みと更新状態の保存が行われ、Control はこのフラグだけでは除外されない。ネットワーク取得は `strata update` の明示的な更新処理による（`terminal/strata_control/updater.py:2112-2122`）。
- 更新完了時の `last_check` 再計算では、エンジンの候補も引き続き調べて状態に保存する。したがって、更新ステップを省いてもエンジン更新候補の記録まで消すわけではない（`terminal/strata_control/updater.py:2130-2137,792-800`）。
- `--check` と併用した場合は更新を行わず、feed に基づく全コンポーネントの確認結果を返す。確認処理も `last_check` を状態へ保存する（`terminal/strata_cli/update_cmd.py:361-367`、`terminal/strata_control/updater.py:778-789`）。

## 出力とエラー

通常の人向け出力では更新開始時に feed の出所を表示し、完了後に実行されたコンポーネントの結果を表示する。`--output json` / `jsonl` はこのオプションと独立しており、JSON 系では結果を機械可読形式で出力する（`terminal/strata_cli/update_cmd.py:368-377`、`terminal/strata_cli/update_cmd.py:117-139`）。エンジン処理が省かれるため、その実行結果項目は作られない。Control など実行対象の失敗は通常の更新失敗として結果に記録され、最初の失敗の終了コードが返る（`terminal/strata_control/updater.py:2123-2138`）。

feed、署名、取得禁止、割り込みなどの失敗は共通の更新エラー経路で報告される。`STRATA_NO_ACQUIRE` による拒否は終了コード 5、割り込みは 130 として扱われる（`terminal/strata_cli/update_cmd.py:355-390`）。これらは `--no-engine` 固有の validation ではない。

## 根拠

- `terminal/strata_cli/update_cmd.py:59-79` — `strata update` と `strata components update` の parser。両方に同じ `store_true` オプションが登録されている。本文書は索引上の `strata update` スコープを扱う。
- `terminal/strata_cli/update_cmd.py:361-377` — `--check` の先行分岐と、通常更新へ `engine=not a.no_engine` を渡す箇所。
- `terminal/strata_control/updater.py:2066-2096,2099-2122` — 選択対象によるモデル確認、エンジン・形状別エンジン・Control・アプリの更新ステップ構成。
- `terminal/strata_control/updater.py:778-789,2130-2138` — 確認時と更新後の feed 判定・状態保存。
