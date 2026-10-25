# `STRATA_PREFILL_AUTO_MAX`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。対象リポジトリの作業ツリーは調査時点で clean。外部ライブラリの環境変数の動作は対象外。

## 役割

`--prefill auto` が選ぶ prompt 処理 chunk の上限を指定します。既定の上限は 8,192 tokens で、この変数を使うと 16,384 または 32,768 tokens まで auto の候補を広げられます。実際にその大きさが使われるかは別途、context、expert cache の空き、prompt buffer の必要量などで決まります。

環境変数を読む実装は CUDA 系の `src/program/generate.cpp` と SYCL 系の `sycl/src/program/generate.cpp` の `--prefill` 引数解析にあります。設定値は起動時の引数解析時に `Options` へ取り込まれます。リクエストごとの再読み込みや、起動後に環境を書き換えた場合の反映はありません。

## 値と判定

両実装とも `std::atoll` で整数変換し、値を次の3段階に丸めます。文字列全体の厳密な検証はしません。

| `--prefill` の値 | `STRATA_PREFILL_AUTO_MAX` | 設定される上限 |
|---|---|---:|
| `auto` | 未設定 | 8,192 |
| `auto` | `atoll` の結果が 16,384 未満 | 8,192 |
| `auto` | `atoll` の結果が 16,384 以上 32,768 未満 | 16,384 |
| `auto` | `atoll` の結果が 32,768 以上 | 32,768 |
| `auto:N` | 任意 | 環境変数を無視し、`N` を同じ3段階で丸める |
| 数値など `auto` 以外 | 任意 | 環境変数は chunk 値に影響しない |

環境変数が空文字、数値で始まらない文字列、または負値なら `atoll` の結果は 0 以下となり、上限は 8,192 です。`atoll` は数値の後ろの文字列を検査しないため、たとえば `16384tail` は 16,384 として扱われます。値を 8,192 未満に指定しても、auto の上限は 8,192 より小さくなりません。範囲外をエラーにする処理はありません。

## 有効になる条件

この変数が chunk の選択上限に使われるのは、`--prefill auto` を指定し、`--prefill auto:N` のような CLI 上限を指定していない場合です。`--prefill` 自体を指定しなければ、環境変数を使った上限設定は行われません。

CUDA 系では、環境変数が設定されているかどうかも platform 固有の既定値判定に関わります。

- **Windows HIP**: 変数が未設定の裸の `--prefill auto` は host limit により 6,144 tokens に制限されます。変数を設定すると、値が空や不正で結果的に上限 8,192 になっても「裸の auto」ではない扱いとなり、この 6,144 上限は適用されません。`auto:N` も裸の auto ではありません。ユーザー指定 chunk が 8,192 以上の場合は、警告を出したうえで要求値を維持する経路があります。
- **Linux HIP の gfx12**: 裸の `--prefill auto` は、GPU 世代と `STRATA_GFX12_CHUNK` / `STRATA_GFX12_DEFAULTS` の条件により 16,384 へ引き上げられることがあります。`STRATA_PREFILL_AUTO_MAX` が設定されていると裸の auto ではなくなるため、この既定値引き上げは行われません。したがってこの変数を空や不正値で設定した場合は 8,192 上限のままです。
- **その他の CUDA/HIP/SYCL 経路**: 直接の値判定は上表どおりです。最終 chunk は後段の実行条件によってさらに小さくなる場合があります。

## 実行時の詳細

auto chunk planner は `prefill_auto_max` を上限として、expert cache から prompt buffer 用領域を借りられる最大 chunk を選びます。通常の scan は 256-token 単位で上限まで候補を調べ、必要 buffer と貸出可能 slot の条件を満たす最大値を採ります。ring byte 機能が無効な旧経路では固定候補リストを使い、8,192 を超える候補は `prefill_auto_max` と context の両方以下の場合だけ候補になります。cache / buffer 条件を満たせなければ上限より小さな chunk になるか、別の小さい buffer 経路に移ります。

したがって、この環境変数は実行 chunk を固定する指定ではなく、auto が選べる上限です。8,192 を超える候補の探索上限は `min(prefill_auto_max, max_context)` で制限されます。一方、planner の `auto_ceiling` は最低 8,192 に保たれるため、`max_context` が 8,192 未満でも通常の 8,192 以下の候補まで一律に小さくする処理ではありません。CUDA の gfx12 や layer split、メモリ条件など他の規則が上限を下げることもあります。

## 根拠

- `src/program/generate.cpp:534-546,2041-2065`: 既定上限、`--prefill` と環境変数の優先順位、`atoll` と段階的 clamp、Windows HIP の裸 auto 判定。
- `src/program/generate.cpp:2256-2272`: Linux HIP gfx12 の 16,384 既定値引き上げ条件。裸 auto のみが対象。
- `src/program/generate.cpp:6612-6661,6677-6690,7391-7401`: context / platform 上限と cache-fit に基づく chunk 候補選択。
- `sycl/src/program/generate.cpp:1836-1845,6099-6129,6717-6729`: SYCL 側の同じ値変換と planner 上限の利用。
- `include/strata/platform/host_limits.hpp:19-30`: Windows HIP の裸 auto 6,144 上限と、明示 chunk の警告条件。
- `docs/DETAILS.md:2030`: gfx12 Linux の裸 auto による 16,384 既定値は、明示 `--prefill N`、`auto:N`、`STRATA_PREFILL_AUTO_MAX` を変更しないとの説明。環境変数固有の性能測定値はこの資料では確認できません。
