# `STRATA_MULTI_BLOCK_ARGMAX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU head 処理で、語彙 logits の argmax や選択 token の確率計算を複数ブロックで処理する機能を許可・抑止する。主な適用先は CUDA/HIP/SYCL の MTP draft token 選択で、`argmax_rows_wanted()` が真になる実行経路では verifier と drafter の greedy argmax にも関係する。CPU 処理や通常のサンプリング設定を直接変更する変数ではない。読み取り関数は CUDA/HIP 実装と SYCL 実装にそれぞれある（`engine/src/kernels/cuda/verify_kernels.cu:1080-1102`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:1886-1896`）。

## 値と判定

両実装とも `std::getenv` の結果を `std::atoi` に渡し、文字列全体の妥当性検査はしない。数値変換結果が 0 なら無効、0 以外なら有効。`atoi` は先頭の空白と符号を許し、先頭の整数部分を読み、後続の非数字を無視する。数値変換できない文字列は 0 になる。したがって `1`、`-1`、`1junk`、` 1` は有効、`0`、`0junk`、空文字、`true`、`false` は無効。大文字小文字の比較はない。`atoi` の後に clamp や範囲検査はない。

| ビルド・経路 | unset | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| CUDA（`STRATA_HIP_GFX906` なし） | 有効 | `atoi(value) != 0` | `atoi(value) == 0` |
| HIP（`STRATA_HIP_GFX906` なし） | `gfx12` 以外では無効、`gfx12` では有効 | `gfx12` で `atoi(value) != 0` | 全 arch で `atoi(value) == 0` |
| HIP（`STRATA_HIP_GFX906` 定義） | 常に無効。環境変数を読まない | なし | 常に無効 |
| SYCL（`__HIPCC__` なし） | 有効 | `atoi(value) != 0` | `atoi(value) == 0` |
| SYCL（`__HIPCC__` 定義） | 常に無効。環境変数を読まない | なし | 常に無効 |

CUDA/HIP 側の HIP gfx12 判定は、`cudaGetDevice` と `cudaGetDeviceProperties` が成功し、デバイス番号が 0–63 の範囲である場合に行う。デバイスごとの arch 判定は `static arch[64]` に保持する（`engine/src/kernels/cuda/verify_kernels.cu:1080-1102`）。SYCL 実装は `__HIPCC__` の場合を除き、値だけで許可を判定する（`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:1886-1896`）。

## 有効になる条件

- CUDA/HIP または SYCL の GPU kernel 実装が使われる必要がある。CPU 経路からこの判定関数を使う呼び出しは確認できない。
- CUDA では unset が許可扱いで、明示的な 0 相当だけが抑止する。HIP は許可判定の後に arch 条件が加わり、`STRATA_HIP_GFX906` ビルドでは常に無効。
- HIP の `gfx12` 判定はデバイスごとにキャッシュされる。`cudaGetDevice` の失敗、デバイス番号が範囲外、または device properties の取得失敗時は false になる（`engine/src/kernels/cuda/verify_kernels.cu:1089-1099`）。
- 通常 verifier の greedy argmax を `argmax_rows` にするには、さらに `argmax_rows_wanted()` の条件が要る。CUDA では未指定時は compute capability major 8 が対象で、major 7 は `STRATA_ARGMAX_ROWS_SM70` が非 0 の場合に対象。`STRATA_ARGMAX_ROWS` が明示されるとその値が優先され、0 以外ならこの変数の許可判定と組み合わせて対象になる。SYCL は未指定時 major 8 のみが対象で、このビルドには `STRATA_ARGMAX_ROWS` override はない（`engine/src/kernels/cuda/verify_kernels.cu:1104-1135`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:1898-1912`）。
- verifier が head bitplane 処理を使った場合、または split head の対象 window の場合、CUDA verifier は `argmax_rows_wanted()` の判定と greedy fallback を通らない（`engine/src/core/verify.cpp:3108-3119,3130-3141`）。SYCL verifier には同じ条件分岐はない（`engine/sycl/src/core/verify.cpp:1937-1956`）。
- MTP の通常 token 選択では、変数が有効なら `row_top_prob_split`、無効なら `row_top_prob` を使う。`argmax_rows_wanted()` も真なら argmax 自体も `argmax_rows` に切り替える（`engine/src/core/mtp.cpp:1533-1543,2654-2664`、`engine/sycl/src/core/mtp.cpp:1238-1248`）。
- CUDA と SYCL の MTP `coupled_rec_` 経路は独自の `coupled_draft_sample`（または CUDA の条件により `spec_draft_sample`）を呼び、その場で return するため、この後の `argmax_rows_wanted()` と `multi_block_head_ops()` による選択を通らない（`engine/src/core/mtp.cpp:1521-1531`、`engine/sycl/src/core/mtp.cpp:1231-1236`）。
- CLI 引数や設定ファイルからこの値を上書きする読み取り・転送経路は見つからなかった。

## 実行時の詳細

CUDA/HIP では `multi_block_head_ops()` の初回呼び出しで値を読み、関数内 `static const int env` に保存する。HIP gfx 判定は別の関数内 static 配列にデバイスごとに保存する。SYCL では初回呼び出し時に値を `static const bool on` に保存する。したがって同一プロセス中に環境値を変更しても再評価されない（`engine/src/kernels/cuda/verify_kernels.cu:1080-1101`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:1886-1896`）。

