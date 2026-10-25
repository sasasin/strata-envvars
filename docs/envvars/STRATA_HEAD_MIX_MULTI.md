# `STRATA_HEAD_MIX_MULTI`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

Verifier の最終 hyper-connection mixer と MTP draft head の mixer で、複数 token の mixer read を `fused_gr_read_multi()` にまとめるかを制御する。有効時は window の各 token/row を一つの multi-row 呼び出しで処理し、無効時は token/row ごとに `gr_read()` を呼ぶ。実装コメントは同じ和（bitwise identical sums）としている。通常の層内 mixer や residual write を一括化する変数ではない。

## 値と判定

値は `std::atoi()` で変換され、変換結果が 0 かどうかで判定される。文字列全体の妥当性確認はない。未設定時の既定値は backend により異なる。

| Backend | unset | 設定時 |
|---|---|---|
| CUDA（`src/`） | 有効 | `atoi(value) != 0` なら有効 |
| HIP（`src/`、`STRATA_USE_HIP`） | 無効 | `atoi(value) != 0` なら有効 |
| SYCL（`sycl/src/`） | 有効 | verifier と MTP とも `atoi(value) != 0` なら有効 |

したがって、`0`、空文字、数字に変換できない文字列は無効。`1` や `-1` は有効。先頭空白や符号は `atoi()` の規則で処理され、数字の後ろに文字が続いても数値部分が 0 以外なら有効（例: `2abc`）。たとえば `0abc` は無効。

## 有効になる条件

- Verifier では、最終 mixer の分岐に到達し、`fuse_head_gr` が false で、かつ `head_ != nullptr && head_->loaded()` の場合に multi-read を選ぶ。`STRATA_FUSE_HEAD_GR` で fused head/residual 経路が有効なら、こちらの値にかかわらず先にその経路が選ばれる。
- MTP では最終 mixer の分岐で `fuse_head_gr` が false かつ本変数が有効なら multi-read を選ぶ。無効なら各 row の `gr_read()` に戻る。
- HIP は未設定では無効であり、明示的に `atoi()` が非 0 になる値を設定した場合だけ有効になる。SYCL 側の実装は `STRATA_USE_HIP` 分岐を持たず、既定有効の判定を使う。
- verifier の multi-read 経路では、output hyper-connection weights が期待する engine form でない場合、処理を失敗させ `verify: the output_hc_* weights have the wrong engine forms` をエラーに設定する。

## 実行時の詳細

値は verifier の `head_mix_multi_enabled()`、または MTP の `mtp_forward()` 相当の処理内にある function-local `static` 初期化で読み込まれる。各箇所で最初に評価した結果をプロセス内に保持するため、その後の環境変数変更は反映されない。Verifier と MTP は別々に初期化する。

multi 経路では token/row ごとの `FusedGrArgs` を作り、`apply = false` として各 row の `R`、norm/down/up weights、epsilon、offset、recurrent state、出力先を設定し、`fused_gr_read_multi()` を呼ぶ。無効時は同じ mixer weights 等を使い、row ごとに `gr_read()` を呼ぶ。Verifier ではその後、得られた `head_mixed_` を Q8_1 量子化して出力 head に渡す。MTP では `sample_` を量子化して draft head に渡す。環境変数自体によるログ出力は確認できない。

## 根拠

- `src/core/verify.cpp:208-223`: CUDA/HIP の既定値と `atoi()` 判定。
- `src/core/verify.cpp:1742-1767`: verifier の優先分岐、loaded head 条件、weight form エラー、multi-read と per-token fallback。
- `src/core/mtp.cpp:858-866,944-975`: MTP における CUDA/HIP の値判定と最終 mixer の multi-read / per-row fallback。
- `sycl/src/core/verify.cpp:177-189,1590-1614`: SYCL verifier の既定有効判定と適用箇所。
- `sycl/src/core/mtp.cpp:993-1000,1092-1123`: SYCL MTP の値判定と適用箇所。
- `docs/A770_SPEED_SPEC.md:662-665` は `fused_gr_read_multi` の standalone kernel 測定に触れるが、本環境変数の既定値や運用条件は説明していない。測定値を本変数の効果としては扱っていない。
