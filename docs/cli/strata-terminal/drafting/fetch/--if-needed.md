# `--if-needed`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--if-needed` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は `False` |

## 役割

DFlash2 drafter の取得・pack 作成を、現在のモデル設定がその drafter を使う見込みで、かつ pack がまだ存在しない場合に限って実行します。条件に合わなければ成功扱いで何も取得しません。parser は `fetch` にだけこのフラグを登録し、`plan` には登録しません（`strata_cli/drafting_cmd.py:17-29`）。

## 使い方

```sh
strata drafting fetch --config /path/to/run-config.json --if-needed
```

アプリ側もモデルの run config と任意の `--mode` を渡し、`--if-needed --output jsonl` で取得を呼び出します（`apps/host/server/control-runtime.mjs:256-261`）。

## 値と既定値

値や alias はありません。指定すると `action="store_true"` で有効になり、省略時は無効です（`strata_cli/drafting_cmd.py:27-29`）。このため、省略時は必要性判定を使わず `ensure()` に進みます。すでに有効な pack があれば `ensure()` 自身が既存 pack を保持して返します（`strata_cli/drafting_cmd.py:74-88`, `strata_control/drafting_fetch.py:54-62`）。

必要性は `drafting.needs_pack()` が判定します。選択モードが DFlash2 になり、対象モデル・family が対応し、当該 revision でエンジンが DFlash2 を serve でき、かつ pack が未準備の場合だけ真です（`strata_control/drafting.py:179-183`）。pack は `<data-dir>/dflash2/qwen3.8-flash-next-dflash2.q8.pack` にあり、ファイルが存在してサイズが 1 MiB を超える場合に準備済みとみなされます（`strata_control/drafting.py:88-100,114-122`）。

## 実行時の動作

モードは明示された `--mode` が最優先で、なければ `--config` の `drafting` 値を使います。`--mode` の受理値は `auto`、`mtp`、`dflash2`、`off` です（`strata_cli/drafting_cmd.py:24-28,40-54`; `strata_control/drafting.py:23-25`）。run config の読み込みに失敗した場合は空設定として扱われます（`strata_cli/drafting_cmd.py:40-46`）。

データディレクトリは明示した `--data-dir`、run config の engine 引数にある `--pack` / `--mtp` から得た場所、Strata の既定カタログの順で決まります。モデル名は config の `model_name`、family は `--family` から判定材料に渡されます。GPU class の取得に失敗した場合は `other` として扱います（`strata_cli/drafting_cmd.py:32-54`; `strata_control/drafting.py:67-73,107-122,203-212`）。

必要と判定されなければ、human 出力は `Nothing to download.`、`json` / `jsonl` 出力は `{"schema_version":1,"ok":true,"event":"result","pack":null,"skipped":true}` 相当を出し、終了コード 0 で戻ります（`strata_cli/drafting_cmd.py:57-79`）。必要な場合は `ensure()` が pinned URL からファイルを取得し、サイズと SHA-256 を確認して engine 用 pack を作成します。進捗は `jsonl` では progress JSON 行、human では進捗表示になります。`--output` は `human`（既定）、`json`、`jsonl` のいずれかです（`strata_cli/drafting_cmd.py:29,81-98`; `strata_control/drafting_fetch.py:29-39,54-102`; `strata_control/drafting.py:88-100`）。

## 適用条件と副作用

この commit では `ENGINE_SERVES_DFLASH2 = False` です。そのため `needs_pack()` はこの revision では常に false となり、`--if-needed` を指定した呼び出しは設定や pack の状態に関係なく skip します。これは DFlash2 がこのリリースの engine serve 経路では使えないため、不要な 1.2 GB download を避ける設定です（`strata_control/drafting.py:141-146,179-183`）。将来この定数が変わった場合の条件付き動作も `needs_pack()` によって決まります。

skip されず `ensure()` に進むと、ネットワーク取得を行い、`<data-dir>/dflash2/src/` を作成して取得元ファイルを一時保存し、pack を生成します。成功後は元の safetensors / config ファイルを削除し、pack を残します。既存の pack が準備済みなら取得・pack し直しません（`strata_control/drafting_fetch.py:54-102`）。このオプション自体は取得を禁止しません。取得抑止環境 `STRATA_NO_ACQUIRE` 等で取得が拒否される場合は失敗経路になります（`strata_control/acquisition.py:26,53-54,70-74`; `strata_control/drafting_fetch.py:63-64`）。

## 出力とエラー

取得・検証・pack 作成時に `DraftingError` または `AcquisitionRefused` が発生すると、終了コード 5 を返します。machine output は `ok:false` と `drafting_failed` エラーを出し、human output は stderr に `strata: ...` を出します（`strata_cli/drafting_cmd.py:87-94`）。SHA-256 不一致時は不正な partial file を削除して再試行を案内し、転送中断時は `.part` を残して再開可能と伝えます。pack 生成失敗時は一時 `.tmp` を消して MTP 継続を案内します（`strata_control/drafting_fetch.py:75-94`; `strata_control/transfer.py:198-221`）。

## 根拠

- parser、値・既定値、実行分岐、出力・終了コード: `strata_cli/drafting_cmd.py:17-29,40-98`
- 必要性・対応モデル・現在の engine 条件・pack 判定: `strata_control/drafting.py:88-100,107-122,141-183`
- 取得、再開、検証、pack 作成と後片付け: `strata_control/drafting_fetch.py:54-102`; `strata_control/transfer.py:198-221`
- 取得拒否条件: `strata_control/acquisition.py:26,53-74`
- 呼び出し例（アプリの利用経路）: `apps/host/server/control-runtime.mjs:256-261`
