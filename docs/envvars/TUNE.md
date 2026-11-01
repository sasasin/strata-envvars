# `TUNE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリや GPU driver が読む環境変数は対象外。

## 役割

`TUNE` は Strata の Docker image が既定の server 起動を行うとき、起動時にチューナーを実行するか、実行する場合のモードを選ぶための entrypoint 設定です。`docker/entrypoint.sh` が値を読み、`quick` または `thorough` を `strata launch --tune` に渡します。Strata の通常の `strata launch` CLI や engine が `TUNE` を直接読む実装は見つかりません。

Docker Compose の NVIDIA / AMD / Intel 定義は `${TUNE:-skip}` でコンテナへ渡すため、Compose ではホスト側の値が未設定または空なら `skip` になります。Compose を使わず Docker entrypoint を起動した場合も、未設定・空は調整を行わず、CLI の既定値 `skip` と同じ結果になります (`docker/compose/docker-compose.nvidia.yml:22`, `docker/compose/docker-compose.amd.yml:21`, `docker/compose/docker-compose.intel.yml:21`, `strata_cli/launch/settings.py:116`)。

## 値と判定

entrypoint は `${TUNE:-}` を取り出して ASCII 大文字を小文字へ変換します。空文字は未設定と同じく空として扱い、空または `skip` のときは `--tune` 引数を追加しません。その他の値はそのまま一つの `--tune` 引数として CLI に渡します (`docker/entrypoint.sh:228-239`)。

| 入力 | entrypoint がすること | 結果 |
| --- | --- | --- |
| 未設定 / 空文字 | `--tune` を追加しない | CLI の既定 `skip`。調整を実行しない |
| `skip`（大文字小文字は不問） | `--tune` を追加しない | 調整を実行しない |
| `quick` / `thorough`（大文字小文字は不問） | 小文字化して `--tune <値>` を追加 | CLI が受け付ける調整モード |
| その他の非空文字列 | 小文字化して `--tune <値>` を追加 | CLI の選択肢検査で拒否 |

CLI の `--tune` は `quick`, `thorough`, `skip` のいずれかに限られ、選択肢 helper は前後空白を除いて小文字化します。したがって `TUNE=" QUICK "` は `quick` として受け付けられますが、entrypoint 自体は空白を除去しません。無効値は CLI の argparse エラーになり、entrypoint は終了コードを `strata launch stopped with code ...` として stderr に出して終了します。CLI のエラーには `argument --tune:` に続いて `'<値>' is not a tuning mode. Choose one of: quick, thorough, skip.`（近い選択肢があれば候補の案内を追加）が含まれます (`strata_cli/launch/cmd.py:37-45,115`; `docker/entrypoint.sh:228-239,285-290`)。

`RETUNE` は別の環境変数です。entrypoint は `RETUNE` が文字列 `1` のときだけ、自身の「preset は既に調整済み」という早期スキップを通過させます。`TUNE=skip` または空ならこの判定に入らないため、`RETUNE=1` 単独では調整しません (`docker/entrypoint.sh:230-239`)。

## 有効になる条件

- entrypoint が既定の server 起動経路を通る必要があります。コンテナに `strata ...`、`sh` などのコマンド引数を渡すと、entrypoint は設定処理より前に `exec` するため `TUNE` を読まず、引数付き `strata launch` でも `TUNE` は適用されません (`docker/entrypoint.sh:53-56,228-239`)。
- 通常起動経路では、エンジンの適合性確認などの準備後に `TUNE` を評価します。`quick` / `thorough` は既存 preset が調整済みでないときに `--tune` として CLI へ渡されます。preset が既に調整済みで `RETUNE` が `1` 以外なら、entrypoint が「This preset is already tuned; keeping the tuned settings ...」と表示して `--tune` を付けません (`docker/entrypoint.sh:136-160,228-239`)。
- `TUNE_ALLOW_SMALL=1` の場合、`TUNE` の値とは独立に `--tune-allow-small` も渡します。その他の値では渡しません (`docker/entrypoint.sh:240`; CLI option `strata_cli/launch/cmd.py:115-116`)。
- チューニングの backend やモデル別処理は `TUNE` ではなく CLI の tuning 実装に委ねられます。CLI は `thorough` のとき thorough mode、それ以外の調整実行時は quick mode を選び、複数ファイルモデル経路では DeepSeek 専用 tuner に分岐します (`strata_cli/launch/runner.py:1512-1524,1555-1589`)。

## 実行時の詳細

値を読むのはコンテナ起動のたびに entrypoint が設定引数を組み立てる時点で、同じ起動中に再読込・cache する処理はありません。`quick` または `thorough` を指定し、preset が未調整なら「Tuning is on (TUNE=...): ...」を stdout に出し、最終的に `strata launch --no-tui ... --tune <モード>` を実行します。既定では preset 側に調整結果が記録され、次の起動では再測定を避ける設計です (`docker/entrypoint.sh:228-239,273-290`; `docs/DOCKER.md:125,132-135`)。

`RETUNE=1` の再測定にはコード上の食い違いがあります。Docker 文書は `RETUNE=1` で再調整すると説明しますが、entrypoint が CLI に加えるのは `--tune <モード>` で、`--retune` は追加していません。preset を CLI に読み込むと保存済み `tuned_preset` / `tuned_at` が残り、`Runner.tune()` は `retune` が false で tuning 情報がある場合に測定を省略します。そのため、すでに調整済み preset に `TUNE=quick RETUNE=1` を指定しても、entrypoint の早期スキップは通過しますが、CLI runner は既存結果を再利用し、実測を再実行しない経路があります。これは `docs/DOCKER.md:125,215` の説明と現行コードの差です (`docker/entrypoint.sh:233-239`; `strata_cli/launch/cmd.py:136-138,205-211,781-784`; `strata_cli/launch/runner.py:1555-1579`; `strata_cli/launch/settings.py:129-133`)。

調整実行時は runner が通常モデル向け tuner または複数ファイルモデル向け DeepSeek tuner を起動します。測定の開始・結果は CLI の tune event として出力され、保存済み情報があれば「This preset is already tuned ...」または「Already tuned on ...」などを出して再測定しません。Docker entrypoint は CLI が非ゼロ終了すると `phase failed` を記録し、上記の終了コードでコンテナ起動を終了します (`strata_cli/launch/runner.py:1512-1553,1555-1624`; `docker/entrypoint.sh:285-290`)。

## 根拠

- `docker/entrypoint.sh:53-56,228-240,273-290` — 対象経路、値の処理、preset / `RETUNE` 判定、CLI への引数付加、起動ログと失敗終了。
- `docker/compose/docker-compose.nvidia.yml:22`, `docker/compose/docker-compose.amd.yml:21`, `docker/compose/docker-compose.intel.yml:21` — Compose からの転送と `skip` fallback。
- `strata_cli/launch/settings.py:26,116,129-133` — CLI の tuning 候補、既定値、tuned marker の意味。
- `strata_cli/launch/cmd.py:37-45,115-116,136-138,205-211,262-265,781-784` — CLI 値検証、preset 設定合成、`--retune` の意味と runner への伝達。
- `strata_cli/launch/runner.py:1512-1553,1555-1624,2286-2318` — 実行モード、tuned marker による再測定省略、起動内での tuning 呼び出し。
- `docs/DOCKER.md:125,132-135,214-215` — 文書上のモード・既定値・再調整説明。`RETUNE=1` の説明は entrypoint / runner 実装と一致しない。
