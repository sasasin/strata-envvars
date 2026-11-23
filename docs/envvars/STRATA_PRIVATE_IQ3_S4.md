# `STRATA_PRIVATE_IQ3_S4`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL バックエンドの Battlemage 向け IQ3_S4 重みについて、通常の重み配置とは別に、decode 用の変換済み重みキャッシュを作成し、そのキャッシュを使う IQ3 行列ベクトル積カーネルへ切り替えるための private opt-in です。環境変数は `engine/sycl/include/b60_weight_cache.hpp` の `b60_cache_requested(kind)` が読みます。kind `21` がこの名前に対応します（`engine/sycl/include/b60_weight_cache.hpp:5-8`）。

この変数だけではキャッシュ経路は有効になりません。B60 decode layout の初期化が行われ、対象 weight の型・形状が合い、実行時にも packed layout などの条件が揃う必要があります（`engine/sycl/include/b60_layout_host.hpp:81-107`, `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6530-6551`）。

## 値と判定

`std::getenv(name)` で値を取得し、値が存在して最初の文字が `'1'` のときだけ true です。文字列全体や数値としての妥当性は検査せず、空文字は false、先頭が `'1'` なら後続文字を問わず true です。空白除去や大文字小文字変換もありません（`engine/sycl/include/b60_weight_cache.hpp:5-8`）。

| ビルド／経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL の B60 weight-cache 判定、kind `21` | false | `1`, `10`, `1anything`（先頭文字が `1`） | 空文字、`0`, `01`, `true`, ` 1` |
| 他の backend、または `kind` が `21` 以外 | この名前は参照されない。helper は他の kind に別名を割り当てるか `nullptr` を返す | 該当なし | 該当なし |

数値境界や負値の parse はありません。設定値が有効でも、後述の B60 layout と IQ3_S4 カーネル条件が満たされなければキャッシュ経路には入りません。

## 有効になる条件

- 実装は `engine/sycl` 配下の SYCL コードです。CUDA/HIP/CPU など別 backend のこの変数の読み取りは確認できません（`engine/sycl/include/b60_weight_cache.hpp:1-8`）。
- キャッシュを組み立てるには、まず `STRATA_PRIVATE_B60_DECODE_LAYOUT` による B60 layout 経路が選ばれる必要があります。通常の2段 pipeline 経路では `--serve` 内で、native pack、2 stage、no-prefill-borrow、batch 無効、prompt cache 無効、spec が6以下、モデル形状が48層・512 experts・2560 embedding・640 FFN・HC=4 / HC-LR=320、さらに `STRATA_PRIVATE_PACKED_REGISTER` の先頭文字が `1` であることが要求されます。条件を外すと `B60 layout candidate requires the fixed all-resident two-stage decode scene` または `B60 packed weights require the packed register reader` の `invalid_argument` になります（`engine/sycl/src/program/generate.cpp:8035-8046`）。
- single actor layout 側も `--serve`、single device、native pack、その他の no-host decode 用固定条件を要求し、外れると `B60 single layout requires the fixed single-device no-host decode scene` で失敗します（`engine/sycl/src/program/generate.cpp:4591-4597`）。
- 選択された層の `WeightTable` に、`native_type == 21` かつ `native_data` があり、形状が `[ne0, ne1] = [2560, 6144]` または `[6144, 2560]` の重みだけが IQ3 cache 候補になります。その他の重みはこの変数が有効でも対象外です（`engine/sycl/include/b60_layout_host.hpp:81-87`）。
- IQ3_S4 cache kernel の実行にはさらに `t == 21`、旧 IQ MMVQ kernels が無効、main actor、weight が packed 済み、`n_in/n_out` が上記2形状、`ncols` が1・2・4、GPU 世代が Battlemage であることが必要です（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6530-6542`）。この分岐に入らない場合は通常の IQ3 public XMX 経路または format 別 MMVQ dispatch に続きます（同 `:6543-6558`）。
- `STRATA_IQ3S_WIDE` が有効で wide kernel が対応する `ncols` と `n_in` の条件を満たす場合、その kernel が先に起動して戻るため、このキャッシュ分岐は通りません（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6502-6527`, `:6530-6542`）。

## 実行時の詳細

`b60_cache_requested(21)` 自体は `static` に保持されません。B60 layout 構築時は、選択された各 weight の候補判定で環境を読み、その後 `add_device` が cache を作成します。実行時は `iq_mmvq` の呼び出しごとに再判定します（`engine/sycl/include/b60_weight_cache.hpp:5-8`, `engine/sycl/include/b60_layout_host.hpp:81-107`, `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6530-6542`）。したがって、コード上は同一プロセス内で環境値が変われば次の判定に反映されますが、layout 初期化後に値を変えると、cache を作成しなかったのに実行時分岐だけが有効になり `B60 missing IQ3 decode cache` で失敗する可能性があります。逆に初期化時に作成した cache は、実行時判定が false なら IQ3_S4 分岐では使われません。

cache 作成時には元データのサイズに応じて device allocation を行い、IQ3 のバイト配置を変換して ordered SYCL queue で処理完了を待ち、元 pointer と kind の組で registry に保存します。形状・pointer・queue の不整合、未対応 shape、allocation 失敗、重複登録などでは例外になります。layout destructor は登録済み cache を解放します（`engine/sycl/src/kernels/cuda/weight_permute.dp.cpp:131-183`）。

## ログと測定値

cache を `add_device` で準備した後、標準エラーに `B60_CACHE device=%d matrices=%zu cumulative_bytes=%llu` が出ます。この行の `matrices` は同じ行内では `owner.cached.size()`、`cumulative_bytes` はその時点までの累積 cache bytes です（`engine/sycl/include/b60_layout_host.hpp:104-107`）。この変数専用の有効・無効ログはありません。

実行時に cache 分岐へ入ったのに pointer が見つからない場合、`B60 missing IQ3 decode cache` の `std::logic_error` が発生します（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6536-6541`）。本調査対象の `docs/DETAILS.md` にこの変数の性能測定値は見つからなかったため、速度や正確性への定量的効果は記載しません。

## 根拠

- 判定名の割り当てと `getenv` / 先頭文字チェック: `engine/sycl/include/b60_weight_cache.hpp:5-8`
- cache 候補の選定、生成呼び出し、診断ログ: `engine/sycl/include/b60_layout_host.hpp:81-107`
- IQ3_S4 実行時分岐と fallback: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6530-6558`
- cache の allocation・変換・登録・解放: `engine/sycl/src/kernels/cuda/weight_permute.dp.cpp:131-183`
- B60 layout の有効条件: `engine/sycl/src/program/generate.cpp:4591-4597`, `:8035-8046`
