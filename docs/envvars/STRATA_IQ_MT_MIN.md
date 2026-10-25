# `STRATA_IQ_MT_MIN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。

## 役割

ネイティブ形式の CPU expert 計算で、gate/up（および IQ4_NL down）の複数 token カーネルへ切り替える最小 token 数を指定する。既定値 `2` では、token が1個のとき ggml-cpu の dot product、2個以上のとき対応する Strata の multi-token カーネルを使う。この二つの計算経路は丸めが異なることがあり、verify window 内で同じ expert を使う token 数により greedy 出力が変わり得る。`1` にすると対象カーネルを1 tokenから使い、drafting による token 数の違いから生じる差を避ける設定となる（`docs/DETAILS.md` の説明を参照）。

## 値と判定

| 環境変数の状態・値 | 判定される最小 token 数 |
| --- | ---: |
| 未設定 | `2` |
| 設定あり（空文字を含む） | `std::atoi` の結果 |
| 例: `1` / `2` | `1` / `2` |
| 例: `abc`、空文字 | `0` |
| 例: `2tail` | `2`（数値として読める先頭部分） |

文字列全体の検証、範囲制限、負値の拒否はない。各経路は `nt >= mt_min` を判定するため、0または負値なら通常の正の `nt` に対して条件を満たす。値は設定有無ではなく `atoi` の整数値として扱う。

## 有効になる条件

- Strata が `STRATA_NATIVE_EXPERTS` を有効にしてビルドされ、ネイティブ expert pack を読み込んで CPU native expert の処理に入ること。CMake の既定は ON。無効ビルドでは native expert 機能自体が利用できず、この変数による切替も起きない。
- gate/up は `native_gu_rows` が処理する形式のうち、CPU ISA と対応形式に合う専用 multi-token kernel がある場合だけ切り替わる。AVX-512 が使える場合は対象の AVX-512 kernel、AVX-512 がない場合は対応する AVX2 kernel、さらに AVX2 がない場合は対応する AVX1 kernel が個別に選ばれる。`STRATA_NO_IQ512`、`STRATA_NO_IQ256`、`STRATA_NO_IQ128` などの無効化条件、未対応形式、CPU ISA 不足では ggml-cpu の dot product にフォールバックする。
- `q2_native_kernels` 対象の Q2_0 gate/up/down は pool 側で別の Q2 経路を通るため、この変数の native GU/down 閾値判定の対象ではない。
- down 側でこの閾値を使うのは IQ4_NL (`d_type == 20`) の AVX2 multi-token kernel。`STRATA_NO_IQ4NL` が設定されている場合、または AVX2 が利用できない場合は ggml-cpu の dot product に進む。Q5_1/Q8_0 の `STRATA_KQ256` 経路など、別条件で選ばれる down kernelの判定はこの閾値を使わない。
- `STRATA_IQ3S_MT1` は、`STRATA_IQ_MT_MIN` が未設定のときに限り、条件を満たす IQ3_S gate/up を1 tokenから AVX2 multi-token kernelへ切り替える別の opt-in。`STRATA_IQ_MT_MIN` が空文字を含め設定されていれば、この IQ3_S 特例は適用されず、本変数の `atoi` 結果が使われる。

## 実行時の詳細

gate/up 側は `native_gu_mt_min` の初回呼び出し時に環境変数を読み、関数内 `static` に parse 結果を保持する。さらに `STRATA_IQ3S_MT1` の特例条件も同関数の static 値として初回評価される。down 側は `native_down_rows` 内で別個の static 値として読み取る。そのため実行中に環境を変更しても、各経路が初期化された後は反映されない。二つの経路は初回評価時点が別々である。

native pack の expert pool は gate/up 行の処理から `native_gu_rows` を呼び、通常の native down 行では `native_down_rows` を呼ぶ。閾値を下げるほど、複数 token 時だけでなく1 token時にも対象カーネルを選びやすくなる。閾値が2の既定経路では単独 token と複数 token の丸め差が起き得るため、同一入力での greedy 出力再現性や batch/solo の照合を優先するときに `1` が使われる。測定結果を一般化できる根拠は本調査では確認していない。

この変数自身によるログ出力、警告、エラー処理はない。

## 根拠

- `src/kernels/cpu/native_expert.cpp:124-141` — gate/up の未設定既定値、`atoi`、static 保持、IQ3_S 特例。
- `src/kernels/cpu/native_expert.cpp:143-193` — gate/up の閾値比較、ISA/形式と無効化環境変数によるカーネル選択および fallback。
- `src/kernels/cpu/native_expert.cpp:233-255` — down 側の独立した `atoi`/既定値、IQ4_NL と AVX2 条件。
- `src/kernels/cpu/pool.cpp:684-719` — native expert pool から各処理関数への呼び出し、および Q2_0 経路の分岐。
- `CMakeLists.txt:107,1317-1361`、`src/kernels/cpu/expert_layout.cpp:376-402` — native expert 機能のビルド条件と無効時の扱い。
- `docs/DETAILS.md:97-109` — 既定時の丸め差、`STRATA_IQ_MT_MIN=1` の目的、関連条件についてのプロジェクト文書。
