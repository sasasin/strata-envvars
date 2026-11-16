# `STRATA_SYCL_PREFILL_COPY_PROFILING`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の prefill 経路で expert 転送用 queue を選ぶとき、専用 copy-engine queue が得られなかった場合の queue profiling 有無を切り替える。環境変数が文字列として厳密に `0` の場合、Strata は profiling property を付けない in-order queue を作って `m.copy` に設定する。expert データの転送自体を無効にする設定ではない。`Prefill::init` が判定し、通常の expert copy と barrier は選ばれた `m.copy` を使う（`sycl/src/prefill/prefill.cpp:1346-1357,2969-2993,4351-4385`、`sycl/include/strata/prefill_copy_queue.hpp:7-12`）。

## 値と判定

`Prefill::init` ごとに `std::getenv` で読み、未設定かどうかを確認したうえで `std::strcmp(value, "0") == 0` と比較する。数値変換はせず、空白除去、大文字小文字変換、先頭文字だけの比較もない（`sycl/src/prefill/prefill.cpp:1350-1353`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `m.copy == nullptr` のとき | 通常の `create_queue(true)` に進む | `0`（完全一致）で非 profiling queue を選ぶ | 空文字、`00`、`0anything`、` 0`、`0 `、`1`、`true`、`false` など。通常 queue に進む |
| 専用 copy-engine queue が作られたとき | その queue を使う | 該当なし。値は参照されるが条件により使われない | 該当なし |

この設定による判定結果は `Prefill::init` 内で保存されるが、環境変数そのものを static cache するコードはない。次回の `init` では再読込する（`sycl/src/prefill/prefill.cpp:1350-1353`）。

## 有効になる条件

- Strata の SYCL prefill 実装を通ること。prefill の初期化は SYCL 生成経路から呼ばれ、初期化失敗は `strata generate: ...` と stderr に出して終了コード 1 で返る（`sycl/src/program/generate.cpp:12949-12955`）。
- `strata::make_copy_engine_queue` が `nullptr` を返すこと。たとえば `STRATA_COPY_ENGINE=0`、Level Zero 以外の backend、copy-engine 用 API がビルドに含まれない、Battlemage 以外で強制指定がない、`SYCL_UR_USE_LEVEL_ZERO_V2=0`、または専用 queue を作れない場合に `nullptr` となる（`sycl/src/core/copy_queue.cpp:73-100,105-113,123-138`）。専用 queue が返れば、この変数の値にかかわらずその queue を使う。
- 専用 queue を抑止する `STRATA_COPY_ENGINE` は helper 内で static に一度読まれ、先頭文字が `0` なら無効化する。`STRATA_SYCL_PREFILL_COPY_PROFILING` は完全一致で `0` を判定するため、両変数の値規則は異なる（`sycl/src/core/copy_queue.cpp:73-75`、`sycl/src/prefill/prefill.cpp:1350-1353`）。
- unset または厳密な `0` 以外の場合は `dpct::device::create_queue(true)` に進む。この prefill translation unit は `DPCT_PROFILING_ENABLED` を定義しており、通常 queue の生成 helper はその macro がある場合に profiling property を付ける。厳密な `0` の分岐で作る独自 queue にはその property を付けない（`sycl/src/prefill/prefill.cpp:1-4,1351-1357`、`sycl/include/dpct/device.hpp:617-629,679-700`）。

## 実行時の詳細

`Prefill::init` はまず `make_copy_engine_queue("the prompt path's expert")` を試す。その結果が null で、かつ対象変数が厳密な `0` の場合、`make_prefill_copy_queue(*m.cs)` を作って所有ポインタを `copy_without_profiling` に保持し、その queue を `m.copy` に割り当てる。この queue は compute queue と同じ context/device、同じ DPCT exception handler を使う in-order queue で、profiling property は指定しない。条件に合わない場合は通常の `create_queue(true)` を使い、それも失敗扱いになれば `err = "prefill: copy stream"` で初期化を失敗させる（`sycl/src/prefill/prefill.cpp:1346-1357`、`sycl/include/strata/prefill_copy_queue.hpp:9-12`）。

選ばれた `m.copy` は、resident でない expert blob の host-to-device `memcpy` と、staging slot の前後関係を保つ barrier に使われる。対象変数が変更するのはこの転送 queue の profiling property で、コピー対象や queue ordering を変える分岐はない（`sycl/src/prefill/prefill.cpp:2969-2993,4351-4385`）。読み取りは初期化時で、リクエストごとではない。プロセス実行中に環境を変更しても初期化済みの `m.copy` は切り替わらず、新しい `Prefill::init` で読み直される。

## ログと測定値

この変数を読んだり、非 profiling queue を選んだりしたことを示す専用ログはない。専用 copy-engine queue が使われる場合は `strata: copy engine: ...`、queue 作成時の例外で専用 queue を使えない場合は `strata: copy engine queue not available (%s): ordinary queue` を stderr に出す。いずれも対象変数固有のログではない（`sycl/src/core/copy_queue.cpp:130-137`）。通常 queue の作成に失敗した場合は初期化エラー `prefill: copy stream` が上位で `strata generate: ...` と表示される。後続の copy queue wait が失敗した場合は `prefill: expert copy stream: ...` を返す（`sycl/src/prefill/prefill.cpp:1355-1357,5210-5221`、`sycl/src/program/generate.cpp:12951-12955`）。

`docs/DETAILS.md` など調査対象資料には、この変数による性能測定値を確認できなかった。ソースコメントにある copy-engine 関連の説明は、この変数の測定値ではないため転記していない。

## 根拠

- 候補名の実読み取りと厳密一致判定: `sycl/src/prefill/prefill.cpp:1350-1357`
- 非 profiling queue の構築: `sycl/include/strata/prefill_copy_queue.hpp:7-12`
- copy-engine queue の戻り条件・fallback・ログ: `sycl/src/core/copy_queue.cpp:73-100,105-138`
- queue profiling property の通常経路: `sycl/src/prefill/prefill.cpp:1-4`、`sycl/include/dpct/device.hpp:617-629,679-700`
- expert copy queue の使用箇所・wait の失敗経路: `sycl/src/prefill/prefill.cpp:2969-2993,4351-4385,5210-5221`
- 初期化呼び出しと上位のエラー出力: `sycl/src/program/generate.cpp:12949-12955`
