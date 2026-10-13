# `STRATA_FS_BUDGET`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

Foresight swap space が、1 枚の GPU カードにつき 1 回の完了済み verify window で新たに予約できる expert の非同期コピー数の上限です。cache miss 後の補充コピーと、router look-ahead による予測コピーが同じ上限を共有します。この値は Foresight swap space 自体を有効にするスイッチではありません。CUDA の serve 経路で `STRATA_FS_SLOTS` により swap space が初期化された場合に読み取られます。

## 値と判定

swap space の初期化時に `env_int("STRATA_FS_BUDGET", 32, 1)` で読み取ります。helper は `getenv` の値を `atoi` に渡し、結果の最小値を 1 に clamp します。文字列全体を厳密に検証する parse ではありません。

| 環境値 | 採用される `budget` |
|---|---:|
| 未設定 | 32 |
| 空文字、整数に変換できない文字列、0、負数 | 1（`atoi` の結果が 1 未満なら 1） |
| 正の整数 | その整数 |
| 数字列の後ろに文字が続く | `atoi` が先頭から変換した整数。例: `3tail` は 3、`tail3` は 1 |

先頭空白と符号は `atoi` の規則に従い、大文字小文字の比較はありません。値にコード上の上限 clamp はありません。`atoi` の整数表現範囲を超える文字列の結果は、このコードから保証できません。

## 有効になる条件

- `STRATA_FS_SLOTS` が設定され、`atoi` の結果が 1 以上であること。未設定または 0 以下なら swap space の生成関数は直ちに `nullptr` を返し、`STRATA_FS_BUDGET` を読みません。slots 数は最大 64 に clamp されます。
- `STRATA_VERIFY_DEVICE_PLAN` が設定され、`atoi` の結果が 0 以外の場合は swap space の初期化が抑止されます。stderr に `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN (the device would plan resident layers without the host)` が出ます。
- 初期化が成功しても、各コピーには対象 slot の空きまたは安全な再利用可能性、pinned arena 上の expert source、および expert blob の取得が必要です。条件を満たさない候補はコピーされません。
- 同一カードの全 layer がカード単位の枠を共有します。`STRATA_FS_ADMIT` が有効な miss 回数閾値を設けていても、予算枠はその閾値を通過した要求だけでなく予測要求にも適用されます。

## 実行時の詳細

値は `foresight_swap_from_env()` の初期化中に一度だけ読み、`ForesightSwap::budget` に保存されます。後からプロセス環境を変更しても、すでに作られた swap space には反映されません。初期化成功時の stderr 設定行には `up to %d copies per card and window` の形式で採用値が表示されます。

`request_locked()` は要求時点の完了済み window 数 `now` を読みます。カードごとに保持する `card_round` が `now` と異なるとき、そのカードの `card_used` を 0 に戻します。同じカード・同じ `now` の間に予約済みの要求数が `budget` に達していれば、要求をそこで打ち切って `over_budget` 統計を増やします。空き枠がなかった要求を後の window へ持ち越す処理はありません。予算枠を通過し、source と slot の条件を満たした要求では `card_used` とコピー要求数を増やし、filler thread の queue に入れます。これはコピーの予約数の上限であり、GPU コピーの完了や、その後の window での GPU 利用を保証しません。

serve 側は decode の verify window 完了時に `completed` を増やします。その値を使うため、各カードの枠は完了した window の境界で次の要求群に切り替わります。look-ahead 由来の要求も同じ `request_locked()` を通るため、miss 補充要求との合計がカードごとの枠に収まります。終了時の `foresight swap: ... over budget` 統計は予算で打ち切られた要求数を示します。

## 根拠

- `src/core/expert_source.cpp:4951-4976`: `STRATA_FS_SLOTS` による有効化、`STRATA_VERIFY_DEVICE_PLAN` による抑止、`env_int` の `atoi` と下限 clamp、budget の既定値 32、および初期化ログ。
- `src/core/expert_source.cpp:4887-4936`: 要求ごとの完了 window 数の取得、カード単位の使用数リセット、上限判定、超過統計、source/slot 条件、コピー queue への追加。
- `src/core/expert_source.cpp:4738-4754,4968`: slot 配列とカード単位の `card_round` / `card_used` 初期化、および slots 数の最大値 clamp。
- `src/core/expert_source.cpp:4942-4948`: 終了時レポートのコピー数・予測コピー数・予算超過数。
- `src/core/expert_source.cpp:4881-4885`: 予測コピーも同じ要求処理に渡されること。
- `src/program/generate.cpp:8181-8193,11660-11666,11963-11967`: CUDA serve 経路での swap space 初期化と look-ahead 接続、および decode verify window 完了数の加算。
- `include/strata/core/foresight_swap.hpp:2-21,49-65`: swap space の目的と環境変数の概要。`docs/DETAILS.md:1680-1688` は slots 機能と測定を説明しますが、`STRATA_FS_BUDGET` の parse 規則や枠の集計単位は説明していないため、本書の具体的な挙動は実装に基づきます。
