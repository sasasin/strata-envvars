# `STRATA_KV_GROW_STEP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

弾力的 K/V（`--kv-grow`）が K/V プールを追加確保するときのセル数の刻み幅を指定する。既定値は 8192 cells で、需要をこの幅の倍数へ切り上げて確保し、`--max-context` を上限にする。変数は `kvg_start` で読み取られ、CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL の `engine/sycl/src/program/generate.cpp` に同じ設定がある（`engine/src/program/generate.cpp:11527-11550`, `engine/sycl/src/program/generate.cpp:6782-6797`）。

これは弾力的 K/V 自体を有効化するスイッチではない。K/V プールが先に elastic として初期化され、`kvg_start` が有効と判断した場合にだけ刻み幅を上書きする。機能の有効化には `--kv-grow` または `STRATA_KV_GROW` が関係する（`engine/src/program/generate.cpp:7715-7732`, `engine/sycl/src/program/generate.cpp:4282-4299`）。

## 値と判定

両実装とも `std::getenv` の結果を `std::atoll` に渡し、変換結果が `> 0` の場合だけ `kvg.step` に代入する。文字列全体の検証はなく、`atoll` が読む先頭の整数部分が正なら後続文字は判定に影響しない。未設定・空文字・数値に変換できない文字列・0・負数は既定の 8192 のまま。例えば `1`、`+16`、` 16tail`、`16tail` は正の値として使われ、`0`、`0tail`、`true`、`-1`、空文字は既定値のままになる。正の値に上限 clamp はない（`engine/src/program/generate.cpp:11531-11533,11550`, `engine/sycl/src/program/generate.cpp:6785-6787,6797`）。

| 条件 | unset / 空文字 | 有効になる値 | 無効値の扱い |
|---|---|---|---|
| `kvg_start` で elastic K/V が有効 | 既定 `8192` cells | `atoll` の変換結果が正の値 | 既定 `8192` cells を維持 |
| `kvg_start` で elastic K/V が無効 | `kvg_start` が早期 return し、変数を読まない | なし | 刻み幅は使われない |

この変数と CLI 引数の優先順位は、`STRATA_KV_GROW` / `--kv-grow` が機能を有効にした後の刻み幅設定である。別の値との上書き関係はなく、正値なら既定の 8192 を置き換える。`STRATA_KV_GROW_INIT` は初期確保セル数、`STRATA_KV_GROW_FLOOR` は cache から K/V に渡す slot の下限を設定する別用途で、step の値を変えない。正値の上限チェックはなく、grow 先の丸め計算も `int64_t` で行われるため、極端に大きな値での算術境界はコード上保証されない（`engine/src/program/generate.cpp:7721-7732,11527-11553,11563-11566`, `engine/sycl/src/program/generate.cpp:4288-4299,6782-6799,6809-6812`）。

## 有効になる条件

- `--kv-grow` または `STRATA_KV_GROW` により弾力的 K/V が要求され、実際に K/V プールが elastic として初期化されていること。`STRATA_KV_GROW` が空でなければ先頭文字が `'0'` でないかで要求を判定し、空または未設定なら CLI 値を使う（`engine/src/program/generate.cpp:7718-7732`, `engine/sycl/src/program/generate.cpp:4285-4299`）。
- エンジン側の要求条件を満たすこと。コードは単一 GPU、`--kv-resident` が無効、expert profile があり、CPU resident experts が無効、expert cache が有効、remote cache がなく、VMM が利用可能で、`--batch`・`--vram-elastic`・`--peer-device` を使わない条件を確認する。要求されているのに条件を満たさない場合は `--kv-grow is off (...)` を stderr に出す（`engine/src/program/generate.cpp:7719-7729`, `engine/sycl/src/program/generate.cpp:4286-4296`）。
- その後の `kvg_start` では、CUDA/HIP 経路は `kv_grow_start` により elastic pool が必要で、cache から slot を借りる場合はさらに VMM range、residency table、expert source、および floor より大きい slot 範囲が必要になる。これらが不足しても elastic pool が有効なら K/V の伸長自体は有効で、cache slot の融通をせず新規 VRAM だけを使う。SYCL 経路も elastic pool、cache の VMM range、device residency table、host residency、expert source、floor 超の slot 範囲を条件に cache 連携を有効化する（`engine/include/strata/core/kv_grow_rules.hpp:18-31`, `engine/src/program/generate.cpp:11541-11551`, `engine/sycl/src/program/generate.cpp:6791-6799`）。
- `STRATA_KV_GROW_STEP` 自体は `kvg.on` の確認後に読み取られるため、弾力的 K/V が無効な経路では効果がない。CLI の直接生成経路と serve のセッション初期化経路から `kvg_start` が呼ばれる（例: `engine/src/program/generate.cpp:13208,24100-24101,24158-24161,24232-24235`; SYCL: `engine/sycl/src/program/generate.cpp:7666,13335-13338,13378-13382,13339-13443`）。

