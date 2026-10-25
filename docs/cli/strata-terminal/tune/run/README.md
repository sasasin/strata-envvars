# `strata tune run`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/tuning.py`、`strata_control/tune_engine.py`、`strata_control/tune_api.py` |

## 役割

指定したエンジンと backend に対して、基準設定と候補設定を実際に計測し、制限付きの探索結果を job として保存します。結果には各候補の測定値、失敗理由、推奨設定が含まれます。設定ファイルは自動変更されず、推奨値の適用は別コマンド `strata tune apply` で行います。

このコマンドはハードウェア上でエンジンを起動して測定します。GPU や対象デバイスを使う可能性があるため、利用中の推論サーバーを停止し、計測中に他の処理が同じデバイスを使わない状態で実行してください。

## 代表的な使い方

```sh
# エンジン自身の serve protocol で候補を測る（既定モード）
strata tune run --engine /path/to/strata --backend cuda --model example-model

# HTTP API 経由で、実際の worker 設定を使って確認する
strata tune run --engine /path/to/strata --backend cuda --model example-model \
  --mode api --config ./strata-example-model.json --api-expect 'hash table'

# 保存した job とレポートを確認する
strata tune status JOB_ID
```

`--engine`、`--backend`、`--model` は必須です。探索の上限、計測 workload、対象 engine の dimension 固定、model identity の記録などはオプションで調整します。索引に列挙されたオプションは [`docs/cli/README.md`](../../../README.md) の `strata tune run` 節を参照してください。

## 実行モード

| モード | 動作 |
| --- | --- |
| `protocol`（既定） | エンジンを候補ごとに子プロセスとして起動し、固定 workload をエンジン独自の serve protocol に送り、結果を測ります。候補ごとに起動し直すため、設定変更を反映した測定になります。 |
| `api` | `--config` の設定を基に候補ごとの一時設定ファイルを作り、worker を loopback の HTTP API で起動して測ります。起動時に `--api-expect` が必須で、応答が指定正規表現に一致するかも確認します。worker と一時設定ファイルは各測定後に終了・削除されます。 |

`protocol` はエンジンの計測 protocol による測定で、利用者が待つ HTTP リクエスト全体の時間とは異なります。実装は指定長の決定的な token ID 列を使い、実際のモデル tokenizer でプロンプトを token 化する処理ではありません。利用者向けの応答時間を確認したい場合は `api` モードで別途測定してください。`api` モードでも、候補 config は元のファイルのコピーから作成され、元ファイルを書き換えません。

## 主要な動作と保存

- `--trials`（既定 16）と `--time`（既定 1800 秒）は探索の上限です。計測開始前に baseline を測り、候補を測定し、baseline を最後に再測定してドリフトを記録します。時間上限に達した後は新しい候補を開始しません。
- `--repeats`（既定 3）は候補ごとの paired repeat 数です。parser で整数として読み取り、探索計画では最低 1 に丸められます。`--trials` は 0 未満の場合に 0 として計画されます。
- `--hold DIMENSION` は繰り返し指定でき、該当 dimension を探索対象から外します。engine binary の flag inventory と backend によって探索可能な dimension は変わります。
- `--model-path` が省略されると model digest を持たない identity となり、後から他の測定と比較可能な model identity を確立できません。`--full-digests` を指定すると engine と model の完全 hash を取り、通常のサンプル hash より強い identity にします。
- `--state-dir` が未指定なら `STRATA_TUNE_DIR`、それも未設定なら Strata の per-user state directory 内 `tuning/` に job を保存します。job ごとに `job.json` が作成・更新され、終了時の report と測定 evidence が残ります。
- 成功した測定は推奨候補を報告することがありますが、それだけで適用可能とは限りません。別途 `strata tune apply JOB_ID` が identity などを再確認し、設定変更を行います。適用後の復元には [`strata tune rollback`](../rollback/README.md) を参照してください。

## 出力と注意点

既定の human 出力では job ID と状態、baseline、実行候補数、失敗候補、drift、推奨内容を表示し、`strata tune status JOB_ID` での確認方法を案内します。`--output json` を指定すると job record を含む JSON を標準出力に返します。

指定 engine が存在しない場合や `--mode api` で `--config` / `--api-expect` が不足する場合はエラーコード 2 で終了します。候補を測定できなかった場合は job 内に失敗理由を記録し、起動失敗・request timeout・engine の `ERR` 応答などは候補の計測失敗として扱われます。baseline の失敗や job 全体の例外は job の状態に記録されます。

`api` モードは既定で loopback port 8123 を使います。別プロセスが同じ port を使用中なら測定できないため、必要なら `--api-port` を変更してください。job は durable state に書き込まれ、protocol モードでは候補ごとに engine 子プロセスを起動し、API モードでは worker と engine を起動します。長時間の計測やデバイス利用を伴うため、実行環境と保存先を確認してから実行してください。

## 関連文書

- [`strata tune`](../README.md) — tune コマンド群の概要
- [`strata tune plan`](../plan/README.md) — 計測せず探索範囲を確認
- [`strata tune apply`](../apply/README.md) — レビューした推奨を設定へ適用
- [`strata tune rollback`](../rollback/README.md) — apply 前の設定へ復元
- [CLI 索引](../../../README.md) — `strata tune run` のオプション文書
- [調査手順と配置規約](../../../001_investigation.md)

## 根拠

- `strata_cli/cli.py:395-396` — `tune` の parser と必須サブコマンド。
- `strata_cli/cli.py:414-459` — `run` の全オプション、既定値、選択値、必須値。
- `strata_cli/cli.py:1640-1650,1708-1709` — `--state-dir` / `STRATA_TUNE_DIR` / per-user state による保存先と run handler。
- `strata_cli/cli.py:1742-1806` — engine の存在確認、探索計画、mode ごとの測定器選択、job の実行と JSON 出力。
- `strata_cli/cli.py:1808-1847` — human report、protocol mode の測定上の制約、apply を別操作とする案内。
- `strata_control/tuning.py:317-362,423-484` — job directory と `job.json` の保存、baseline・候補・再測定、時間上限、失敗状態と lease の解放。
- `strata_control/tuning.py:723-768` — engine/model identity、digest、hold、探索上限と repeat 数の計画処理。
- `strata_control/tune_engine.py:388-420,430-471,501-557,596-612` — protocol mode の engine 子プロセス起動、workload 測定、失敗経路と終了。
- `strata_control/tune_engine.py:560-568` — 固定 workload の決定的 token ID 列。
- `strata_control/tune_api.py:41-47,73-104,123-135,260-294` — API worker の起動・停止と候補別 config copy の生成・削除。
- `strata_control/paths.py:13-21` — per-user state directory の POSIX / Windows 規則。
