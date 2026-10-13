# `STRATA_HC_UPMIX_CHECK`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

Prefill の hyper-connection（HC）読み出しで、通常の up projection と `gr_mix_r` の組み合わせを基準値として計算し、融合カーネル `gr_upmix` の `mixed` 出力との差を stderr に記録する診断用カウンターである。これ自体は融合経路を有効にしない。比較処理は `STRATA_HC_UPMIX` が有効で、かつその融合経路の適用条件を満たした場合に限って実行される。

## 値と判定

| 値 | 処理 |
| --- | --- |
| 未設定 | 比較回数 `0`。比較しない。 |
| 空文字、数値に変換できない文字列 | `std::atoi` の結果 `0`。比較しない。 |
| 正の整数 | 適用条件を満たす最初の読み出しから、その回数だけ比較する。 |
| `0` または負の整数 | 比較しない。 |

値は `std::atoi` で整数化されるため、文字列全体の厳密な数値検証はしない。先頭の空白や符号を許容し、数値として読める接頭辞の後ろは判定に使わない（例: `2x` は `2`）。数値接頭辞がない場合は `0` となる。正数に上限を設けるコードはない。

## 有効になる条件

比較カウンターは、HC upmix の実行候補ブロック内で初期化・参照される。次の全条件を満たさなければ、この変数を設定しても何も起きない。

- `STRATA_HC_UPMIX` の先頭文字が `'1'` である（値全体の比較ではない）。この設定も初回評価時に static cache される。
- Prefill の現在のチャンク長 `T` が `STRATA_PF_SWITCH_MIN_T` 以上である。`STRATA_PF_SWITCH_MIN_T` は未設定なら `0`、設定時は `atoll` で一度読み取られる。
- `gr_unfused()` が false で、`m.lo16_lo` と `m.mixed_bf_lo` が存在しない。
- up 重みが BF16 を FP32 に格納する形式で、データがあり、形状が `ne0 == LR` かつ `ne1 == D` である。

`gr_upmix` が実際にカーネルを起動するのは HIP ビルドで、選択中デバイスのアーキテクチャ名が gfx1100、gfx1101、gfx1102、gfx1150、gfx1151 のいずれかで、`T > 0` の場合である。CUDA ビルド、およびこの一覧外のデバイスでは `gr_upmix` は `false` を返してカーネルを起動しない。SYCL版にも同じ環境変数判定と比較コードがあるが、そこから呼ぶ `gr_upmix` の実装も `__HIPCC__` でないビルドでは `false` を返す。

## 実行時の詳細

`checks` は関数内 static 変数であり、プロセス起動時ではなく、実行中に初めて上記候補ブロックへ到達したとき環境から読み取られる。その値はプロセス内でキャッシュされる。候補となる HC 読み出しごとに `checks > 0` なら先に1減らすため、指定回数はモデル全体・両方の half（`0` は attention、`1` は FFN）を通じて共有される。適用条件を満たさない読み出しでは消費されない。起動後に環境変数を変更しても初期値や残り回数は変わらない。

各比較ではまず通常経路の BF16 up projection と `gr_mix_r` を実行し、`mixed` をホスト側の基準配列 `ref` にコピーする。続いて `gr_upmix` を呼んで候補出力を `got` にコピーし、ストリームを同期して、全要素の二乗誤差和 `e2`、基準値の二乗和 `r2`、最大絶対差 `emax` を集計する。stderr には次の形式でレイヤー、half、`T`、相対 RMS、最大差、融合カーネルの成否を出す。

```text
strata: STRATA_HC_UPMIX_CHECK layer <l> half <half> T <T>: mixed rel RMS <値>, max |diff| <値> (upmix|upmix refused)
```

相対 RMS は `sqrt(e2 / max(r2, 1e-30))`。合否しきい値はなく、ログを出すだけである。比較が終わると、`gr_upmix` が成功した場合はその出力を後続処理に使い、失敗時は通常経路を続ける。CUDA／非対応 HIP デバイスでは融合カーネルが起動されないため、`got` は直前の通常経路の `mixed` と同じバッファの内容を読むことになり、ログの差分は融合実装の検証にはならず、末尾は `upmix refused` になる。

正の比較回数を指定すると、基準計算と候補計算に加えてデバイスからの配列コピーと同期を行う。したがって診断対象の処理には追加の時間とメモリを要する。比較値が同一か、出力品質が十分かをこのコードが判定するわけではない。

## 根拠

- `src/prefill/prefill.cpp:315-325` — HC upmix と check の説明、`STRATA_HC_UPMIX` の先頭文字判定、`STRATA_PF_SWITCH_MIN_T` の既定値・読み取り。
- `src/prefill/prefill.cpp:2564-2600` — 有効条件、`atoi` による初期化、比較回数の消費、基準値・候補値の取得、誤差計算とログ、失敗時の通常経路。
- `sycl/src/prefill/prefill.cpp:250-260`, `2833-2883` — SYCL側の同等の判定と比較処理。
- `src/prefill/kernels.cu:1725-1730`, `1852-1870` — HIP向けカーネルの意図と、gfx11／`T > 0` 以外および非HIPビルドでの不実行。
- `sycl/src/prefill/kernels.dp.cpp:2095-2100`, `2340-2358` — SYCL側カーネルの意図と実行条件。
- `include/strata/kernels/gfx_arch.hpp:22-25` — WMMA対象となる gfx11 アーキテクチャ名。
- `docs/STRIX_HALO.md:100-115` — `STRATA_HC_UPMIX=1` を prompt 経路の opt-in として記載。資料の説明はソースの「HC up projection と epilogue を融合する」説明と整合する。`STRATA_HC_UPMIX_CHECK` の値判定や比較回数の詳細は同資料にはない。
