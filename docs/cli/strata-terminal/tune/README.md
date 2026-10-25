# `strata tune`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune` |
| 主な実装 | `strata_cli/cli.py`、`strata_cli/tune_commands.py`、`strata_control/tuning.py`、`strata_control/tune_apply.py` |

## 役割

エンジンの実行設定を候補ごとに測定し、結果を後から確認できる形で保存する tuning CLI です。モデルの学習や重みの変更ではなく、エンジン起動設定を探索します。サブコマンドは必須です（`strata_cli/cli.py:395-397`、`strata_control/tuning.py:1-5`）。

この階層には二つの使い方があります。`plan` / `run` はエンジン設定の bounded sweep を計画・計測し、`apply` はレビューした sweep の推薦を run config に反映します。`auto` は既存の profile または run config を実機で自動測定し、条件を満たす結果を起動時に使う tuning preset として保存します。これらは同じ `strata tune` 配下ですが、別の処理経路です（`strata_cli/cli.py:398-486`、`strata_cli/tune_commands.py:20-46,174-261`）。

## 代表的な使い方

```sh
# 対象 backend / engine が探索できる設定と、除外理由を確認
strata tune plan --engine ./build/strata --backend cuda --model my-model

# 候補 sweep を実行し、レポートを確認
strata tune run --engine ./build/strata --backend cuda --model my-model \
  --model-path ./model.gguf
strata tune status <job-id>

# 測定したい profile/config を自動 tuning して preset を保存
strata tune auto "./strata-my-model.json"
```

`plan` と `run` では `--engine`、`--backend`、`--model` が必須です。例の `my-model`、engine path、GGUF path は利用環境の実ファイル・識別子に置き換えてください（`strata_cli/cli.py:398-459`）。

## 実行モード

| サブコマンド | 動作 |
| --- | --- |
| `plan` | engine の help から取得した option inventory と backend を照合し、探索次元・除外理由・試行上限を表示します。計測は行いません。 |
| `run` | 基準値と候補値を bounded sweep で測定し、job/report を保存します。`--mode protocol` は既定でエンジン自身の serve protocol を測定し、`--mode api` は worker の HTTP API 経由で測定します。 |
| `apply <job-id>` | 完了した sweep の推薦を確認し、対象 run config のエンジン引数を更新します。明示的な別ステップです。 |
| `rollback <application-id>` | apply 前に退避した run config を復元します。apply 後に対象ファイルが編集されていれば、変更を失わないよう拒否します。 |
| `status <job-id>` / `list` | 保存済み job の状態・レポート、または job の一覧を表示します。 |
| `auto <target>` | 実機で現在設定と候補を測定し、改善または既定設定の確認が成立した場合、`--no-save` がなければ tuning preset を保存します。 |

parser の既定は `plan` / `run` とも objective=`generation`、trials=16、時間上限表示=1800秒、repeats=3 です。`run` の workload は prompt 512 tokens、生成上限128 tokens、mode=`protocol`。`api` mode には `--config` と `--api-expect` が必須です（`strata_cli/cli.py:403-459,1770-1786`）。

## 主な動作と副作用

- `plan` は engine の `--help` を実行して option を読み取り、backend が扱える設定だけを候補にします。実行不能等で option 一覧を取得できない場合は静的情報に基づく計画として記録・表示されます。実際に一覧を取得できたのに backend と engine の option が合わず探索次元が全て除外された場合は、その不一致理由を計画に含めます（`strata_control/tuning.py:151-174,205-224,723-768`）。
- `run` は基準・候補の測定結果、失敗理由、baseline drift などを report に残します。探索は `--trials` と `--time` の上限に制約されます。既定の protocol 計測は利用者が待つ HTTP 経路そのものではないため、CLI は推薦を信頼する前に `--mode api` で確認するよう案内します。job/report の永続化は実行処理（`tuning.Tuner`）に委譲されます（`strata_cli/cli.py:1742-1847`）。
- job の保存先は `--state-dir`、環境変数 `STRATA_TUNE_DIR`、既定の Strata state ディレクトリ内 `tuning` の順に決まります。`list` / `status` はこの保存先を読み、`run` / `apply` / `rollback` は同じ state root を使います（`strata_cli/cli.py:1643-1650,1655-1685,1708-1713`）。
- `apply` は推薦の有無、job 完了状態、report の整合性、engine/model/backend/workload/context の同一性などを検査します。記録に model digest がない sweep は適用を拒否します。候補引数は run config の `args` に反映され、既存の同じ引数を置換し、ほかの設定は保持します。元ファイルと application record を保存し、設定ファイルを atomic write します（`strata_cli/cli.py:1850-1905`、`strata_control/tune_apply.py:118-166,227-289,306-370`）。
- 現行 CLI の `apply` は `apply_recommendation(..., verify=None)` を呼びます。そのためこの入口では候補設定を実際のモデルで起動して token 生成を検証しません。成功表示にも未検証の旨が出ます。推薦が起動可能であることは別途確認してください（`strata_cli/cli.py:1900-1921`）。
- `rollback` は元 config の退避 bytes を復元します。apply 以後に対象 config が変わっていれば、ユーザー編集を上書きしないよう失敗します（`strata_control/tune_apply.py:373-390`）。
- `auto` は worker を起動して測定し、進捗を stderr に出します。work dir の既定は一時ディレクトリです。試行履歴を保存し、結果が `improved` または `default_confirmed` で `--no-save` でなければ preset を作成します。`--leave-ram` は0〜50%に限られ、範囲外はエラー、非0指定は speed goal を room goal に切り替えます（`strata_cli/tune_commands.py:31-46,174-261`）。

## 注意点

- sweep は自動的に active profile/config を変更しません。変更は `apply` で行います。`auto` は別系統で、測定後に preset を保存できます。
- `run --mode api` は `--config` と回答検証用の `--api-expect` がないと終了コード2相当のエラーになります（`strata_cli/cli.py:1771-1784`）。
- `apply` の現行 CLI 経路は実モデルでの起動検証を渡していません。適用後に設定を利用する前に、生成が正常に行えるか確認してください（`strata_cli/cli.py:1900-1921`）。
- backend、実機、GPU driver、モデル構成ごとの性能値や利用可能な候補は実行環境で異なります。この文書ではベンチマーク結果や性能向上を保証しません。

## 関連文書

- [`strata tune plan`](plan/README.md)
- [`strata tune run`](run/README.md)
- [`strata tune apply`](apply/README.md)
- [`strata tune rollback`](rollback/README.md)
- [`strata tune status`](status/README.md)
- [`strata tune list`](list/README.md)
- [`strata tune auto`](auto/README.md)
- [CLI 文書索引](../../README.md)

## 根拠

- `strata_cli/cli.py:395-486` — コマンド階層、サブコマンドと引数の parser。
- `strata_cli/cli.py:1632-1739` — state directory、`plan` / `list` / `status` の分岐と表示。
- `strata_cli/cli.py:1742-1847` — sweep 計測方式、report、protocol/API の案内。
- `strata_cli/cli.py:1850-1963` — apply・rollback と失敗経路。
- `strata_cli/tune_commands.py:20-46,174-261` — `auto` の parser、測定、preset 保存、終了コード。
- `strata_control/tuning.py:151-174,205-224,723-768` — backend/engine option による探索範囲と plan。
- `strata_control/tune_apply.py:118-166,227-289,306-390` — config 差分、適用記録、atomic write、rollback。
