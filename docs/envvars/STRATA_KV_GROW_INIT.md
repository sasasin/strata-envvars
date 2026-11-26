# `STRATA_KV_GROW_INIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--kv-grow` で有効になる elastic K/V の初期 VRAM 割当セル数を指定する。CUDA/HIP 共通の `engine/src/program/generate.cpp` と SYCL の `engine/sycl/src/program/generate.cpp` が読み、`qsa_set_kv_elastic` に渡す。elastic K/V が無効でもこの変数は読み取られ初期セル数のグローバル値を更新するが、その値を使った pool 作成は行われない。成長機能の有効化は別設定 `--kv-grow` / `STRATA_KV_GROW` と複数条件で決まり、この変数単独では有効にならない（`engine/src/program/generate.cpp:7715-7732`、`engine/sycl/src/program/generate.cpp:4282-4299`）。

## 値と判定

両実装とも `std::getenv` の戻り値を `std::atoll` に渡し、変換結果が正のときだけ採用する。未設定、空文字、数値に変換できない文字列、0、負値は既定値 `16384` にフォールバックする。`atoll` は文字列全体の厳密な数値検証には使われておらず、数値の後ろに文字がある場合も数値部分を変換する（例: `12000tail` は 12000）。先頭空白と符号も `atoll` の変換規則に従う。大文字小文字の区別は該当しない。整数範囲を超える入力の結果はコードで検証・規定されていない。採用値に対する `max_context` との clamp はこの読み取り箇所にはないが、pool の初期 mapping は pool の slot 数を超えない（`engine/src/program/generate.cpp:7730-7732`、`engine/sycl/src/program/generate.cpp:4297-4299`、`engine/src/core/layer.cpp:638-640,654-656`、`engine/sycl/src/core/layer.cpp:593-595,609-612`）。

| ビルド経路 | unset | 設定時に採用される値 | 既定値へ戻る値 |
|---|---|---|---|
| CUDA / HIP | 16384 cells | `atoll(value) > 0` の整数。例: `1`, `16384`, `12000tail` | 空文字、`0`, `-1`, `true`, `n/a` |
| SYCL | 16384 cells | `atoll(value) > 0` の整数。例: `1`, `16384`, `12000tail` | 空文字、`0`, `-1`, `true`, `n/a` |

## 有効になる条件

- 起動経路は `strata generate`。変数は同じ `generate.cpp` の session 構築ブロックで読み取られる（`engine/src/program/generate.cpp:7712-7732`、`engine/sycl/src/program/generate.cpp:4280-4299`）。
- 初期セル数が実際の pool 割当に使われるのは `qsa_set_kv_elastic` が elastic 状態を有効にした場合。上位判定は `--kv-grow` または `STRATA_KV_GROW` の要求に加えて、単一 GPU、K/V streaming 無効、expert profile あり、CPU resident experts 無効、expert cache 有効、remote expert cache なし、VMM 利用可能、`--batch` 無効、`--vram-elastic` 無効、`--peer-device` 未指定を要求する（`engine/src/program/generate.cpp:7718-7729`、SYCL: `engine/sycl/src/program/generate.cpp:4285-4296`）。
- `STRATA_KV_GROW` が空または未設定なら CLI の `o.kv_grow` が使われる。空でない値は先頭文字だけを見て、`'0'` 以外なら要求扱い（`engine/src/program/generate.cpp:7718-7726`、SYCL: `engine/sycl/src/program/generate.cpp:4285-4293`）。
- elastic 状態が有効でなければ `STRATA_KV_GROW_INIT` の正値を設定しても初期 elastic pool は作られず、その値による K/V 拡張も起きない（`engine/src/core/layer.cpp:680-683,828-849`、SYCL: `engine/sycl/src/core/layer.cpp:657-660,798-819`）。
- `kv_grow_start` / `kvg_start` にはさらに cache の VMM range、residency table、expert source 等の条件があり、expert cache からの slot 再利用ができない場合は新規 VRAM で拡張する経路となる（`engine/include/strata/core/kv_grow_rules.hpp:23-31`、`engine/src/program/generate.cpp:11541-11552`）。この初期値はそれらの cache 条件を変更しない。

## 実行時の詳細

環境変数は session 状態の確保直前に同期的に一度読み取られ、`qsa_set_kv_elastic(on, 初期セル数)` が共有状態を設定する。設定後にプロセス環境を変更しても、この起動済み generate 処理の初期値には反映されない。`qsa_set_kv_elastic` は `enabled && vmm_available()` を有効状態として保存し、正の初期値を `g_kv_elastic_init` に保存する（`engine/src/program/generate.cpp:7712-7734`、`engine/src/core/layer.cpp:624-626,680-684`。SYCL: `engine/sycl/src/program/generate.cpp:4280-4303`、`engine/sycl/src/core/layer.cpp:579-581,657-661`）。

有効な場合、各 QSA state の K/V pool は全 context 分の仮想範囲を予約し、初回は `g_kv_elastic_init` cells 分の slot を物理 mapping する。セル数は `pool_slots` 内でページ単位に切り上げられ、pool の slot 数を上限にする。以後、要求に必要なセル範囲が mapped 範囲を超えると `kvg_ensure` が必要範囲を拡張し、設定済みの grow step や cache 状態に従って mapping する（`engine/src/core/layer.cpp:638-676,807-849`、`engine/src/program/generate.cpp:11561-11568,11649-11674`。SYCL: `engine/sycl/src/core/layer.cpp:593-648,777-819`、`engine/sycl/src/program/generate.cpp:6807-6813`）。

## ログと測定値

この変数の値自体を表示する専用ログはない。elastic 初期 pool の予約または mapping に失敗すると `strata: the elastic K/V could not reserve or map its pools` を出し、QSA state 初期化失敗として `strata generate: session_init failed` を出して終了コード 1 で戻る（`engine/src/core/layer.cpp:847-849`、`engine/src/program/generate.cpp:7738-7740`）。SYCL でも同じ予約・mapping 失敗文言を出して session 初期化失敗経路に入る（`engine/sycl/src/core/layer.cpp:817-819`、`engine/sycl/src/program/generate.cpp:4308-4310`）。後続の拡張時には mapping 不足や chunk 初期化失敗、拡張失敗の診断が出る（CUDA/HIP: `engine/src/core/layer.cpp:663-674`、`engine/src/program/generate.cpp:11649-11674`。SYCL: `engine/sycl/src/core/layer.cpp:619-645`）。この変数自体について Strata の測定値は記載されていない。

## 根拠

- CUDA/HIP の読み取り、既定値、elastic gate: `engine/src/program/generate.cpp:7712-7734`
- SYCL の読み取り、既定値、elastic gate: `engine/sycl/src/program/generate.cpp:4280-4303`
- 初期値の保存と pool 初期 mapping: `engine/src/core/layer.cpp:624-626,638-676,680-684,807-849`、`engine/sycl/src/core/layer.cpp:579-581,593-648,657-661,777-819`
- grow 条件と実行時拡張: `engine/include/strata/core/kv_grow_rules.hpp:23-31`、`engine/src/program/generate.cpp:11541-11568,11649-11674`、`engine/sycl/src/program/generate.cpp:6791-6813`
