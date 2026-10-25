# `STRATA_GLM_EXL3_DECODE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

DeepSeek-V4.1 engine (`strata-dsv41`) の CUDA EXL3 **decode** で、旧 v1.1.8 kernel 群（`exl3_legacy.cu`）か現行 kernel 群（`exl3.cu`）のどちらを使うか選びます。選択は GPU ごとに行われます。prompt path を切り替える変数ではありません。

## 値と判定

値は数値変換せず、文字列全体を大文字小文字を区別して比較します。

| 値 | CUDA NVIDIA での選択 |
|---|---|
| 未設定 | compute capability major が 8 未満なら legacy、それ以外は現行 kernel |
| `legacy` | legacy kernel |
| `new` | 現行 kernel |
| 空文字、`Legacy`、`NEW`、その他の文字列 | 未設定と同じ GPU 世代による既定選択 |

`legacy` / `new` の後ろに文字が付く値（例: `legacy1`）も完全一致しないため、GPU 世代による既定値に戻ります。

## 有効になる条件

- 変数を読むのは非-HIP CUDA 実装です。HIP では `use_legacy()` が常に `false` を返し、旧 kernel への dispatch はコンパイル時にも無効です。
- EXL3 kernel 群は `STRATA_BUILD_DSV41=ON` かつ `STRATA_HIP_GFX906` でないビルドの `strata-dsv41` 経路に組み込まれます。したがって通常の `strata` 実行や DSV41 を含まない build ではこの変数の効果はありません。
- GPU device index が 0–63 の場合にのみ環境変数と GPU 世代を調べます。index が範囲外なら現行 kernel を選択します。
- ソースコメントでは旧 kernel が NVIDIA sm_80 未満向けの既定とされています。EXL3 のモデル・形式がその engine の処理対象になる必要もあります。

## 実行時の詳細

各 device の選択結果は `static std::atomic<int> cache[64]` に保存され、最初に尋ねられた時点の環境変数と compute capability で固定されます。同じプロセスで環境変数を後から変更しても、その device の選択は再評価されません。異なる device は別々に評価されます。

legacy が選ばれると stderr に `exl3: CUDA%d decodes with v1.1.8's kernels` を出します。現行 kernel 選択時の対応する選択ログはありません。選択結果は `prepare`、`mv`、`moe_gate_up`、`moe_down`、`win_experts` など legacy 対応関数へ委譲する分岐で使われます。また `mv_cols()` は legacy 選択時に 4 を返します。実装コメントは token path と verify window が同じ kernel family を使うとしており、window 内で経路が混ざらないようにしています。

## 根拠

- `CMakeLists.txt:797-811` — DSV41 engine の build option、kernel library と executable の構成、非-HIP build の legacy kernel 追加。
- `src/dsv41/vendor/exl3.cu:36-50,1264-1288` — 非-HIP の legacy dispatch macro、値の比較、compute capability による既定選択、device ごとの cache と選択ログ。
- `src/dsv41/vendor/exl3.cu:1365-1373,1384-1390,1516-1543` — `mv_cols()` と `prepare` / expert decode 関数での選択利用。
- `src/dsv41/vendor/exl3_legacy.cu:3-7,21-22` — 旧 kernel の用途と HIP では含めない旨の実装注記。

`docs/DETAILS.md` にこの変数の説明や性能測定値は見つかりませんでした。ここでは性能差を推定していません。
