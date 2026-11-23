# `STRATA_Q8_V70`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の native multi-column MMVQ で、Q8_0 重みの 2〜4 列 GEMV に対して、ブロックループを展開した専用 kernel の選択を opt-in する。通常の multi-column kernel と同じ出力になる設計とソースコメントに記されているが、この調査では実行・測定していない。環境変数は `q8_v70_on()` で読み取られ、`launch_multi_n()` から適格な Q8_0 呼び出しに限って選択される（`engine/src/kernels/cuda/native_mmvq.cu:1574-1584,1636-1652,1654-1674,1677-1684`）。

## 値と判定

値は `std::getenv` で取得し、未設定なら無効、設定されていれば `std::atoi(v) != 0` で有効・無効を判定する。文字列全体の検証はなく、`atoi` が先頭から変換できる 10 進整数を使うため、空文字や数字で始まらない文字列は 0、数値の後ろに文字がある場合は数値部分で判定される。符号と先行空白も `atoi` の変換規則に従い、`true`/`false` は数値に変換されず無効。コードに範囲チェックや clamp はない（`engine/src/kernels/cuda/native_mmvq.cu:1636-1638`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA コンパイル（HIP ではない） | 無効 | `1`, `-1`, `2tail`, ` 1`（`atoi` の結果が非 0） | 空文字、`0`, `0anything`, `true`, `false`, `x1` |
| HIP コンパイル | この分岐はコンパイル対象外 | 該当なし | 該当なし |

`atoi` の整数範囲外入力に対する処理はコードで検査・規定していない。値を変更しても、プロセス内で最初に `q8_v70_on()` が実行された後は関数内 `static const bool` に保存された結果が使われる（`engine/src/kernels/cuda/native_mmvq.cu:1636-1638`）。

## 有効になる条件

- Strata が CUDA 実装としてビルドされていること。対象コードは `#if !defined(__HIPCC__)` 内にあり、HIP ビルドでは除外される（`engine/src/kernels/cuda/native_mmvq.cu:1573,1676,1682-1684`）。
- native MMVQ が Q8_0 (`ggml_type == 8`) へ到達すること。先に Q8 packed 経路が成功した場合はそちらで戻り、8 列以上では RDNA WMMA 経路が選ばれる場合がある（`engine/src/kernels/cuda/native_mmvq.cu:3699-3704`）。
- 対象が通常の `SmallTraits<Q80Block, 8>` multi-column 経路で、列数が 2〜4 であること。ほかの trait または列数では helper は `false` を返す（`engine/src/kernels/cuda/native_mmvq.cu:1653-1658,1713-1742`）。
- `g_multi_exact` が true であること。初期値は true だが `native_mmvq_set_multi_exact()` で変更できる（`engine/src/kernels/cuda/native_mmvq.cu:1246,1659,3272-3273`）。
- `STRATA_TSUM` が有効でないこと。`s26_tsum_on()` は値の先頭文字が `'1'` かを判定し、true の場合は専用 kernel を選ばない（`engine/src/kernels/cuda/native_mmvq.cu:1252-1255,1659`）。
- `n_in` が 1024 の倍数で `2048..8192`（2〜8 × 1024）、かつ `n_out` が偶数であること（`engine/src/kernels/cuda/native_mmvq.cu:1659-1662`）。
- 現在の CUDA device の compute capability が 7.0 であること。device 選択・属性取得に失敗した場合や他の capability では専用 kernel を選ばず、通常の multi-column kernel にフォールバックする（`engine/src/kernels/cuda/native_mmvq.cu:1641-1651`）。

候補索引 `docs/envvars/000_envvers.md` はこの変数を「NVIDIA and AMD」と分類しているが、確認した読み取りと専用 kernel は CUDA 実装の HIP 除外領域にあり、AMD/HIP で有効になるコードは見つからなかった。この分類はソース上の実装範囲と一致しない。

## 実行時の詳細

Q8_0 multi-column 呼び出しは `native_q8_0_mmvq()` から `small_mmvq()` へ進み、`launch_multi_n()` が Q8_0 の 2〜4 列の場合に `q8_v70_launch()` を試す。専用経路が成立しなければ後続の既定 multi-column kernel が選ばれる（`engine/src/kernels/cuda/native_mmvq.cu:3699-3704,1677-1710,1713-1742`）。

形状・`g_multi_exact`・`STRATA_TSUM` の条件が先に確認され、条件を満たすときに `q8_v70_on()` が環境変数を初回評価する。環境変数の真偽値はプロセス内でキャッシュされ、device ごとの compute capability 判定も `per_dev[16]` にキャッシュされる。実行中に環境を変更してもこの読み取り結果には反映されない（`engine/src/kernels/cuda/native_mmvq.cu:1636-1651,1654-1662`）。

専用 kernel は `n_in / 1024` ごとに 2〜8 の template instantiation を起動し、2 行ずつ処理する。ソースコメントは、既定 kernel と各出力が bitwise 同一になる設計だと述べている（`engine/src/kernels/cuda/native_mmvq.cu:1578-1584,1587-1634,1662-1673`）。

## ログと測定値

有効値で適格な CUDA device が初めて確認された場合、その device について stderr に次の形式を出す。device 判定はキャッシュされるため、同じ device で繰り返し出るものではない。unset・無効値、compute capability が 7.0 でない場合、device/API 判定に失敗した場合は、このログを出さず通常経路へ進む（`engine/src/kernels/cuda/native_mmvq.cu:1638-1649`）。

```text
strata: STRATA_Q8_V70=1: the unrolled Q8_0 GEMV for 2-4 columns on CUDA%d (bitwise the default kernel)
```

ソースコメントには特定の V100 の 3 列 projection で既定 kernel が 540〜570 GB/s とあるが、これは既定経路に関する記述であり、この環境変数による改善値ではない。ここでは新たな測定をしていない（`engine/src/kernels/cuda/native_mmvq.cu:1575-1584`）。

## 根拠

- `engine/src/kernels/cuda/native_mmvq.cu:1573-1584` — CUDA/HIP の境界、対象 kernel の設計・適用形状。
- `engine/src/kernels/cuda/native_mmvq.cu:1636-1652` — 値変換、cache、device 判定、ログ。
- `engine/src/kernels/cuda/native_mmvq.cu:1653-1684` — 選択条件、専用 kernel 起動と通常経路への継続。
- `engine/src/kernels/cuda/native_mmvq.cu:1677-1742,3699-3704` — Q8_0 の呼び出し経路と列数 dispatch。
- `engine/src/kernels/cuda/native_mmvq.cu:1246,1252-1255,3272-3273` — exact-layout 状態と `STRATA_TSUM` 判定。
