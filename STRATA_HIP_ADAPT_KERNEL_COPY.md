# `STRATA_HIP_ADAPT_KERNEL_COPY`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・GPU ドライバーの環境変数（`HSA_ENABLE_SDMA` など）は対象外。

## 役割

HIP ビルド専用の opt-in。適応層（adaptive tier）の expert swap の host→device コピーを、copy-engine（SDMA）の memcpy ではなく、refill stream 上のカーネル（`copy_from_mapped`）で実行する。gfx1030 で MMQ prompt 経路・adaptive swaps・SDMA が同時に効いたときハングする問題（#884）の回避策。prompt read の SDMA はそのまま（SDMA を全体で切る `HSA_ENABLE_SDMA=0` とは違い、swap だけ SDMA 経由にしない）。

読み取りは `src/program/generate.cpp` の `adapt_copy_h2d()` 1 箇所（SYCL ビルドに同一ロジックのミラー `sycl/src/program/generate.cpp:201`）。呼び出しは adaptive swap の device_slot 書き込み（`src/program/generate.cpp:8438,12941`）。

## 値と判定

`std::getenv` の結果の**先頭文字 `e[0]` だけ**を `'1'` と比較する。文字列全体・数値は parse しない。

| 状態 | 判定 |
|---|---|
| 未設定（`nullptr`） | 無効（既定） |
| 空文字 `""` | 無効（`e[0]` は `\0`） |
| 先頭文字が `1`（`1`, `10`, `1anything`） | 有効 |
| それ以外（`0`, `true`, `false`, `2` など） | 無効 |

大文字小文字・空白・数値妥当性は検査しない。

根拠: `src/program/generate.cpp:181-182`。

## 有効になる条件

値が有効でも、次の条件が揃わないと通常の `cudaMemcpyAsync`（SDMA）に fallback する。

- ビルドが HIP（`#if defined(STRATA_USE_HIP)`）。CUDA ビルドではこの分岐自体通らない。
- `bytes % 16 == 0`。
- `src` と `dst` が 16 バイト境界对齐（`(uintptr_t)src & 15 == 0` かつ `(uintptr_t)dst & 15 == 0`）。
- source が registered / mapped であること（`cudaHostGetDevicePointer` が成功し非 null を返す）。失敗・null は通常の memcpy へ。

条件不足のとき `copy_from_mapped` は呼ばれず、`cudaMemcpyAsync(..., cudaMemcpyHostToDevice, st)` になる（`src/program/generate.cpp:186-195`）。

## 実行時の詳細

判定結果は `adapt_copy_h2d()` 内の `static const bool kernel` に保存され、プロセス内で最初に呼ばれたとき一度だけ環境を読む。その後の環境変更は再評価されない。

有効時、初回判定で stderr に一度だけ:

```
strata: STRATA_HIP_ADAPT_KERNEL_COPY=1: adaptive swaps copy with a kernel, not SDMA (#884)
```

（`src/program/generate.cpp:183`）。

有効かつ条件を満たす swap では、`copy_from_mapped`（`float4` 単位の device コピーカーネル、`src/kernels/cuda/elementwise.cu:299-308`）を adaptive stream（refill stream）上に launch する。カーネル launch 後の `cudaGetLastError()` を返す。

## 測定値（資料に記載）

`docs/AMD_HIP.md:209-211` はこれを gfx1030 ハング（#884）の workaround として説明し、「reporter のマシンで未テスト」と明記する。このスイッチ自体の性能向上数値は資料にない。同節の `436 -> 757 tok/s` は別変数 `STRATA_DENSE_MMQ` の測定であり、`STRATA_HIP_ADAPT_KERNEL_COPY` の効果ではない。

## 相互作用

- `STRATA_DENSE_MMQ`（同じ #884 のハング条件に関与。MMQ prompt 経路が有効なときに swap・SDMA と組み合わさるとハング）。
- `HSA_ENABLE_SDMA` は外部 driver が読む変数で、Strata の実装はこれを解釈しない（Strata 側は prompt read の SDMA をこのスイッチで切らない、という事実だけ）。

## 根拠

- 読み取り・判定: `src/program/generate.cpp:180-185`。
- 条件と fallback: `src/program/generate.cpp:186-195`。
- 呼び出し箇所（adaptive swap）: `src/program/generate.cpp:8438,12941`。
- コピーカーネル: `src/kernels/cuda/elementwise.cu:299-308`。
- SYCL ミラー: `sycl/src/program/generate.cpp:201-206`。
- docs 照合: `docs/AMD_HIP.md:209-211`、`docs/DETAILS.md:278`。
