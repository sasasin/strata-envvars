# `STRATA_ADAPT_FETCH_MARGIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

PCIe share で取得した未常駐 expert を VRAM cache に直接 admission する際、取得候補の routing count が置換対象の resident expert よりどれだけ多ければ入れ替えるかを指定する差分閾値です。候補 `e` と置換対象 `v` について `use[e] >= use[v] + fetch_margin` のとき admission されます。閾値を変えるだけで、PCIe share の候補選択や `STRATA_ADAPT_FETCH` の有効化自体は変えません（`engine/src/core/expert_source.cpp:5640-5676`、`engine/include/strata/core/expert_source.hpp:674-680`）。

値を読むのは CUDA/HIP 系 engine の `strata serve` と `strata generate` です。SYCL と Metal は別 engine として構成されており、この読み取り箇所はありません（`engine/src/program/generate.cpp:15083-15088,24596-24602`、`engine/CMakeLists.txt:1-7,126-150`）。

## 値と判定

両実行経路とも `getenv` が null でなければ `std::atof` で変換し、`float` に cast して `drive.d.fetch_margin` に設定します。null（未設定）なら `ExpertDispatch` の初期値 `0.5f` が使われます。空文字は設定済みなので `atof("")` の結果 0 が設定されます。文字列全体の妥当性検査、後続文字の拒否、範囲確認、clamp、変換失敗時の警告はありません（`engine/src/program/generate.cpp:15084,24597`、`engine/include/strata/core/expert_source.hpp:679-680`）。

| 条件 | unset | 有効になる値の例 | 値として受理されるが意味に注意する例 |
|---|---|---|---|
| `strata serve` / `strata generate` の fetch 初期化まで到達 | `0.5` | `0.5`, `1`, `-1`, `1.25` は `atof` の数値変換結果 | 空文字、`true`、`n/a` は `0`。`0anything` は先頭の数値 `0`。前後の空白や数値の後ろの文字列も `atof` の規則で処理される |

`atof` は数値の後ろを含めた文字列全体を検査しません。したがって、たとえば `1.5junk` は先頭の数値部分を変換し、数値として始まらない文字列は 0 になります。`nan` / `inf` なども変換関数に渡され、Strata 独自の有限値検査はありません。境界は許容範囲として定義されておらず、負値も拒否されません。実際に admission されるかは後述の比較と他の条件によります（`engine/src/program/generate.cpp:15084,24597`、`engine/src/core/expert_source.cpp:5663-5676`）。

## 有効になる条件

- `STRATA_ADAPT_FETCH` が正の値である必要があります。これは別の設定で、`adapt_fetch()` がプロセス内 static 値として読む値です。GPU 既定値の適用で同変数が設定される構成もあります。margin を指定しても fetch 自体は有効になりません（`engine/src/program/generate.cpp:2345-2347,15067-15084,24580-24597`）。
- GPU 既定値による親機能の有効化は compute capability 12.x で VRAM 16 GiB 以下、または sm_86 / sm_89 で 13 GiB 以下のカードが対象です。既に `STRATA_ADAPT_FETCH` が設定済みならその値を残し、既定値で上書きしません。`STRATA_DEFAULTS=026` 等で既定表が無効化された場合も自動設定されません（`engine/include/strata/core/nv_defaults.hpp:27-37`、`engine/src/core/nv_defaults.cpp:21-27,222-238`）。
- 適応 tier の routing 使用量があり、residency table と VRAM cache slot が必要です。serve はさらに `--spec-split`、layer split / 複数 GPU、`--peer-device`、helper GPU、`--adapt-async`、`--pipeline-windows`、`--batch`、`STRATA_ADAPT_OVERLAP=1` の各経路では fetch を無効扱いにします（`engine/src/program/generate.cpp:15055-15080`）。generate は `--spec-split`、layer split、peer tier、helper GPU を無効理由として判定します（同 `24571-24593`）。
- admission 側には GPU plan、正の PCIe share、PCIe mode 2、および対象 layer の PCIe source が必要です。`--pcie-mode dma` / `direct` では設定ブロックが fetch を無効扱いにし、`ExpertDispatch::fetch_can` も `plan->pcie_mode == 2` を要求します（`engine/src/program/generate.cpp:15067-15084,24580-24597`、`engine/src/core/expert_source.cpp:5271-5275`）。
- 現在の window で PCIe fetch が発生し、候補が未常駐・pinned であること、候補の routing count が `STRATA_ADAPT_FETCH_MIN` 以上でコピー中でないこと、置換先が resident・現在の window で未使用・保護対象でないことが必要です。これらを満たす候補と置換先を routing count 順に比較し、margin 以上の差がある場合だけ slot を引き継ぎます（`engine/src/core/expert_source.cpp:5555-5572,5637-5676`）。

