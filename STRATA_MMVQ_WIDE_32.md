# `STRATA_MMVQ_WIDE_32`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

SYCL backend の native MMVQ で、Q8_0 と IQ4_NL の 32要素ブロック用 wide32 カーネルを使うか選びます。無効にすると、両形式は旧 small/multi カーネルに進みます。対象実装は `sycl/src/kernels/cuda/native_mmvq.dp.cpp` にあり、候補一覧にある名前でも CUDA/HIP/C++ 共通の設定ではありません。

## 値と判定

`wide_32()` は環境変数が未設定なら `true`、設定されていれば `std::atoi(value) != 0` を使います。文字列全体の妥当性や末尾は検査しません。

| 環境値 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| `0`、`00`、`+0`、`-0`、空文字、数値変換できない文字列（例: `true`） | 無効（`atoi` が 0） |
| `1`、`-1`、`2tail`、先頭空白の後に非ゼロ数値がある文字列 | 有効（`atoi` が非ゼロ） |

`atoi` は先頭の空白と符号を扱い、数値部分の後ろに文字があっても変換できた数値を返します。数値変換の失敗を別途エラーとして扱うコードはありません。変換範囲外の値についても Strata 側に検査や fallback はありません。

判定結果は `wide_32()` 内の関数ローカル `static const bool` に保存されます。`try_wide32()` が初めて判定した後にプロセス環境が変わっても、再評価されません。

## 有効になる条件

この環境変数を読むのは SYCL ソースの native MMVQ 実装です。wide32 経路を実際に起動するには、さらに `ncols` が 1〜8、`n_in` が 32 の倍数である必要があります。条件外では `try_wide32()` は `false` を返し、呼び出し元が small MMVQ に進みます。

Q8_0 はまず登録済みの packed Q8_0 重みを使えるか確認し、それが処理した場合は wide32 の判定を通りません。IQ4_NL にはこの Q8_0 packed 経路はありません。ここに示した条件以外に、OS、GPU 世代、CLI、別の環境変数による追加判定はこの機能の直接実装にはありません。

## 実行時の詳細

native MMVQ の GGML type 8 は `native_q8_0_mmvq()`、type 20 は `native_iq4_nl_mmvq()` に振り分けられ、どちらも `try_wide32()` を呼びます。wide32 が有効で形状条件も満たす場合、列数ごとの wide32 SYCL kernel を launch し、launch check 後に戻ります。無効または形状条件外なら、それぞれ `small_mmvq<Q80Block, 8>` / `small_mmvq<IQ4NLBlock, 4>` を呼びます。環境変数自体についてログ出力やエラー終了はありません。

`docs/INTEL.md` は、`STRATA_MMVQ_WIDE_32=0` で Q8_0/IQ4_NL の旧 kernel に戻せると説明しています。同資料には SYCL port の測定値と出力差についての記載もありますが、これは資料記載の測定報告であり、この調査で再測定・出力同一性の検証はしていません。

## 根拠

- 全ソース検索で得た直接の読み取り箇所は `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1959-1965` のみ。値の既定と cache は `1959-1961`、wide32 の形状条件と選択は `1963-1976`。
- wide32 が扱う型とカーネル計算は `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1890-1948`。
- Q8_0 の packed 経路、wide32 呼び出し、および旧経路への fallback は `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3628-3632`。IQ4_NL の呼び出しと fallback は `3640-3643`。
- GGML type 8/20 の振り分けは `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3685-3702`。
- 資料上の旧経路切り替えと測定の説明は `docs/INTEL.md:472-482`。
