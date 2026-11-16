# `STRATA_PRIVATE_GU_XXS_PACKED`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この private opt-in は、SYCL の B60 packed decode layout で IQ2_XXS (`gu_type == 16`) の gate/up 重みを、行方向に並べ替えた配置として扱うかを指定する。値を有効にすると、layout 準備時に IQ2_XXS の gate/up 行列を permutation 対象へ登録し、single-device staging / mirror exchange でも同じ配置の変換を行う。また、条件を満たす Battlemage の grouped expert gate/up では専用の ESIMD kernel を選択できる。down 重み、他の量子化形式、通常の raw-weight 経路を単独で切り替える変数ではない（`sycl/include/b60_layout_host.hpp:38-55,126-135`、`sycl/src/kernels/cuda/weight_permute.dp.cpp:88-98`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4621-4625,5605-5613`）。

## 値と判定

すべての直接読み取りは `std::getenv` の結果が非 null で、かつ `p[0] == '1'` かを判定する。文字列全体の parse や数値変換はしない。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| B60 layout の expert 収集 (`Layouts::add_experts`) | 無効。IQ2_XXS gate/up は登録されない | `1`, `10`, `1anything`（先頭文字が `1`） | 空文字、`0`, `true`, ` 1`, `-1` |
| single-device staging / mirror exchange | 無効。IQ2_XXS 部分は raw 順序のまま処理される | 同上 | 同上 |
| packed IQ2_XXS kernel 判定 (`p16_enabled`) | 無効 | 同上 | 同上 |

大文字小文字や後続文字は判定に関与しない。空文字は設定済みでも無効。負値は数値として解釈されず、先頭が `1` でないので無効である（`sycl/include/b60_layout_host.hpp:39-51`、`sycl/src/kernels/cuda/weight_permute.dp.cpp:306-307,329-330`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4622-4624`）。

## 有効になる条件

- 実行ファイルが該当する Strata SYCL backend / kernels を含む必要がある。確認した読み取り箇所は `sycl/` 配下の実装である。
- Host layout 側の IQ2_XXS 行列登録にはさらに `b60_layout_requested()` が必要であり、これは別の `STRATA_PRIVATE_B60_DECODE_LAYOUT` が先頭文字 `1` のときに成立する。対象変数が有効でも B60 layout が要求されなければ `add_experts` の処理は通常呼ばれない（`sycl/src/program/generate.cpp:4508-4515,7876-7887`、`sycl/include/b60_layout_state.hpp:7-9`）。
- `p16_enabled` が true になるには、対象変数に加え、`b60_main_actor()`、重みが packed 状態 (`b60_weights_packed()`)、デバイス世代が `IntelGpuGen::Battlemage` であることが必要（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4621-4625`）。main actor は B60 layout / single actor scope から設定される（`sycl/include/b60_layout_state.hpp:14-20`）。
- 一般 grouped gate/up kernel の専用経路には `TG==16`, `LN==8`, `KM`, `n_embd==2560`, `n_ff==640`, `!g_old_kernels`, `!g_split_multi` も必要（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5605-5613`）。別の S4 grouped 経路では追加で `!v1`, `gu_lanes()==8`, `grid_groups==0`, `cap_groups==cap_entries`, `b60_next_iq_pool()` と device / capacity 条件が必要（同 `:7388-7392`）。
- B60 layout 自体にも serve、native pack、GPU 構成、モデル形状等の制約があり、満たさないと `generate.cpp` が `invalid_argument` を投げる。single actor 経路は固定の single-device no-host decode 条件、複数段経路は固定 all-resident two-stage decode 条件を検査する（`sycl/src/program/generate.cpp:4509-4515,7876-7883`）。
- CLI 引数によるこの変数の上書きは見つからなかった。別環境変数 `STRATA_PRIVATE_GU_IQ1_PACKED` は IQ1_M の配置用で、IQ2_XXS の本変数判定とは独立している（`sycl/include/b60_layout_host.hpp:49-53`）。

## 実行時の詳細

- `Layouts::add_experts` は expert format ごとに本変数を読み、値が有効かつ `gu_type==16` の場合に IQ2_XXS gate/up の各行列を type 16、640 rows、10 blocks として登録する。配置形状が期待する `gu_row`, `up_off`, `down_off` と異なる場合は `invalid_argument("B60 IQ2_XXS offsets")` になる。down matrix はこの条件に関係なく別途登録される（`sycl/include/b60_layout_host.hpp:38-55`）。
- `Layouts::packed(true)` は登録済み matrices を `b60_weight_permute_many` に渡し、type 16 / 10 blocks を 66-byte block permutation で変換する。`packed(false)` は逆方向へ戻す。B60 layout がなく登録行列がない場合、処理は早期 return する（`sycl/include/b60_layout_host.hpp:126-135`、`sycl/src/kernels/cuda/weight_permute.dp.cpp:8-20,35-50,88-98`）。
- Single-device の mirror exchange と staging helper は呼び出しごとに本変数を読み、その値を GPU kernel の byte-index 変換へ渡す。IQ2_XXS gate/up では block size 66 の packed/raw 変換を使い、down 部分は対象変数に関係なく block size 18 の変換を使う（`sycl/src/kernels/cuda/weight_permute.dp.cpp:260-279,295-330,333-342`）。
- `p16_enabled` は関数内 `static const bool` に保存するため、最初の呼び出し時に読んだ値がそのプロセス内の後続呼び出しにも使われる。一方、host layout と staging/exchange の判定はそれぞれ関数実行時に読む。従ってプロセス中に環境値を変更するケースは、一貫した適用を保証するコードではない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4622-4625`、`sycl/include/b60_layout_host.hpp:39`、`sycl/src/kernels/cuda/weight_permute.dp.cpp:306,329`）。
- Gate/up の標準 packed-register launch では条件が揃うと `launch_gu_xxs` を実行し、それ以外は後続の一般 kernel 選択へ進む（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5605-5613`）。コードは計算経路の切り替えを示すが、この調査では出力の同一性や性能を実測していない。

## ログと測定値

この変数専用の有効・無効ログや警告は見つからなかった。layout の変換が実行された場合は stderr に `B60_LAYOUT phase=packed ...` または `B60_LAYOUT phase=raw ...` が出るが、この行は対象変数の値や IQ2_XXS 選択結果を表示しない（`sycl/include/b60_layout_host.hpp:126-135`）。形状・layout 条件の失敗は上記の例外文字列で観測できる。対象変数の効果に関する測定値は、参照した Strata 資料に見つからなかった。

## 根拠

- `sycl/include/b60_layout_host.hpp:38-55,126-135` — 値判定、IQ2_XXS の行列登録、packed/raw phase。
- `sycl/src/kernels/cuda/weight_permute.dp.cpp:8-20,35-50,88-98,260-279,295-342` — permutation、single-device staging / exchange の値判定と変換。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4621-4625,5605-5613,7388-7392` — static 判定、Battlemage・モデル形状等の kernel 条件。
- `sycl/include/b60_layout_state.hpp:7-20` — B60 layout / main actor の追加条件。
- `sycl/src/program/generate.cpp:4508-4515,7876-7887` — B60 layout の生成時条件と失敗経路。