## 実行時の詳細

`strata serve` と `strata generate` は初期化時に fetch が使用可能と判定された場合だけ margin を読み、`ExpertDispatch` に保存します。serve では server engine 初期化の設定、generate では実行開始時の設定です。margin 自体を static cache するコードはなく、各経路の初期化で一度読みます。環境を実行中に変更して反映する処理はありません。`STRATA_ADAPT_FETCH` の static cache とは別の読み取りです（`engine/src/program/generate.cpp:2345-2347,15067-15088,24580-24602`）。

各 window の PCIe share は layer の未常駐 miss のうち routing count が高いものを選びます。取得後、候補を `fetch_min` 以上の使用量で絞り、window 内で使っていない resident expert のうち使用量が低いものを置換先に選びます。候補 `e` が `use[e] < use[v] + fetch_margin` ならその比較以降の admission を止め、そうでなければ候補を置換先の VRAM slot に割り当て、host residency table を更新します。つまり margin は置換差の閾値で、未設定時の 0.5 は routing count の差が 0.5 以上という比較です（`engine/src/core/expert_source.cpp:5640-5676`）。

## ログと測定値

fetch 初期化が有効なら stderr に `strata serve: STRATA_ADAPT_FETCH=%d: the PCIe share takes each layer's most-routed misses and admits those routed >= %.2f and %.2f more than a resident one%s` または `strata generate: ...` が出て、実効 `fetch_min` と margin を小数 2 桁で表示します。fetch が実行条件を満たさないときは `STRATA_ADAPT_FETCH is off (<理由>)`、GPU 既定値で有効化された値が使えないときは `STRATA_ADAPT_FETCH=2 (the default for this card) is not used in this run (<理由>)` が出ます。margin の無効値専用警告やエラーはありません（`engine/src/program/generate.cpp:15073-15088,24587-24602`）。

`docs/DETAILS.md:1262` は fetch 機能全体の構成例と測定値を記録し、margin の既定値を `0.5` としています。ただし掲載された性能値は fetch の複数条件をまとめた結果で、margin 単独の効果を分離した測定ではありません。そのため、この変数単独の性能向上値としては記載しません。

## 根拠

- `engine/src/program/generate.cpp:2345-2347` — 親機能 `STRATA_ADAPT_FETCH` の static 読み取り。
- `engine/src/program/generate.cpp:15055-15088` — serve 側の fetch 条件、margin 読み取り、設定ログ。
- `engine/src/program/generate.cpp:24571-24602` — generate 側の fetch 条件、margin 読み取り、設定ログ。
- `engine/include/strata/core/expert_source.hpp:674-692` — dispatch の既定値と margin の役割。
- `engine/src/core/expert_source.cpp:5271-5275,5555-5572,5637-5679` — admission 前提、候補選択、閾値比較、residency 更新。
- `engine/CMakeLists.txt:1-7,126-150` — CUDA/HIP engine と別 backend の構成。
- `docs/DETAILS.md:1262` — fetch の説明と条件付き測定値（margin 単独の測定ではない）。
