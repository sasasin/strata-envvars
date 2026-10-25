# `strata drafting fetch`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。Strata checkout の作業状態は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| 主な実装 | `strata_cli/drafting_cmd.py`、`strata_control/drafting_fetch.py` |
| 引数 | `--data-dir`、`--config`、`--family`、`--mode`、`--if-needed`、`--output` |

## 役割

DFlash2 drafter の配布ファイルを固定 revision から取得し、SHA-256 を確認した後、エンジン用 pack に変換してモデルデータ領域へ配置します。取得元、revision、ファイルサイズ、hash は Strata 側で固定されています。ダウンロード元の `safetensors` と設定ファイルは pack 後に削除され、エンジン用 pack が残ります（`strata_control/drafting_fetch.py:1-8,54-57,70-101`、`strata_control/drafting.py:82-100`）。

通常のモデル起動はこのコマンドとは別の経路です。CLI の説明では、ネットワーク取得を行うのは明示的な取得コマンドで、モデルの起動・serve は取得しません（`strata_control/drafting_fetch.py:6-8`、`strata_control/acquisition.py:1-14`）。

## 使い方

```sh
# Strata が使う標準のモデルデータ領域に取得して pack を作る
strata drafting fetch

# 保存先を明示する
strata drafting fetch --data-dir /path/to/model-data

# 必要条件を満たす場合だけ取得し、機械処理向け JSON Lines で進捗を受け取る
strata drafting fetch --config /path/to/run-config.json --if-needed --output jsonl

# 変更や通信をせず、取得計画を確認する
strata drafting plan --data-dir /path/to/model-data
```

`plan` は別サブコマンドです。`fetch` と共通の `--data-dir`、`--config`、`--family`、`--mode`、`--output` を使って、対象モデルの判断や pack の有無、取得サイズなどを表示します。実ファイルの取得・変換は行いません（`strata_cli/drafting_cmd.py:17-29,63-73`、`strata_control/drafting_fetch.py:29-39`）。

## 実行モードと主な動作

- 既定の出力は `human` です。`--output json` は機械向け JSON の結果を出し、`--output jsonl` は JSON Lines の進捗イベントと結果を出します。いずれも parser が受理する値は `human`、`json`、`jsonl` です（`strata_cli/drafting_cmd.py:17-29,57-59,81-98`）。
- Pack がすでに存在して十分なサイズであれば、再取得せずそのパスを返します。未取得の場合、`strata_control/drafting.py` に記録された固定 revision のファイルを取得し、ファイルサイズと SHA-256 を検査してから pack を作ります。pack の既定パスは `<data-dir>/dflash2/qwen3.8-flash-next-dflash2.q8.pack` です（`strata_control/drafting_fetch.py:54-67,70-89`、`strata_control/drafting.py:88-100,114-122`）。
- `--config` と `--mode` は、`--if-needed` の要否判定や `plan` の判断材料になります。`--data-dir` を省略すると、config の engine 引数からデータ領域を特定し、見つからなければ Strata 標準のデータ領域を使います。config の読み込みで OS または JSON エラーが起きた場合、エラーを表示せず空 config として続行します（`strata_cli/drafting_cmd.py:40-55`）。
- `--family` はモデル family がまだ run config にない場合に判断材料として使われます。対応するのは `qwen` と `gyro` family、または config のモデル名が Qwen3.8-Flash-Next 系に一致する場合です（`strata_control/drafting.py:102-111`）。
- `--if-needed` を付けない `fetch` は、mode・family・config が DFlash2 利用条件に合うかにかかわらず、明示的な取得処理を実行します。付けた場合は `drafting.needs_pack()` が false なら取得を省略します（`strata_cli/drafting_cmd.py:57-79`）。

## 適用条件と注意点

この revision では `ENGINE_SERVES_DFLASH2 = False` です。そのため `needs_pack()` は常に false となり、`--if-needed` を付けた呼び出しは `Nothing to download.`（機械出力では `skipped: true`）を返して終了します。これは現在の serving 機能が DFlash2 を使わないことを反映します。`--if-needed` を付けない明示的な `fetch` は、この条件判定による skip を通らず取得します（`strata_control/drafting.py:141-146,179-184`、`strata_cli/drafting_cmd.py:62-79`）。

したがって、pack を事前配置する用途を除き、DFlash2 を実際のモデル起動で使えるとはこの revision のソースから確認できません。リリースノートも DFlash2 を Terminal の opt-in 機能として説明していますが、実装上 serving に非対応である点は上記定数と判断処理に従います（`docs/release-notes-0.2.3.md:7`、`strata_control/drafting.py:141-176`）。

取得を許可しない実行環境では `acquisition.require()` が拒否し、取得処理は `AcquisitionRefused` を返します。取得ファイルの hash 不一致、通信失敗、pack 生成失敗もエラーになります。CLI はこれらのエラーを stderr（human）または JSON（`json` / `jsonl`）に出し、終了コード `5` を返します。hash 不一致ファイルは削除され、通信中断は再試行時に続きから取得できる旨をエラーに示します（`strata_control/acquisition.py:32-43,70-73`、`strata_control/drafting_fetch.py:70-94`、`strata_cli/drafting_cmd.py:87-98`）。

## 関連文書

- [`strata drafting` 概要](../README.md)
- [`strata drafting plan` 概要](../plan/README.md)
- [`strata launch` 概要](../../launch/README.md)
- [CLI 索引の `strata drafting fetch` 節](../../../README.md#strata-drafting-fetch-draftingfetch)
- 個別オプション: [`--config`](--config.md)、[`--data-dir`](--data-dir.md)、[`--family`](--family.md)、[`--help` / `-h`](--help.md)、[`--if-needed`](--if-needed.md)、[`--mode`](--mode.md)、[`--output`](--output.md)

## 根拠

- `strata_cli/cli.py:172-173,2144-2146` — drafting parser の登録と実行 dispatch。
- `strata_cli/drafting_cmd.py:17-29` — `plan` / `fetch` の parser と option scope。
- `strata_cli/drafting_cmd.py:40-55,57-99` — config・data dir の解決、plan / skip / fetch の分岐、出力と終了コード。
- `strata_control/drafting_fetch.py:1-8,29-39,54-102` — 取得計画、hash 検査、pack 作成と元ファイル削除。
- `strata_control/drafting.py:82-122,141-184` — 固定対象、保存先、対応条件、現 revision の serving 可否と必要判定。
- `strata_control/acquisition.py:1-14,32-43,70-83` — 明示取得の境界と取得拒否時のエラー。
- `docs/release-notes-0.2.3.md:7` — DFlash2 の利用者向け説明。

同一 revision の CLI `--help` は実行していません。parser 定義・処理経路・関連実装を直接確認しました。GitHub Release の実配布物は確認しておらず、本書は指定 checkout のソースに基づきます。
