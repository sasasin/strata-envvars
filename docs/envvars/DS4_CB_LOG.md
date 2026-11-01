# `DS4_CB_LOG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal ランタイムが `Context::flush_runs()` で command buffer を flush するとき、未完了の deferred command buffer に含まれる dispatch 数と、記録されていれば最初・最後の kernel 名を stderr に一行出す診断用スイッチです。処理の選択、dispatch、commit、wait の動作そのものは変更しません。 (`metal/src/mtl_rt.mm:855-868,871-895`)

## 値と判定

値の文字列や数値は parse されず、`std::getenv("DS4_CB_LOG") != nullptr` という存在判定だけです。

| 状態 | `cb_log` |
|---|---|
| 未設定 | 無効 |
| 空文字で設定 | 有効 |
| 任意の非空文字列（`0`、`false` を含む） | 有効 |

結果は `flush_runs()` 内の `static const bool` に保存されます。最初の `flush_runs()` 呼び出し時に判定し、その後プロセス内で環境を変更しても再評価されません。 (`metal/src/mtl_rt.mm:855-858`)

## 有効になる条件

- `STRATA_DS4_RUNTIME` を定義してビルドされた Metal ランタイムが対象です。この定義は Metal CMake プロジェクトが `ds4_rt_mm` に与えています。Metal プロジェクト自体は macOS 専用です。 (`metal/CMakeLists.txt:17,152-164`; `metal/src/mtl_rt.mm:43,76,899`)
- `Context::flush_runs()` が呼ばれ、かつ `impl_->cb_def != nil`（flush 対象の deferred command buffer がある）場合に `CB ...` の行が出ます。inflight buffer だけを待つ呼び出しではこの行は出ません。 (`metal/src/mtl_rt.mm:855-868,871-895`)
- kernel 名は `DS4_CB_LOG` だけでは蓄積されません。単一 dispatch を deferred command buffer に encode する経路で、別変数 `DS4_ERRINFO` が設定されている場合に `def_names` へ名前が追加されます。`DS4_ERRINFO` が未設定なら、出力の `first` と `last` は空でも dispatch 数は出ます。 (`metal/src/mtl_rt.mm:908-933`)

## 実行時の詳細

ログ形式は `CB %d disp  first=%-24s last=%s\n` で、stderr に出ます。`%d` は `impl_->def_n`、`first` と `last` は `def_names` から取り出した最初と最後の kernel 名です。名前列が空なら空文字になります。 (`metal/src/mtl_rt.mm:858-868`)

出力判定は command buffer を commit する直前です。その後、通常どおり encoder を終了し、event を signal するよう設定して commit し、inflight command buffer があれば完了を待ちます。したがってこの変数自体は command buffer の境界・待機・エラー処理を変えません。失敗時の `mtl: deferred command buffer failed: ...` などは別の既存処理です。 (`metal/src/mtl_rt.mm:871-895`)

## 根拠

- `metal/src/mtl_rt.mm:855-868` — 環境読み取りの cache、command buffer の有無による条件、ログ形式。
- `metal/src/mtl_rt.mm:908-933` — deferred command buffer の dispatch encode と、`DS4_ERRINFO` が設定された場合の kernel 名記録。
- `metal/src/mtl_rt.mm:871-895` — commit、wait、失敗ログの経路。
- `metal/CMakeLists.txt:17,152-164` — Metal project の macOS 制約と runtime compile definition。
- `metal/src/mtl_rt.h:112-119` — `flush_runs()` が batched dispatch を commit して待つ API であること。
