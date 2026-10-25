# `STRATA_METAL_MTP_CHAIN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal engine の MTP（投機デコード用 draft layer）で、draft 1 回分の処理をまとめて GPU に送る経路を選びます。有効な場合、draft の選択、確率計算、次ステップ用 embedding を含む一連の処理を1回の command buffer で実行します。無効な場合は draft step ごとに command buffer を実行し、各 step の token 選択と次 embedding の dequantize をホスト側で行います。

## 値と判定

Metal の `Window::mtp_load()` が `std::getenv()` で値を読み、文字列全体を `"0"` と比較します。数値変換や前後空白の除去はありません。

| 値 | chain の要求 |
|---|---|
| 未設定 | 有効を要求 |
| 空文字 | 有効を要求（設定値は `"0"` と一致しない） |
| 文字列がちょうど `0` | 無効 |
| その他の設定値（例: `1`, `false`, `00`, ` 0`） | 有効を要求 |

有効を要求しても、後述の embedding 型条件と初期 parity 確認を通らなければ chain は使われません。値の読み取りは MTP layer の load 時に行われます。

根拠: `metal/src/engine/window.cpp:1489-1494,1578-1585`。

## 有効になる条件

- `STRATA_METAL_MTP_CHAIN` がちょうど `0` ではない。
- `token_embd.weight` の型番号が `{30, 8, 2, 6, 20, 23, 42, 21, 11, 12, 13, 14, 18}` のいずれか。
- load 時の GPU embedding とホスト dequantize の parity 確認で、8 probe rows 全体の最大絶対差が `1e-6` 以下。
- MTP 自体が load され、draft 呼び出しに `max_steps > 0` がある。

CLI では `--mtp` が指定され、`--spec` が2以上のときに MTP load に進みます。`--mtp` を指定しても `--spec` が2未満なら `--mtp` は無視されます。この変数は Metal engine の実装でのみ参照されます。

## 実行時の詳細

型が対応していれば、load 時に `mtp_chain.metal` を compile し、8 token row で GPU embedding とホストの dequantize 結果を比較します。差が `1e-6` を超えた場合は `chain_` を false に戻し、stderr に `strata metal: the GPU embedding differs from the host's: a command buffer per step` を出します。chain の初期化時には、parity 結果とともに `strata metal: MTP draft round in one command buffer ...` も出力されます。

draft 時は `chain_` が true かつ `max_steps > 0` なら一連の dispatch を組み立てて `run_graph()` を一度呼びます。それ以外は step ごとに `run_graph()` を呼び、GPU の選択結果を読み戻してホストで確率を計算し、次の step に進みます。したがって `=0` は MTP を無効にせず、Metal MTP の実行方法を切り替えます。実行中に環境変数を変更しても、既に load 済みの `chain_` は再判定されません。

## 文書との照合

`docs/MAC.md` は `STRATA_METAL_MTP_CHAIN=0` を「draft step ごとに GPU submission を行う」と説明しており、実装と一致します。同資料にはこの変数による性能測定値は記載されていません。

## 根拠

- `src/program/generate.cpp:4612-4629` — `--mtp` と `--spec` による MTP load 条件。
- `src/core/mtp.cpp:249-257` — Metal build では Metal engine の `mtp_load()` に委譲。
- `metal/src/engine/window.cpp:1578-1615` — 環境変数判定、対応 tensor 型、GPU/host parity 確認、fallback とログ。
- `metal/src/engine/window.cpp:1902-1959` — chain 経路と step ごとの経路。
- `docs/MAC.md:183-192` — 利用者向けスイッチ一覧。
