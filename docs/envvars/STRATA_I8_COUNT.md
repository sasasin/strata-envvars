# `STRATA_I8_COUNT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

prompt prefill の chunk-major 経路で、group walk に到達した層と routed entry のうち、`native_expert_i8` と group walk 内の他カーネル（MMQ または FP16 path）に進んだ数を数え、chunk ごとに stderr へ診断行を出します。コードコメントは結果に影響しない診断と明記しています。環境変数はカーネル選択を変えず、診断カウンターの更新と出力だけを有効にします（`src/prefill/prefill.cpp:1865-1875,6012-6023,7267-7275`）。

## 値と判定

`i8_count_on()` は `std::getenv` の結果を `std::atoi` に渡し、変換結果が 0 でなければ有効とします。値全体の厳密な検証はしません。したがって未設定は無効、空文字も `atoi` が 0 を返すため無効です。`0`、`0anything`、`true`、数値で始まらない文字列は無効です。`1`、`2`、`-1`、`1anything` は変換結果が非 0 なので有効です。`atoi` の規則に従い先頭空白や符号を許容し、数値として読める先頭部分の後ろは判定に使いません。値域の clamp や変換失敗のエラー処理はありません（`src/prefill/prefill.cpp:1867-1869`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `i8_count_on()` が呼ばれる実行ファイル | `false` | `1`、`-1`、`1tail`（`atoi` 結果が非 0） | 空文字、`0`、`0tail`、`true`、`tail` |

## 有効になる条件

- 診断処理は `src/prefill/prefill.cpp` の GPU prefill 実装にあります。同ファイルは `strata_prefill` ターゲットに含まれます（`cmake/strata_gpu_engine.cmake:444`）。Metal 経路は `Prefill::run` 内で別の prompt runner を呼んで先に return するため、この診断出力を通りません（`src/prefill/prefill.cpp:8967-8985`）。
- 通常の `run_impl` による chunk-major prompt 処理が診断の対象です。`STRATA_PREFILL_LAYER_MAJOR` などで layer-major 経路が選ばれ `run_layer_major` が成功すると、そこから return するため本カウンターと出力は通りません（`src/prefill/prefill.cpp:7817,8991-9029`）。
- 集計は group walk に到達した層について行われます。個々の層で native int8 経路を採るかどうかは別判定です。たとえば、native layout、fused/staged entry や WMMA/Hadamard 経路との競合、CPU share・peer・`m.pp`・group buffer 等の条件、`STRATA_PREFILL_GROUP_GATHER`、デバイスと layout の対応が関係します（`src/prefill/prefill.cpp:5966-5999`）。そのため有効な診断値を設定しても、対象層が group walk に到達しない場合や `native_expert_i8` が選ばれない場合があります。
- `STRATA_PREFILL_GROUP_GATHER` は unset または `atoi` が非 0 の場合に int8 group 経路を許します。`0` ならその経路の条件を満たさず、診断の `native_expert_i8` 件数にも反映されません（`src/prefill/prefill.cpp:5974-5977,5982-5990`）。

## 実行時の詳細

`i8_count_on()` の関数内 `static const bool` が最初に評価された時点で環境を読み、プロセス内に cache します。最初の呼び出し以後に環境を変更しても判定は変わりません。CLI 引数や設定ファイルによる上書きはこのコードにはありません（`src/prefill/prefill.cpp:1867-1869`）。

有効時、group walk に到達した層ごとに層数と routed entry 数を加算し、int8 選択数、int8 groups、最小の group 平均 entry 数、few-rows grouped route の数を記録します。`few-rows` は int8 層の内数として加算されます。chunk の処理が報告箇所まで到達すると stderr に `strata i8-count: chunk of ...` で始まる行を出し、その後カウンターをゼロ初期化します。chunk 処理がその箇所より前に失敗・return する場合は、その行は出ません（`src/prefill/prefill.cpp:6012-6023,7267-7275`）。

## ログと測定値

有効時のログは次の書式です（数値部分は実行時の集計値）。`elsewhere in the walk` は routed entry 総数から `native_expert_i8` の entry 数を引いた値です。

```text
strata i8-count: chunk of %lld tokens: %lld layers reached the group walk, %lld on native_expert_i8; routed entries %lld, on native_expert_i8 %lld (%.2f %%), elsewhere in the walk %lld; i8 groups %lld; smallest group average seen %lld entries; few-rows route (grouped kernels, counted in the int8 ones): %lld layers, %lld entries
```

出力先は `stderr` です。変数が無効ならカウントとこのログは行いません。関連資料にこの変数の性能測定値は確認できません（ログ書式と集計処理: `src/prefill/prefill.cpp:7267-7275`）。

## 根拠

- 値の読み取り・parse・cache、診断用途の説明: `src/prefill/prefill.cpp:1865-1875`
- group walk での集計条件とカウンター更新: `src/prefill/prefill.cpp:5966-6023`
- chunk ごとの stderr 出力と reset: `src/prefill/prefill.cpp:7267-7275`
- layer-major / Metal の別経路: `src/prefill/prefill.cpp:8967-8985,8991-9029`
- prefill ソースの GPU ターゲット登録: `cmake/strata_gpu_engine.cmake:444`
