# `FNX_PF_GDN_CHUNK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata-split` の prompt GDN recurrence で、32 行単位の sub-chunk scan（`k_gdn_ch_prep` + `k_gdn_ch_rec`）を使うか、行ごとの recurrence（`k_gdn_pf_rec`）を使うかを選ぶ。未設定時は sub-chunk scan を選ぶ。値が `0` なら行ごとの recurrence に切り替わる。sub-chunk scan は状態非依存の準備カーネルと状態更新カーネルを使い、通常経路とは浮動小数点の加算順序が異なるため、同じ結果のビット一致はコードから保証されない（`engine/src/split/src/kernels.cu:2049-2068`; `engine/src/split/src/gdn_prompt.cuh:155-165`）。

この読み取りは `engine/src/split/src/kernels.cu` の `gdn_prompt_impl` にだけある。対象は `-DSTRATA_BUILD_SPLIT=ON` で構築する split engine の prompt GDN 経路であり、通常の `strata` engine 全体の設定ではない。split は Linux CUDA または HIP の構成でビルドされる（`engine/src/split/CMakeLists.txt:1-7,20-26`）。

## 値と判定

初回に fallback scan へ入るとき `std::getenv` で読み、文字列全体を `strcmp` で比較する。数値変換は行わない（`engine/src/split/src/kernels.cu:2018-2022`）。

| 条件 | unset | 有効になる値 | 無効値と結果 |
| --- | --- | --- | --- |
| `gdn_prompt_impl` が sub-chunk / row-by-row の選択箇所まで到達 | sub-chunk scan を選ぶ | 正確に `1`: sub-chunk scan。正確に `0`: row-by-row scan | 空文字、`true` / `false`、`00`、`0anything`、前後空白付きの値などはすべて無効。`FNX_PF_GDN_CHUNK: 0 or 1, not '<値>'` の `std::runtime_error` を送出する |
| CUDA tensor-core scan がその呼び出しで完了 | この変数を読まない | この変数を読まない | この変数を読まないため、値の検証も行われない |

大文字小文字や空白の正規化、数値の範囲処理はない。明示的な空文字は unset と同じ扱いではなく無効値である。CLI 引数による上書きはこの関数にない（`engine/src/split/src/kernels.cu:2018-2022`）。

## 有効になる条件

- split engine の prompt で GDN 層を処理し、`gdn_prompt` から `gdn_prompt_impl` が呼ばれること（`engine/src/split/src/prefill.cu:1651-1657`, `engine/src/split/src/kernels.cu:2073-2079`）。
- 通常の CUDA build では tensor-core GDN scan がコンパイルされ、実行時にも選択されて scan を完了すると、この変数の選択箇所へ到達せず設定は効かない。tensor-core scan は `FNX_KPART == 4 && !FNX_HIP && FNX_ARCH >= 80` のときコンパイルされる（`engine/src/split/src/gdn_tc_prompt.cuh:11-15`）。モデル読込時に IQ experts でないモデルは tensor-core scan の既定を ON、IQ experts のモデルは OFF にする。`FNX_PFX_GDN_TC` はその既定を上書きする。scan が選ばれない、または `gdn_tc_run` が `false` を返す場合は、この変数の fallback 分岐へ進む（`engine/src/split/src/engine.cu:65-66`, `engine/src/split/src/kernels.cu:2008-2022`）。
- HIP build では tensor-core scan の compile guard に合致しないため、この fallback の選択箇所へ進む（`engine/src/split/src/gdn_tc_prompt.cuh:11-15`, `engine/src/split/src/kernels.cu:2008-2023`）。
- GDN を含まない attention 層では呼び出されない（`engine/src/split/src/prefill.cu:1651-1657`）。

## 実行時の詳細

`chunked` は関数内 `static const bool` の初期化ラムダで設定される。したがって、環境を読むのはプロセス内で初めてこの選択箇所に到達した時点で、その後の呼び出しではキャッシュ済みの値を使う。実行中に環境を変更しても再評価されない（`engine/src/split/src/kernels.cu:2018-2023`）。CUDA tensor-core scan が先に成功して return する場合、この static の初期化は遅延したままで、変数の読み取りも無効値の検査も発生しない（`engine/src/split/src/kernels.cu:2008-2022`）。

sub-chunk scan では `GCH=32` 行の準備カーネルと再帰カーネルを起動し、その後専用 norm カーネルを起動する。`0` の経路では逐次 recurrence カーネルと norm カーネルを使う。どちらも同じ prompt GDN 呼び出しの出力 `y32` と GDN 状態 `S` を更新し、その後の出力 projection に `y32` が渡される（`engine/src/split/src/kernels.cu:2049-2068`, `engine/src/split/src/prefill.cu:1655-1657`）。ソースコメントは sub-chunk scan の加算順序が行単位経路と異なると記しているが、性能差や出力差の測定値はこの変数についての調査対象資料から確認できない（`engine/src/split/src/gdn_prompt.cuh:163-165`）。

無効値は例外になる。`sfnx` の実行中に伝播した例外は標準出力へ `ERR <例外文>`、標準エラーへ `sfnx: failed: <例外文>` を出して flush し、終了コード 1 で終了する（`engine/src/split/tools/sfnx.cpp:1094-1103,1160-1166`）。

## 根拠

- `engine/src/split/src/kernels.cu:2001-2023` — prompt GDN 実装、tensor-core scan の先行分岐、環境値の parse と既定値。
- `engine/src/split/src/kernels.cu:2049-2069` — 選択される scan と norm、kernel launch error の確認。
- `engine/src/split/src/gdn_prompt.cuh:155-165` — 32 行 sub-chunk scan の説明と加算順序の差。
- `engine/src/split/src/prefill.cu:1651-1657` — prompt GDN 呼び出しと後続 projection。
- `engine/src/split/src/gdn_tc_prompt.cuh:11-15`, `engine/src/split/src/engine.cu:65-66` — CUDA tensor-core scan の build 条件とモデル由来の既定。
- `engine/src/split/tools/sfnx.cpp:1094-1103,1160-1166` — 実行中例外の ERR / stderr 報告と終了。
- `engine/src/split/CMakeLists.txt:1-7,20-26` — split engine の build/backend 条件。
