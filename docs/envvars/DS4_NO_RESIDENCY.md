# `DS4_NO_RESIDENCY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Metal の `mtl::Context` が作る command queue に、DeepSeek エンジンの共有 `MTLResidencySet` を追加する処理を止めるための切り替えです。`DS4_NO_RESIDENCY` が環境に設定されていると、この queue に対する `addResidencySet:` 呼び出しをスキップします。

## 値と判定

値の内容は parse せず、`std::getenv("DS4_NO_RESIDENCY")` が null かどうかだけを判定します。

| 環境変数 | 判定 | 結果 |
|---|---|---|
| 未設定 | `getenv` が null | residency set が取得でき、null でなければ `impl_->q` に追加する |
| 任意の設定値 | `getenv` が非 null | `impl_->q` への residency set 追加をスキップする |

したがって `1` だけでなく `0`、任意の文字列、空文字も設定されていれば同じく追加を止めます。数値変換、無効値時の fallback、CLI 引数や別環境変数との優先順位はありません。

## 有効になる条件

- `STRATA_DS4_RUNTIME` が定義された Metal runtime でのみ、この判定を含むコードがコンパイルされます。CMake では `ds4_rt_mm` と `ds4_rt_gpu` にこの macro を定義し、これらを `strata_ds4` にリンクします（`metal/CMakeLists.txt:151-169`）。
- `mtl::Context` の構築時に評価されます。`Context` を作るたびに判定し、static cache はありません。構築後に環境値を変えても、その既存 queue への追加処理は再評価されません。
- residency set を追加するには、weak import された `ds4_gpu_residency_set` 関数が利用可能で、関数が返す `rs` も null でない必要があります。どちらかが満たされない場合は追加されません。

## 実行時の詳細

`Context` はまず既定 Metal device と command queue を作ります。その後、`STRATA_DS4_RUNTIME` 経路では `ds4_gpu_residency_set` が利用可能かつ `DS4_NO_RESIDENCY` が未設定の場合にだけ共有 set を取得し、非 null なら `impl_->q` に追加します。変数を設定した場合に Strata が行う処理は、この追加呼び出しを省くことです。変数に関するログ、警告、終了、エラー処理はありません（`metal/src/mtl_rt.mm:43-45,292-316`）。

この切り替えは全ての residency set 使用を止めるものではありません。Metal GPU runtime の各 stream queue は別途 `rt().rs` を無条件に追加します（`metal/src/gpu/runtime.cpp:139-148`）。また、zero-copy buffer の登録経路は `DS4_NO_RESIDENCY` を参照せず、取得できた set に allocation を追加して commit します（`metal/src/mtl_rt.mm:422-445`）。

## 根拠

- 候補名の全参照検索では、実際の読み取りは `metal/src/mtl_rt.mm:308` の一か所です。helper 経由や動的な名前渡しの参照はありませんでした。
- residency set 関数は `STRATA_DS4_RUNTIME` 下で weak import され、GPU runtime 側から `residency_set_impl()` を返します（`metal/src/mtl_rt.mm:43-45`; `metal/src/gpu/runtime.cpp:430,839-847`）。
- `docs/MAC.md:31-36` は Metal engine の residency set 利用を説明しますが、`DS4_NO_RESIDENCY` の値判定や挙動の説明は確認できませんでした。
