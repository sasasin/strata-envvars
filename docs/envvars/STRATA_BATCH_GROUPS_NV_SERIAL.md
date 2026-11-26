# `STRATA_BATCH_GROUPS_NV_SERIAL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`--batch-groups` を指定しない layer split の batch で、2 NVIDIA GPU 向けの自動 group 数を 1 にする opt-in です。通常の自動選択は batch slot 数を割り切る GPU stage 数までの group を選びます。この変数が有効な場合、ちょうど 2 stage の layer split ではその自動選択を 1 group に変更し、slot window を各 stage で順番に処理する経路にします。明示的な `--batch-groups auto` は pipeline を要求するため、この変数より優先されます。実読込は `engine/src/program/generate.cpp` の `batch_groups_for`、値の解釈と group 解決は `engine/include/strata/program/batch_groups.hpp` の `nv_serial_wanted` / `resolve` です（`generate.cpp:7803-7820`, `batch_groups.hpp:103-110,122-137`）。

## 値と判定

Strata は `std::getenv` の結果を `nv_serial_wanted` に渡します。helper は文字列全体の parse や大文字小文字変換をせず、未設定 (`nullptr`) または空文字なら `STRATA_DEFAULTS=026` の判定に委ねます。空でない値は先頭文字だけを見て、`'0'` なら無効、それ以外なら有効です。したがって `0`, `0anything` は無効、`1`, `yes`, `true`, `false`, ` 1` は有効です。末尾や数値としての妥当性は検査せず、境界値・負値の数値解釈もありません (`batch_groups.hpp:103-110`)。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_DEFAULTS=026` が off | pipeline 側の自動選択 | `1`, `yes`, `false`, ` 1` | 空文字, `0`, `0anything` |
| `STRATA_DEFAULTS=026` が on | 旧来の 1 group | `1`, `yes`, `false`, ` 1` | 空文字は既定値に従い 1 group、`0`, `0anything` は明示 override で pipeline 側 |

ここで `STRATA_DEFAULTS=026` が on なのは、`STRATA_DEFAULTS` が完全一致で `026`, `0.2.6`, `v0.2.6` のいずれかの場合です。それ以外（未設定、空、`0`, `027` など）は off です。この master switch は初回呼出し時の値を関数内 `static` に cache します (`engine/include/strata/core/defaults_026.hpp:21-30`)。一方、この対象変数自体には cache がなく、`batch_groups_for` の各呼出しで `getenv` されます (`generate.cpp:7803-7817`)。

## 有効になる条件

- `generate` が非 HIP build であること。対象の `std::getenv` と代入は `#if !defined(STRATA_USE_HIP)` 内です (`engine/src/program/generate.cpp:7813-7818`)。
- `--serve` と `--batch` 2 以上が有効で、各 layer split stage が別 GPU に置かれること。batch はこれらの条件を満たさないと停止されます (`generate.cpp:7954-7968`)。
- 2 GPU の layer split（`later_stages == 1`）で、slot 数を 2 で割り切れて自動選択が複数 group になること。通常の自動 group 数は slot 数を割り切る stage 数までの最大値です (`batch_groups.hpp:113-119,126-137`)。
- `--batch-groups` を指定しないこと。数値指定も `auto` 指定も明示指定として扱われ、serial への既定変更は適用されません。特に `--batch-groups auto` は pipeline を選びます (`generate.cpp:4044-4049`, `batch_groups.hpp:126-137`)。
- `--batch-mtp` が有効でないこと、および `--adapt-async 1` でないこと。どちらも対象変数の two-card 分岐を通らず、既定 auto は別の理由で 1 group になる場合があります。`--batch-mtp` と `STRATA_BATCH_MTP_SERIAL` の組合せには先行する serial 選択があります (`generate.cpp:7810-7817`, `batch_groups.hpp:131-136`)。
- `STRATA_DEFAULTS=026` が有効でも、対象変数に空でない値を明示すれば対象変数が優先します。先頭が `0` なら master switch を打ち消し、先頭がそれ以外なら serial を要求します (`batch_groups.hpp:105-110`)。

条件に合わない build / GPU 構成 / batch では、この値自体が有効でも group 解決に反映されません。明示 group 数が layer split を使わない、または batch を割り切らない場合は `WARNING: --batch-groups ... needs a layer split and to divide --batch ...; one group` が出て 1 group に fallback します (`generate.cpp:7994-7999`)。

## 実行時の詳細

`batch_groups_for` は CLI の group 指定、batch 数、stage 数、MTP / async 状態と環境値を `Input` に詰め、`resolve` が group 数を返します。既定自動選択は `--batch-groups` 未指定、layer split あり、batch が 1 より大きい場合に働きます。自動候補が複数 group で、対象変数が有効かつ `later_stages == 1`、MTP off、async off の場合だけ `resolve` は group 数を 1 にします (`generate.cpp:7803-7820`, `batch_groups.hpp:122-137`)。

値は batch setup 中の解決時に読み取られ、解決した `o.batch_groups` が実際の batch loop で使われます。環境変数をリクエストごとに読み直す処理はありません。1 group なら `piped` は false となり、batch window は全 slot をまとめて処理します。複数 group の場合は `GS = o.batch / o.batch_groups` で各 group の slot 数を決め、stage 間で group を pipeline します (`generate.cpp:7975-7999,17529-17538`)。

## ログと測定値

対象の serial 選択で自動 group 数が 1 になると、stderr に次の形式で理由を表示します（`%d` は batch slot 数と pipeline の候補 group 数）。

```text
strata generate: --batch-groups auto: 1 group of N slots - serial windows (STRATA_BATCH_GROUPS_NV_SERIAL=1 or STRATA_DEFAULTS=026 asked for them on two NVIDIA cards; --batch-groups auto pipelines); --batch-groups G asks for the pipelined groups
```

出力箇所は `generate.cpp:7982-7985`、理由文字列は `engine/include/strata/program/batch_groups.hpp:148-150` です。この変数単独の警告や終了経路はありません。明示 `--batch-groups auto` では上記の serial 理由ログは出ず、選ばれた group 数の通常ログになります (`generate.cpp:7977-7992`)。

Strata の `docs/BATCHING.md:474-480` も、0.2.7 以降の二枚 NVIDIA GPU の既定は pipeline、対象変数または `STRATA_DEFAULTS=026` で serial に戻る、と記載しておりソースと整合します。同資料には機種・モデル・設定つきの性能測定がありますが、本調査では再測定していません。速度差を一般化した実測値としては扱いません。

## 根拠

- `engine/src/program/generate.cpp:4044-4049` — `--batch-groups` を明示指定として記録。
- `engine/src/program/generate.cpp:7803-7820` — batch group 入力の構成、対象変数の読込、非 HIP build guard。
- `engine/include/strata/program/batch_groups.hpp:103-119` — 対象値の判定と自動 group 数。
- `engine/include/strata/program/batch_groups.hpp:122-150` — 既定値への適用条件、優先順位とログ理由。
- `engine/include/strata/core/defaults_026.hpp:21-30` — `STRATA_DEFAULTS` の完全一致判定と cache。
- `engine/src/program/generate.cpp:7954-7999,17529-17538` — batch の有効条件、解決ログ、fallback と実行時 group 数。
