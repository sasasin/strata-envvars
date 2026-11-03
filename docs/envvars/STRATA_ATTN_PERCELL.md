# `STRATA_ATTN_PERCELL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL backend の QSA prompt prefill で、通常の prompt attention kernel が使えない場合に選ぶ fallback を切り替えます。既定は per-cell score kernel です。`STRATA_ATTN_PERCELL=0` とすると `qsa_decode_attn_batch()` を使います。CUDA/HIP backend の同名候補を制御する読み取りは見つかりませんでした。

この切り替えは QSA layer の prompt 処理だけにあります。QSA でない layer、decode、または通常の SYCL prompt kernel が成功する場合には適用されません。QSA layer の処理と切り替え位置は `sycl/src/prefill/prefill.cpp:3243-3245,3526-3569` にあります。

## 値と判定

値全体の parse や数値変換はせず、`getenv()` の結果の先頭文字だけを調べます。判定結果は `static const bool` に保持されます。

| 設定 | 結果 |
|---|---|
| 未設定 | 有効（per-cell kernel） |
| 空文字 | 有効（先頭文字は `\0` で `'0'` ではない） |
| 先頭文字が `0` | 無効。例: `0`, `0abc` |
| それ以外 | 有効。例: `1`, `true`, `false`, `2`, 空白で始まる文字列 |

大文字小文字、空白、残りの文字、数値としての妥当性は検査されません。したがって文字列 `false` も有効です。判定実装は `sycl/src/prefill/prefill.cpp:3557-3568` です。

## 有効になる条件

- SYCL build の `strata_prefill` に含まれる実装であること（`sycl/CMakeLists.txt:275-279`）。
- prompt が QSA layer に到達すること（`sycl/src/prefill/prefill.cpp:3243-3245`）。
- `qsa_prompt_attn_batch()` が prompt kernel を実行せず `false` を返すか、`STRATA_PROMPT_ATTN_OLD` が設定されていて呼び出しを短絡すること。SYCL ではこの関数が ESIMD / XMX prompt kernel を試し、いずれも実行できない場合に `false` を返します（`sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1972-1974,2011-2015`）。ESIMD / XMX の有効条件と fallback はそれぞれ `sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:405-418`、`sycl/src/kernels/cuda/qsa_prompt_attn_xmx.dp.cpp:368-388` にあります。
- `STRATA_PROMPT_ATTN_OLD` は値ではなく設定有無で判定されます。空文字を含め、設定されていれば `qsa_prompt_attn_batch()` を呼ばず fallback に進みます（`sycl/src/prefill/prefill.cpp:3529-3554`）。

これらの条件を満たさない場合、`STRATA_ATTN_PERCELL` の値は読まれず、この分岐には影響しません。CLI 引数による上書きはこの読み取り箇所にはありません。

## 実行時の詳細

fallback に入ると、初回にこの分岐へ到達した時点で環境変数を読み、そのプロセス内では値をキャッシュします。後から環境を変更しても再評価されません。真なら `qsa_prompt_attn_percell()`、偽なら `qsa_decode_attn_batch()` を chunk ごとに呼びます（`sycl/src/prefill/prefill.cpp:3553-3569`）。per-cell kernel は 128 cell 単位で score を計算し、値の集約には warp kernel の処理を使います。ソースコメントでは FP32 だが warp kernel と加算順が異なり、bitwise 一致しないとされています（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:713-719,763-768,1282-1303`）。

この変数専用のログ、警告、無効値エラーはありません。いずれの値でもコードは二つの kernel 呼び出しの一方へ分岐します。warp fallback の `qsa_decode_attn_batch()` は geometry 不正または必須 buffer 不在時に stderr へ `qsa_decode_attn_batch: unsupported geometry or missing buffers` を出して `exit(1)` します（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:876-882`）。後続の attention 出力処理は共通です（`sycl/src/prefill/prefill.cpp:3570-3575`）。

## 根拠

- 候補名の全参照は `sycl/src/prefill/prefill.cpp:3558-3559` のみで、環境から値を読む実装を確認しました。helper 経由や動的な名前の参照はありませんでした。
- per-cell kernel の実装と精度注記: `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:713-719,763-768,1282-1303`。
- prompt attention kernel の試行・fallback: `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1972-2015`。
- `docs/DETAILS.md` にこの変数の個別説明は見当たりませんでした。
