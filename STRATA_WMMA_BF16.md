# `STRATA_WMMA_BF16`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。Strata 所有ソースを対象とし、外部ライブラリ内部の環境変数の動作は対象外。

## 役割

AMD HIP ビルドの BF16 prefill GEMM で、Strata の RDNA3/RDNA3.5 WMMA カーネルを使うかを制御します。この変数は単独では WMMA を有効化しません。別の `STRATA_WMMA_GEMM` が有効であるとき、`STRATA_WMMA_BF16` が無効なら BF16 GEMM だけ WMMA 試行を飛ばします。FP16 GEMM の WMMA 分岐はこの変数を読みません。

実行対象の GEMM は `Y[t,n] = beta * Y[t,n] + sum_k W[n,k] * X[t,k]` です。WMMA カーネルが形状やデバイス条件を受け付けない場合、呼び出し元は通常の BF16 GEMM 処理を続けます。

## 値と判定

HIP の `Gemm::bf16()` 内で `std::getenv()` の結果を先頭文字だけで判定します。空文字は設定済みですが、先頭文字が `\0` なので無効です。

| `STRATA_WMMA_BF16` | 判定 | 結果（`STRATA_WMMA_GEMM` も有効な場合） |
|---|---|---|
| 未設定 | 有効 | BF16 WMMA を試行する |
| 空文字 | 無効 | BF16 WMMA を試行しない |
| 先頭文字が `0` | 無効 | BF16 WMMA を試行しない（例: `0`, `0abc`） |
| その他の先頭文字 | 有効 | BF16 WMMA を試行する（例: `1`, `true`, `false`, `2`） |

文字列全体、数値としての妥当性、大文字小文字、前後の空白は検査されません。したがって文字列 `false` は有効です。根拠: `src/prefill/gemm.cu:579-583` と `sycl/src/prefill/gemm.dp.cpp:754-758`。

## 有効になる条件

BF16 WMMA 呼び出しには、次の条件が必要です。

- HIP 用の `STRATA_USE_HIP` 分岐であること。通常の CUDA ビルドではこの環境変数判定と呼び出しはコンパイル対象外です。HIP ビルドは `strata_prefill` に `wmma_gemm.cu` を追加します（`CMakeLists.txt:589-593`）。
- `STRATA_WMMA_GEMM` が設定され、空文字ではなく、先頭文字が `0` 以外であること。未設定、空文字、`0...` は WMMA 全体の試行を無効にします（`src/prefill/gemm.cu:577-582`）。
- `STRATA_WMMA_BF16` が上表で有効であること。
- `ldx <= K` であること。`Gemm::bf16()` はこの場合 `ldx` を 0 に正規化しますが、`ldx > K` なら WMMA 分岐を通りません。
- `T >= 16` で、`beta` が `0.0f` または `1.0f` であること。
- WMMA 実装側が受け付けること: X/W/Y が null でない、T/N/K が正、実行中デバイスが対応 gfx11、K が 16 の倍数、`ldy >= N`。呼び出し元が `ldy <= 0` を N に置き換えてから渡します。

WMMA 実装の gfx11 判定は `gfx1100`, `gfx1101`, `gfx1102`, `gfx1150`, `gfx1151` に限られます。ビルド時に `STRATA_WMMA_GFX11` が定義されていない場合の実装は `false` を返す stub です。条件不成立や stub の場合、呼び出し元は早期 return せず通常経路へ進みます。根拠: `src/prefill/wmma_gemm.cu:31-56,264-301,710-735`。

## 実行時の詳細

`STRATA_WMMA_BF16` と `STRATA_WMMA_GEMM` は、それぞれ関数内の `static const bool` として初回評価結果を保持します。環境値の変更は、その `Gemm::bf16()` 関数が最初に評価された後には反映されません。要求条件を満たして WMMA 関数が `true` を返すと BF16 GEMM はそこで完了します。`false` のときは、HIP の FP16 入出力経路が有効ならその変換経路を試し、その後 hipBLASLt が利用可能で受け付ければそれを使い、そうでなければ標準の GEMM 呼び出しへ進みます（`src/prefill/gemm.cu:581-607,667-672`）。

SYCL 側の変換済み prefill ソース `sycl/src/prefill/gemm.dp.cpp` にも同じ環境判定と WMMA 呼び出しがあります（`754-758`）。ただし、そこも `STRATA_USE_HIP` の条件ブロック内です。SYCL 側は `strata_resolve()` で prefill ソースを解決してビルドする構成です（`sycl/CMakeLists.txt:232-236`）。

## 文書との照合

`docs/STRIX_HALO.md` と `docs/AMD_HIP.md` には関連する AMD WMMA 機能の説明がありますが、`STRATA_WMMA_BF16` の値規則や既定値は記載されていません。ここでは実装の分岐を根拠にし、性能や数値精度に関する主張は行いません。

## 根拠

- `src/prefill/gemm.cu:571-607,667-672` — HIP の BF16 GEMM 分岐、環境値判定、fallback。
- `sycl/src/prefill/gemm.dp.cpp:746-782` — SYCL 側にある同じ条件分岐。
- `src/prefill/wmma_gemm.cu:31-56,264-301,710-735` — gfx11 の実行時判定、WMMA の追加条件、非対応ビルド用 stub。
- `CMakeLists.txt:589-593` — HIP ビルドで WMMA 実装ソースを追加。
- `docs/STRIX_HALO.md`, `docs/AMD_HIP.md` — 関連機能の資料を照合。対象変数の具体的な値規則は記載なし。