リポジトリ全体で名前を検索したところ、上記 2 箇所以外にはヘッダーの説明コメントと `terminal/data/settings-register.json` の登録名があった。登録 JSON は設定項目のメタデータであり、値を読む実装ではない（`engine/include/strata/kernels/verify_kernels.hpp:241-243`、`terminal/data/settings-register.json:26398-26435`）。

MTP では head logits の各行に対する greedy token を選び、選んだ token の確率計算を行う。許可された場合は複数ブロック実装を呼び、それ以外は既存の一ブロック関数を呼ぶ。実装コメントは `argmax_rows` を一ブロック greedy pick と bitwise 同じものとして記述しているが、この調査では build や実行による再検証はしていない（`engine/include/strata/kernels/verify_kernels.hpp:217-225`、`engine/src/core/mtp.cpp:1533-1543`）。CUDA verifier でも条件を満たす場合は greedy pick を `argmax_rows` にし、そうでなければ `sample_tokens` の greedy 設定を使う（`engine/src/core/verify.cpp:3127-3140`）。

## ログと測定値

この変数の値や有効・無効理由を出力するログは、確認した読み取り・呼び出し経路にはない。呼び出される複数ブロック kernel の launch error は既存の `check("argmax_rows")` / `check("row_top_prob_split")` に渡るが、当該 kernel のエラー時は `check` が `stderr` に `<名前>: <CUDA error string>` を出して `exit(1)` する（`engine/src/kernels/cuda/verify_kernels.cu:24-27,985-992,1015-1020`）。この変数固有の測定値は `docs/DETAILS.md` などの資料で確認できなかった。

## 根拠

- `engine/src/kernels/cuda/verify_kernels.cu:1080-1102` — CUDA/HIP の読み取り、変換、既定値、gfx12 条件。
- `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:1886-1917` — SYCL の読み取り、既定値、GPU major 条件、例外時の終了経路。
- `engine/src/kernels/cuda/verify_kernels.cu:985-992,1015-1020` — CUDA の複数ブロック kernel 呼び出しとエラー処理。
- `engine/src/core/verify.cpp:3127-3141`、`engine/sycl/src/core/verify.cpp:1946-1956` — verifier の greedy 経路。
- `engine/src/core/mtp.cpp:1521-1543,2649-2664`、`engine/sycl/src/core/mtp.cpp:1226-1248` — MTP の選択・確率計算経路。
- `engine/include/strata/kernels/verify_kernels.hpp:217-246` — kernel と判定関数の宣言・設計上の説明。
