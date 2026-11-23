# `STRATA_FS_VERIFY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Foresight swap の VRAM スロットを初回使用時に読み戻し、コピー元の expert blob とバイト単位で比較する診断用スイッチです。通常のスロット利用に照合処理を加えます。照合に失敗したスロットは使用対象から外されます。設定を読むのは `foresight_swap_from_env` で、照合は `ForesightSwap::take` が行います（`engine/src/core/expert_source.cpp:7161-7195,7294-7321`）。

## 値と判定

serve の Foresight swap 初期化時に、局所 `env_int` helper が `getenv` で読み、設定値を `atoi` で整数化します。未設定なら `0`、変換後の値は下限 `0` に clamp され、`!= 0` なら照合を有効にします。空文字や数値に変換できない文字列は `atoi` により `0` となります。文字列全体の検証はなく、数値の後ろの文字は `atoi` の変換対象外です。たとえば `1` や `2junk` は有効、`0`、`0anything`、`true`、空文字、`-1` は無効です。先頭空白や符号の処理も `atoi` に従います。`atoi` の表現範囲を超える入力について、Strata 独自の検査や規則はありません（`engine/src/core/expert_source.cpp:7307-7312`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| serve で Foresight swap 初期化に到達 | `0`（無効） | `atoi` 結果が正の整数になる値。例: `1`, `2junk` | `atoi` 結果が 0 以下の値。例: 空文字, `0`, `0anything`, `true`, `-1` |

## 有効になる条件

- serve の実行経路で Foresight swap 初期化が呼ばれる必要があります。初期化では `STRATA_FS_SLOTS` を `atoi` で読み、0 以下なら swap 自体を作らず、この変数も読みません（`engine/src/program/generate.cpp:14795-14807`, `engine/src/core/expert_source.cpp:7294-7306`）。
- `STRATA_VERIFY_DEVICE_PLAN` または `STRATA_VERIFY_DEVICE_HITS` が設定され、かつその `atoi` 結果が非 0 の場合、swap 初期化は警告を出して終了します。その場合 `STRATA_FS_VERIFY` による照合機能もありません（`engine/src/core/expert_source.cpp:7299-7305`）。
- swap の初期化に失敗した場合も swap は破棄され、この設定の効果はありません（`engine/src/core/expert_source.cpp:7312-7316`）。
- Strata の設定一覧は親機能 `STRATA_FS_SLOTS` を CUDA 向けとして記載しています。該当実装は CUDA runtime API（`cudaMemcpy` 等）を直接呼びます。`STRATA_FS_VERIFY` 専用の追加 backend guard はこの読み取り・照合箇所にはありません（`docs/DETAILS.md:1244`, `engine/src/core/expert_source.cpp:7082-7113,7176-7180`）。

## 実行時の詳細

serve の swap 初期化時に一度だけ環境値を読み、結果を `ForesightSwap::verify` に保存します。リクエストごとの再読込や static cache はなく、起動後に環境値を変更しても既存 swap には反映されません（`engine/src/program/generate.cpp:14795-14807`, `engine/src/core/expert_source.cpp:7294-7312`; フィールドは `engine/include/strata/core/foresight_swap.hpp:49-66`）。

expert の GPU コピーがイベント完了後に初めて `take` された時、verify が有効ならスロット全体を Device-to-Host で読み戻し、コピー元 `sl.src` と `memcmp` します。照合成功なら通常どおり GPU グループの入力として返します。照合が不一致、または読み戻しの `cudaMemcpy` が失敗した場合は `verify_bad` を増やし、その expert の対応付けとスロットを無効にして `take` は false を返します。呼び出し側は通常の cache miss 経路へ進み、miss を記録し、設定されていれば PCIe fetch 条件を評価します（`engine/src/core/expert_source.cpp:7161-7195,5573-5607`）。スロットが再利用されて再コピーされた場合は、次に初めて使う際に再照合されます。

## ログと測定値

個々の照合不一致や読み戻し失敗について、verify 専用の stderr 警告やプロセス終了はありません。serve の集計出力には verify が有効な場合に限り `verified <成功数> ok / <失敗数> BAD` が追加されます（`engine/src/core/expert_source.cpp:7281-7291`）。serve 側では `strata serve: ` を付けてこの report を stderr に出します（`engine/src/program/generate.cpp:23286`）。照合失敗は該当スロットを使わない結果になりますが、それだけで serve 全体を終了しません。

照合にはスロット blob 全体の同期読み戻しと比較が発生します。Strata 資料にこの設定の性能測定値は見つかりませんでした。

## 根拠

- `engine/src/core/expert_source.cpp:7294-7321` — swap の有効化条件、関連変数との排他、値の読み取りと判定、初期化ログ。
- `engine/src/core/expert_source.cpp:7161-7195` — 初回 slot 使用時の照合、成功・失敗時の状態遷移。
- `engine/src/core/expert_source.cpp:5573-5607` — `take` が失敗した後の miss 処理。
- `engine/src/core/expert_source.cpp:7281-7291` と `engine/src/program/generate.cpp:23286` — swap report の内容と stderr 出力。
- `engine/include/strata/core/foresight_swap.hpp:49-66` と `engine/src/program/generate.cpp:14795-14807` — 保存される bool と serve 初期化への接続。
