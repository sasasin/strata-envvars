# `STRATA_KV_GROW_STEP`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

elastic K/V（`--kv-grow`）が VRAM に追加確保するセル数の刻み幅を指定します。K/V を要求量に合わせて拡張するときと、要求が小さくなって K/V の VRAM を expert cache に返すときの丸め単位に使われます。K/V 拡張機能そのものを有効にするスイッチではありません。

## 値と判定

`kvg_start()` が `STRATA_KV_GROW_STEP` を `std::atoll()` で読み、変換結果が正のときだけ `kvg.step` に採用します。既定値は `8192` セルです。

| 環境変数の値 | 結果 |
|---|---|
| 未設定 | 既定の `8192` セル |
| 空文字、数値に変換できない文字列、`0` または負数 | 既定の `8192` セル |
| 正の整数 | その値をセル数として採用 |
| 数字の後ろに別の文字が続く値 | `atoll()` が読めた先頭の整数が正なら採用（例: `4096tail` は `4096`） |

全体の文字列一致や厳密な数値 parse、上限 clamp はありません。`atoll()` のため、先頭の空白や符号も整数変換の規則に従います。値の単位はバイトではなく K/V のセル数です。

## 有効になる条件

この値が使われるのは、elastic K/V が有効な場合だけです。起動時の有効条件は、`--kv-grow` または `STRATA_KV_GROW` による要求に加え、単一 GPU、expert profile、全 K/V が VRAM にあること、全 expert が RAM にあること、expert cache の利用、VMM 対応が必要で、`--batch`、`--vram-elastic`、`--peer-device` は併用できません。条件を満たさない場合、要求があれば stderr に `--kv-grow is off (...)` を出し、`STRATA_KV_GROW_STEP` は適用されません。

さらに、K/V 初期化後の `kvg_start()` では、elastic K/V、cache の VMM range、device residency table、resident expert 情報、expert source が揃い、対象 cache 領域が既定 floor の 128 slots より大きい場合にだけ `kvg.step` を読みます。CUDA と SYCL の `generate.cpp` に同じ判定があります。

## 実行時の詳細

`kvg_ensure(cells, ...)` は、現在の K/V より多くのセルが必要な場合に `cells` を `kvg.step` の倍数へ切り上げ、`--max-context` を上限として K/V pool を拡張します。したがって大きい step は拡張時に要求量より多くのセルをまとめて確保し、小さい step はより細かい単位で確保します。セルが現在量以下なら何もしません。

request 間の trim も同じ step で切り上げた目標量を使います。十分に余剰がある場合にだけ、K/V pool の後半を unmap して cache に戻し、expert を補充します。そのため step は grow と trim の両方の粒度および trim 判定に影響します。grow/trim は実際に動く場合、stderr に K/V のセル数や cache slot の移動を出します。終了時には elastic K/V の現在セル数、grow/trim 回数、退避・再補充した expert 数が表示されます。

値は `kvg_start()` の実行時に通常一度だけ読み、その後の request ごとには読み直しません。実行中に環境変数を変更しても、そのプロセスの `kvg.step` には反映されません。子プロセスへの転送処理はこの変数について見つかりませんでした。

## 根拠

- `src/program/generate.cpp:6401-6418` — 既定値、elastic K/V の開始条件、環境変数の parse。
- `src/program/generate.cpp:6426-6432,6510-6528` — 要求セル数の切り上げと grow 処理。
- `src/program/generate.cpp:6530-6541` — trim 目標値の切り上げと K/V shrink。
- `src/program/generate.cpp:4221-4238` — `--kv-grow` / `STRATA_KV_GROW` の有効条件と VMM 初期化。
- `src/program/generate.cpp:10215-10221,10362-10365,11891-11896` — request、parked conversation、decode window での grow 呼び出し。
- `src/program/generate.cpp:10438-10448,13391-13394` — request 間の trim と終了時の統計。
- `sycl/src/program/generate.cpp:3768-3785,6056-6087,6238-6242` — SYCL 側の同等実装。
- `src/core/layer.cpp:576-603`, `sycl/src/core/layer.cpp:659-705` — elastic K/V の pool 単位の grow/shrink。
- `docs/DETAILS.md:260-264` — `--kv-grow` の概要と適用条件。step の値域や parse 規則は説明していないため、値の判定は実装に基づく。
