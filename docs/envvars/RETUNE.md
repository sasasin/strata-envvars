# `RETUNE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Docker image の `docker/entrypoint.sh` が、既存 preset の調整済み結果を保持するか、`strata launch` に再測定を指示するかを切り替えます。Strata の通常の CLI や engine が `RETUNE` を直接読む箇所は見つかりません。Docker entrypoint が `RETUNE=1` を CLI 引数 `--retune` に変換します。

## 値と判定

シェルの `${RETUNE:-0}` を文字列 `1` と完全一致で比較します。

| 環境値 | 判定 |
|---|---|
| 未設定、空文字 | 無効（`0` に置換） |
| `1` | 有効 |
| その他すべて（例: `0`, `01`, `1 `, `true`） | 無効 |

大文字小文字や数値への変換はありません。値は tune 判定を行う entrypoint の実行時に参照され、Strata のプロセス内に cache されません。

## 有効になる条件

- `TUNE` が空でなく、小文字化した値が `skip` でないことが必要です。したがって `RETUNE=1` だけでは調整を開始しません。`TUNE=skip`（大文字小文字を問わない）でも `RETUNE` は使われません。
- この分岐の中で、保存済み preset が存在し、`strata launch --list-presets` の該当行が `not tuned` を含まない場合、entrypoint は「調整済み」と判定します。調整済みで `RETUNE` が有効でなければ `--tune` を付けず、「This preset is already tuned; keeping the tuned settings (set RETUNE=1 to tune again).」と表示します。
- 調整済み preset がない場合、または `RETUNE=1` の場合、entrypoint は `--tune <小文字化した TUNE>` を追加します。さらに `RETUNE=1` なら `--retune` も追加します。`TUNE` の有効な CLI 値は `quick`, `thorough`, `skip` です。entrypoint は `skip` を除く値を渡すため、不明な値は CLI の選択肢検証で拒否されます。

## 実行時の詳細

`--retune` は保存済みの tuning 結果がある場合も測定を行う指定です。launch CLI は `--retune` を受け取ると `Runner` にフラグを渡し、`--tune` が `skip` なら `quick` に切り替えます。通常の単一ファイル経路では `Runner.tune()` がこのフラグを見て、保存済み preset や同じ model / choices に対する保存済み tuning 結果を使った早期 return を行わず、測定用の `strata tune auto ... --mode quick|thorough` を起動します。`Runner.tune()` は multi-file 経路を別の `tune_deepseek()` に渡すため、その経路の詳細はここでは断定しません。

Docker entrypoint は `RETUNE` を読んで CLI 引数へ変換します。CLI / Runner は `RETUNE` 自体を読みません。そのため `strata launch` を直接実行するときは `RETUNE=1` ではなく `--retune` を指定します。測定開始時には Runner が `Tuning for the best speed. Close other heavy programs while it measures.` を出し、測定結果を `Tuning result: ...` として表示します。

## 根拠

- `docker/entrypoint.sh:20` — Docker 設定の説明。
- `docker/entrypoint.sh:228-239` — `TUNE` 条件、既存 preset 判定、`RETUNE` の完全一致判定、CLI 引数とログ。
- `strata_cli/launch/cmd.py:122-123,143-145,904-907` — `--tune` の選択肢、`--retune` の説明と Runner への受け渡し、`skip` 時の既定 quick。
- `strata_cli/launch/runner.py:1839-1875,1893-1908` — 保存結果の再利用条件、測定起動、結果ログ。
- `docs/DOCKER.md:125,214-215` — Docker 文書も `RETUNE=1` による再調整を案内。
