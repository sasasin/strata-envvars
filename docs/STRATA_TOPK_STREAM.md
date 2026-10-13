# `STRATA_TOPK_STREAM`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

CUDA の QSA prompt top-k 選択で、Turing（sm_75）の大きな prefill に広幅 top-k kernel を使う帯域を有効にします。`=0` はその追加の Turing 帯域を抑え、条件を満たす場合に register kernel を選ばせます。top-k の選択結果は同じで、変わるのは kernel の選択です。

## 値と判定

`src/kernels/cuda/qsa_select.cu` の `qsa_block_topk()` 内で `std::getenv()` の結果を一度だけ読む static local 値です。文字列全体の parse や真偽値変換はしません。

| 値 | `turing_wide` |
|---|---|
| unset | `true` |
| 空文字 | `true`（設定済みだが先頭文字 `\0` は `'0'` ではない） |
| 先頭文字が `'0'` | `false`（例: `0`, `0abc`, `00`） |
| その他すべて | `true`（例: `1`, `false`, `-1`, ` 0`） |

大文字小文字、空白、後続文字、数値としての妥当性は判定しません。判定値は初めてコードがこの static 初期化箇所に到達したときに固定されます。以後の環境変更は反映されません。初回呼び出しが別 kernel で return するなど、この箇所を通らなければ、まだ読み取り・固定されません。

## 有効になる条件

- 通常の CUDA top-k dispatch で、`nq > 0`、旧 kernel 指定などによる早期 return がなく、geometry 検査を通過する必要があります。sm_90 以降で cluster kernel が選ばれて return する場合も、この環境変数の判定箇所には到達しません。
- 追加の `turing_wide` 条件は、CUDA 側で `counted` が true、すなわち `STRATA_TOPK_CAPACITY_GUARD` が設定されておらず、呼び出し側が有効な `active_blocks` を渡し、GPU が Turing（compute capability 7.5）である場合に働きます。`STRATA_TOPK_ACTIVE_ANY=1` はコード上この GPU 判定のテスト用代替です。
- `reach` は通常、counted prefill では `active_blocks`（上限 `max_blocks`）、それ以外では `max_blocks` です。広幅 kernel は `reach > fit` ならこの環境変数にかかわらず選ばれます。したがって先頭文字 `0` が抑えるのは、`counted && reach > 22528` という追加帯域だけであり、register kernel の収容上限を超えた場合の広幅 kernel までは抑えません。
- 主な通常経路では prefill が `active_blocks` を渡します（`src/prefill/prefill.cpp`）。decode 呼び出しは通常その引数を省略するため、この Turing 帯域条件は成立しません。ただし `reach > fit` の容量条件による広幅 kernel は別です。
- HIP コンパイルでは `#if !defined(__HIPCC__)` の範囲外となり、この変数は読み取られません。SYCL build は `sycl/src/kernels/cuda/qsa_select.dp.cpp` の移植版を使い、同じ判定・dispatch 条件を持ちます。SYCL の各デバイスで Turing 条件が成立することまでは、このコードと資料から確認できません。

## 実行時の詳細

`qsa_block_topk()` は、旧 kernel 指定または適用可能な小サイズ fallback を先に処理し、その後で geometry を確認します。残った CUDA 経路は、`reach > fit` または（`turing_wide && counted && reach > 22528`）なら `block_topk_wide_kernel` を起動し、それ以外は `block_topk_reg_kernel` を使います。CUDA ソースでは `TK_T=1024`、`TK_PER=33` で、CUDA の `TK_PER_MAX` も 33 です。

環境変数専用のログはありません。この変数の読み取り箇所から子プロセスへ転送・上書きする処理もありません。選択された kernel の CUDA 起動失敗は共通の `qsa_block_topk: <CUDA error>` を stderr に出して終了します。

## 文書との照合

`docs/TROUBLESHOOTING.md` は RTX 20（Turing）で約 90K tokens を超える prompt の top-k が広幅 kernel を使い、`STRATA_TOPK_STREAM=0` で従来 kernel に戻せると説明しています。CUDA 実装の追加条件は `reach > 22528` blocks です（各 block が4 cellsのコメント上の関係から約90K cellsに相当）。同資料と実装コメントは選択 ID が同じとしています。`docs/DETAILS.md` はこの変数を troubleshooting 項目として案内しています。資料に測定条件や性能値の十分な説明はないため、ここでは速度向上を主張しません。

## 根拠

- 読み取り、早期 return、geometry 判定、kernel dispatch: `src/kernels/cuda/qsa_select.cu:1295-1362`。
- Turing のデバイス判定: `src/kernels/cuda/qsa_select.cu:1211-1227`。
- kernel のブロック幅と選択 ID のコメント: `src/kernels/cuda/qsa_select.cu:555-567`。
- 通常の prefill が `active_blocks` を渡す箇所: `src/prefill/prefill.cpp:2760-2775`。decode 側で引数を省略する例: `src/core/layer.cpp:1129`。
- CUDA build への組み込み: `CMakeLists.txt:365-383`。SYCL が移植版を解決する規則と対象 kernel: `sycl/CMakeLists.txt:87-96,205-214`; 判定箇所: `sycl/src/kernels/cuda/qsa_select.dp.cpp:2003-2011`。
- 利用者向け説明: `docs/TROUBLESHOOTING.md:93-94`, `docs/DETAILS.md:278-279`。
