# `STRATA_ATTN_PRE75`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

QSA のバッチ attention で、PR #540 の attention kernel を選ぶ条件を調整する A/B 用スイッチ。対象コードがビルドに含まれる場合、既定では CUDA の compute capability 7.5 未満、および HIP の `gfx103x` でこの kernel を使う。`0` で選択を止める。通常の `qsa_decode_attn_step` ではなく、`qsa_decode_attn_batch` の kernel 選択に作用する。

## 値と判定

CUDA/HIP 実装は環境変数の**先頭1文字だけ**を読み、文字列全体の比較や数値変換はしない。

| 値 | CUDA（実験ビルド） | HIP（gfx906 wave64 以外のビルド） |
| --- | --- | --- |
| 未設定 | GPU 世代による既定選択 | `gfx103x` だけ選択 |
| `0` で始まる値（`0`, `0abc` など） | 常に選択しない | 常に選択しない |
| `1` で始まる値（`1`, `10` など） | GPU 世代による既定選択のまま。sm_75 以上を強制的に有効化しない | 全対象デバイスで選択 |
| 空文字または `0`/`1` 以外で始まる値 | 未設定相当 | 未設定相当 |

CUDA/HIP では初回 `pre75_attn()` 呼び出し時に値を static 初期化し、その後の環境変更は反映しない。SYCL 実装も初回呼び出し時に static 初期化するが、判定は異なり、先頭文字が `0` のときだけ無効化する。したがって SYCL では未設定・空文字・`1` 以外の値も無効化にはならない。

## 有効になる条件

- **CUDA**: `STRATA_EXPERIMENTAL_SM60` を定義してビルドした場合だけ専用 kernel と分岐がコンパイルされる。環境変数が未設定、`1`、無効値なら、現在の GPU の compute capability が 7.5 未満の場合に選択する。7.5 以上では選択しない。実験ビルド自体は CMake で既定 OFF。
- **HIP**: `STRATA_HIP_GFX906` を定義しない HIP ビルドに分岐が含まれる。未設定・空・無効値なら、現在のデバイス名が `gfx103` で始まる場合に選択する。`1` で始まる値なら、そのビルド内の他の wave32 デバイスにも選択する。gfx906 wave64 ビルドではこの環境変数による分岐自体がコンパイルされない。
- **SYCL**: `STRATA_EXPERIMENTAL_SM60` 定義時だけ分岐がコンパイルされ、現在のデバイスの compute capability が 7.5 未満なら選択する。`0` で始まる値は GPU 世代による選択を無効化する。CUDA 実装のような強制有効化値はない。

デバイス情報の取得に失敗した場合や、device ordinal が `0..63` の範囲外の場合は選択しない。CUDA/HIP はデバイス特性を ordinal ごとにキャッシュし、SYCL 変換コードも同じく ordinal ごとに compute capability をキャッシュする。レイヤー分割などで複数 GPU を使う場合も、現在のデバイスごとに条件を評価する。

## 実行時の詳細

この設定は QSA attention の計算式や入力値を変えるのではなく、`qsa_decode_attn_batch` が起動する chunk kernel を切り替える。`pre75_attn()` が真なら PR #540 の実装、偽なら標準実装を選ぶ。バッチ関数は prefill、verification、MTP などから呼ばれている。ソースコメントは PR #540 の kernel を同じ演算順の bit-exact な実装と説明しているが、この調査では独自の実行・測定は行っていない。

この変数専用のログ出力はない。通常ビルドで該当コードがコンパイルされていない場合、設定しても効果はない。

## 根拠

- `src/kernels/cuda/qsa_decode_attn.cu:282-290` — kernel の説明と CUDA/HIP でのコンパイル条件。
- `src/kernels/cuda/qsa_decode_attn.cu:575-614` — 値の読み方、static 初期化、CUDA/HIP ごとのデバイス判定と kernel 選択マクロ。
- `src/kernels/cuda/qsa_decode_attn.cu:618-620, 690-701` — バッチ関数と選択された kernel の起動箇所。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:308-312, 550-576` — SYCL 側のビルド条件、値の判定、compute capability による選択。
- `CMakeLists.txt:154-154, 188-192` — CUDA の `STRATA_EXPERIMENTAL_SM60` は既定 OFF で、ON 時に compile definition を付ける。
- `src/prefill/prefill.cpp:2848`, `src/core/verify.cpp:1376-1391`, `src/core/mtp.cpp:825` — CUDA/共通側の batch 関数の呼び出し例。SYCL 側にも対応する呼び出しがある。
- `docs/OLDER_GPUS.md:26, 98-100`, `docs/NVIDIA_V100.md:33` — gfx103x の既定選択、`=0` による停止、CUDA sm_70 での位置づけに関する説明。これらはソース上の条件と照合した。`docs/DETAILS.md` にこの変数の記載は見つからなかった。