## 実行時の詳細

`kvg.step` は `KvGrow` 状態のメンバーで、初期値 8192。`kvg_start` が elastic pool を確認した後に環境変数を評価する。static cache はなく、`kvg_start` が呼ばれるたびに読み取るが、その後の grow/trim では保存済み `kvg.step` を使うため、実行中に環境を変更しても既存の `kvg` 状態には反映されない（`engine/src/program/generate.cpp:11527-11553,11563-11566,11678-11685`; SYCL: `engine/sycl/src/program/generate.cpp:6782-6799,6809-6812,6963-6967`）。

K/V を `cells` まで伸ばす際、通常の CUDA/HIP 経路は `kv_grow_target(cells, kvg.step, o.max_context)` で次の step 境界へ切り上げる。SYCL も同じ計算を行う。結果は `o.max_context` で制限される。必要な K/V が現在の容量以下なら grow を行わず、step は使われない（`engine/include/strata/core/kv_grow_rules.hpp:34-37`, `engine/src/program/generate.cpp:11563-11567`, `engine/sycl/src/program/generate.cpp:6809-6813`）。

```text
target = min(max_context, ceil(cells / step) * step)
```

通常の CUDA/HIP 経路では、grow 前に実行中の device 作業を quiesce し、必要に応じて expert cache の slot/chunk を K/V に渡した後、elastic pool を grow する。cache 条件を満たさない場合は新規 VRAM から伸長する。SYCL 経路も grow 前に queue を待ち、必要な cache chunk を調整してから pool を grow する（`engine/src/program/generate.cpp:11561-11575,11649-11674`, `engine/sycl/src/program/generate.cpp:6807-6821,6927-6959`）。

## ログと測定値

この変数で選ばれた `step` の数値を直接出力するログはない。cache 連携が使われる場合、初期化時に `strata generate: elastic K/V: ...` が stderr に出る。grow 後は `strata: K/V grown to ...` が出て、失敗時には `strata: the K/V could not grow to ...` が続く。expert 移動や residency table upload の失敗もそれぞれ `strata: moving experts for the K/V failed: ...`、`strata: the residency table upload failed: ...` と出力する（`engine/src/program/generate.cpp:11554-11559,11632-11645,11665-11674`; SYCL: `engine/sycl/src/program/generate.cpp:6800-6805,6889-6925,6937-6959`）。

grow が失敗した場合、呼び出し元は生成処理から終了コード `1` で戻る（例: `engine/src/program/generate.cpp:24100-24101,24158-24161,24232-24235`; SYCL: `engine/sycl/src/program/generate.cpp:13335-13338,13378-13382,13439-13443`）。測定値は記載しない。

## 根拠

- 候補名の全参照: `engine/src/program/generate.cpp:11550`, `engine/sycl/src/program/generate.cpp:6797` が実際の `std::getenv` 読み取り。`terminal/data/settings-register.json:20208` にも名前があるが、実行時の読み取りではない。
- 値の既定値・判定・step 境界: `engine/src/program/generate.cpp:11527-11550,11563-11566`, `engine/sycl/src/program/generate.cpp:6782-6797,6809-6812`。
- 有効化条件・関連設定: `engine/src/program/generate.cpp:7715-7732`, `engine/sycl/src/program/generate.cpp:4282-4299`, `engine/include/strata/core/kv_grow_rules.hpp:18-37`。
- grow の実行・結果: `engine/src/program/generate.cpp:11649-11674`, `engine/sycl/src/program/generate.cpp:6927-6959`。
