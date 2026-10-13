# `STRATA_KV_HOST_DMA`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の KV ストリーミングを使うプロンプト処理で、KV の host copy への書き込み方法を切り替える A/B 用の opt-in 変数です。有効時、通常形式の K/V は GPU の append kernel から host copy へ直接書かず、staging pool に追記した後で変更ブロックを host copy に DMA 転送します。CUDA ビルドでは無効です。

## 値と判定

| 条件 | 結果 |
|---|---|
| `STRATA_USE_HIP` 定義なし | `false`（コンパイル時定数） |
| `STRATA_USE_HIP` 定義あり、未設定 | `false` |
| 設定値の先頭文字が `1` | `true`。`1`、`10`、`1anything` が該当 |
| 空文字、先頭文字が `1` 以外 | `false`。`0`、`true`、` 1` などが該当 |

文字列全体や数値としての妥当性は検査しません。判定は `std::getenv()` の結果の先頭文字 `e[0] == '1'` だけです。HIP の場合、値はこのコード箇所に初めて到達した時にローカル `static const bool` として評価・保存され、プロセス中に環境を書き換えても再評価されません。根拠: `src/prefill/prefill.cpp:2669-2674`。

## 有効になる条件

- `STRATA_USE_HIP` を定義したビルドであること。CUDA では `kv_host_dma` が常に `false` です。gfx906 互換ビルドなど `STRATA_USE_HIP` を定義しないビルドにも適用されません。
- 対象 QSA layer が `st.kv_mode == 1` の staging 経路にあること。通常は `--kv-resident` による KV streaming がこのモードを使います。KV が全て VRAM にある場合は `staged` が false となり、変数は効果を持ちません。
- `st.kv_hybrid`（K8V4）では DMA 切り替えの分岐を通りません。K8V4 の append は `st.host.present()` に従って host copy と staging pool の両方へ書き込み、この変数による unstage DMA を呼びません。

## 実行時の詳細

通常形式では、環境変数が有効で staged の場合、append 関数へ渡す host destination (`host_w`) を `nullptr` にし、K/V を staging pool と常駐 VRAM slot に追記します。その後 `kv_unstage_to_host()` が staging pool から host copy へ、`p0 / page_size` から `(p0 + T + page_size - 1) / page_size` までのブロックをコピーします。無効時または非 staged 時は `st.host` を append に渡し、従来どおり append 側が host copy へも書きます。対象コードは通常の K/V と Q4 の append を含みます。

`kv_unstage_to_host()` は CUDA/HIP 共通実装で `cudaMemcpyAsync(..., cudaMemcpyDefault, stream)` を使います。HIP 用の同じ経路は `STRATA_USE_HIP` ビルドでコンパイルされます。コピー範囲が空なら関数は何もしません。転送エラーは `check("unstage")` に渡されます。根拠: `src/prefill/prefill.cpp:2694-2704`, `src/kernels/cuda/kv_stream.cu:264-272`。

ソースコメントと `docs/TROUBLESHOOTING.md` は、目的を「プロンプト中、GPU kernel が RAM 側 K/V copy に書かず DMA で転送し、回答内容は同じ」と説明しています。資料にはこの変数自体の測定値や対応 GPU 別の性能結果はありません。K8V4 については実装分岐が変数を参照せず、通常形式向けの説明を当てはめられません。根拠: `src/prefill/prefill.cpp:2664-2688`, `docs/TROUBLESHOOTING.md:166-170`。

## 根拠

- `src/prefill/prefill.cpp:2647-2675,2694-2704` — KV streaming の staging 判定、HIP 限定の値判定、通常 append への host pointer と DMA 切り替え。
- `src/kernels/cuda/kv_stream.cu:264-272` — staging pool から host copy への非同期転送。
- `include/strata/kernels/kv_stream.hpp:102-107` — 関数の宣言と用途の説明。
- `src/program/generate.cpp:394,707-708,1856` — KV streaming 状態と `--kv-resident` オプション。
- `docs/TROUBLESHOOTING.md:158-171` — Windows AMD の TDR 調査手順としての環境変数案内。
