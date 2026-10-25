# `strata tune auto`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| 実装 | `strata_cli/tune_commands.py`、`strata_control/autotune.py`、`strata_control/tune_session.py` |
| 対象 | 保存済み profile または run configuration（JSON）を使った自動チューニング |

## 役割

指定した構成で実際の Strata worker と推論エンジンを起動し、現在の設定を基準に候補設定を測定します。ノイズを上回る性能向上が確認された場合は、設定を名前付き tuning preset として保存し、既定ではその preset を有効化します。測定結果はモデル・構成・マシンの情報と対応付けられます。性能差が確認できなければ、現在の設定を変更せずに終了します。

この `auto` は、`strata tune plan` / `strata tune run` / `strata tune apply` の bounded sweep・レビュー経路とは別の実装です。オプション一覧は [`docs/cli/README.md`](../../../README.md) の `strata tune auto` 節を参照してください。

## 使い方

```sh
# 保存済み profile を既定の quick モードで測定
strata tune auto "My profile"

# run configuration を使い、より長い thorough モードで測定
strata tune auto ./run-config.json --mode thorough

# 測定結果は出すが preset を保存しない
strata tune auto "My profile" --no-save
```

`target` は保存済み profile 名または run configuration（JSON）です。JSON 設定を渡す例では、現在の作業ディレクトリから `./run-config.json` にアクセスできることが前提です。

## 実行モードと測定

| モード | 動作 |
| --- | --- |
| `quick`（既定） | 既定予算は約20分。基準設定と候補を交互に測定し、予算内で試す候補を選びます。 |
| `thorough` | 既定予算は最大約2時間。候補を測定し、採用候補を5組の比較で確認します。 |
| `--time MINUTES` | 実行予算を分単位で指定します。候補数・測定回数は利用可能な予算にも左右されます。 |

比較は現在の構成を基準にした一つずつの設定変更です。候補は測定した基準との比率がノイズ由来の差を超え、比較ラウンドで十分に勝ち、prompt 速度を大きく落とさない場合に採用候補になります。測定できる設定は backend、engine が対応するフラグ、マシン状態などに応じて変わります。

`--goal` と `--leave-ram` は速度だけでなく空けておくメモリーの希望を測定条件に反映します。`--use coding` は長い prompt の速度も評価します。回答がわずかに変わり得る設定や、回答が再現しない設定は、それぞれ `--allow-small-differences`、`--allow-not-repeatable` を付けた場合に候補へ含めます。

## 主な動作と副作用

- 候補ごとに run configuration のコピーを作成し、`serve.server` worker を localhost の一時 port で起動して測定します。worker にはランダムな API key を設定し、測定終了時に停止します。元の設定ファイルを候補ごとに書き換える処理ではありません。
- 作業ディレクトリを省略すると `strata-tune-` で始まる一時ディレクトリを作成し、run config と engine / worker log を保存します。`--work-dir` を指定した場合はそのディレクトリを使用します。
- 既定では候補測定中の別エンジン・CPU 負荷を確認し、必要に応じて待機します。共有 GPU 環境で `--gpu-lock` を指定すると、各 engine run の間その lock file を保持します。`--no-quiet-check` は静穏状態の確認を無効にします。
- 完了時には試行履歴を preset store に記録します。結果が `improved` または `default_confirmed` で、かつ `--no-save` がない場合、preset を作成して既定で有効化します。したがって「改善なし」の確認結果でも、設定上の選択を記録する preset が作られる場合があります。
- `--status-file` を指定すると、進捗 JSON を各段階で一時ファイル経由の置換により更新します。`--output json` は最終結果を JSON として stdout に出力します。通常の human 出力では進捗を stderr、最終結果を stdout に出します。
- 起動済みの通常サーバーをこのコマンド自身が停止する処理はありません。ただし `strata launch` が自動チューニングを呼び出す場合は、launch が自分のサーバーを停止してから測定し、結果に応じて再起動する経路があります（[`strata launch` 概要](../../launch/README.md)）。

## 注意点と失敗

- 通常は数十分かかり、`thorough` は最大約2時間を既定予算とするため、時間と CPU・メモリー・GPU を使います。測定中はエンジンを繰り返し起動し、固定の chat / prompt 要求を localhost worker に送信します。
- 基準設定で測定できない場合、engine が見つからない場合、profile / JSON の解決に失敗した場合などはエラーになります。利用可能なメモリーが少ない場合や、マシンが測定中に変動した場合は候補をスキップまたは比較不能とし、変更しないことがあります。
- `--leave-ram` は整数 0〜50 の範囲です。範囲外は終了コード 2 のエラーです。`--goal` は `speed` / `full` / `room` / `room:MiB` を受理し、他の形式は値エラーになります。`room:MiB` の MiB 部分は整数として解析されます。
- 通常の入力・engine 不在エラーは human 出力では `strata: ...` を stderr に出します。JSON 出力では `ok: false` と error を stdout に出します。チューニング結果が正常に返った場合の終了コードは、改善または既定設定確認で 0、キャンセルで 130、それ以外の結果で 6 です。
- `--boot-timeout` は各 worker 起動の準備待ち時間（秒）で、parser の既定値は 900 秒です。起動できない・応答しない engine は測定失敗として扱われます。

## 関連文書

- [`strata tune` 概要](../README.md)
- [`strata tune plan` 概要](../plan/README.md)
- [`strata tune run` 概要](../run/README.md)
- [`strata tune apply` 概要](../apply/README.md)
- [`strata launch` 概要](../../launch/README.md)
- [`CLI オプション索引`](../../../README.md)

## 根拠

- Strata `strata_cli/cli.py:486,1652-1653` — `auto` の登録と dispatcher からの呼び出し。
- Strata `strata_cli/tune_commands.py:20-47` — target、オプション、既定値の parser 定義。
- Strata `strata_cli/tune_commands.py:111-115,139-147,174-200` — target 解決、goal と `--leave-ram` の検証、engine・backend・測定 options の決定。
- Strata `strata_cli/tune_commands.py:202-260` — 進捗通知、workdir、試行履歴、preset 保存、human / JSON 出力、終了コード。
- Strata `strata_control/autotune.py:50-76,160-175,379-430,630-648` — mode ごとの予算・ラウンド、採用判定、測定と結果の分類。
- Strata `strata_control/tune_session.py:420-480,489-521` — worker 用 config / log 作成、localhost worker 起動と終了。
- Strata `strata_control/presets.py:268-307` — preset の作成・保存・有効化。
- Strata `strata_cli/launch/runner.py:1325-1361,1396-1415` — launch からの呼び出し、起動済みの同一 profile server 停止。
