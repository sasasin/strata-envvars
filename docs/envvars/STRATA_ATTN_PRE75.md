# `STRATA_ATTN_PRE75`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA attention の chunk 計算で、PR #540 の `attn_chunk_kernel_pre75` を選ぶかどうかを切り替える A/B 用環境変数。選ばれると chunk 部分和の計算 kernel が変わる。merge kernel や index/top-k の選択処理を分岐させる変数ではない。CUDA/HIP の `qsa_decode_attn_step` と `qsa_decode_attn_batch` の chunk 経路で参照される（`engine/src/kernels/cuda/qsa_decode_attn.cu:926-976,1038-1116,1309-1349`）。

標準 CUDA build では `STRATA_ATTN_DAILY` の選択もこの分岐に関わる。HIP では `gfx103x` を既定対象にし、値 `1` で別の wave32 GPU にも拡張する。SYCL ファイルには読み取りを含む `pre75_attn()` があるものの、その関数は同ファイルで呼び出されず、現行 SYCL の decode kernel 選択にこの変数が使われる経路は確認できない（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:767-792,1001-1015,1307-1395`）。

## 値と判定

CUDA/HIP の `pre75_attn()` は最初の呼び出しで `std::getenv` の結果を関数内 `static` に保存する。未設定なら `-1`、値の先頭文字が `0` なら `0`、先頭文字が `1` なら `1`、それ以外なら `-1`。文字列全体の比較や数値変換はせず、空文字・空白・大文字小文字・後続文字の妥当性検査もない（`engine/src/kernels/cuda/qsa_decode_attn.cu:930-935`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA experimental build (`STRATA_EXPERIMENTAL_SM60`) | `STRATA_ATTN_DAILY=1` なら on、それ以外は GPU compute capability が 7.5 未満なら選択 | `1`, `1anything` は明示の on 判定。ただし `STRATA_ATTN_DAILY` が on でない場合、実際の CUDA 判定は device capability `< 75` で、`1` だけでは新しい GPU に強制しない | `0`, `0anything` は off。`true`, 空文字, ` 1`, `2` は環境指定としては無効（unset 相当） |
| 標準 CUDA build（`STRATA_EXPERIMENTAL_SM60` なし） | `STRATA_ATTN_DAILY` の判定に従う | `1`, `1anything` は `pre75_attn()` 内で認識されるが、標準 CUDA 分岐では `STRATA_ATTN_DAILY` の結果が使われるため強制 on にはならない | `0`, `0anything` は明示的に off。それ以外は `STRATA_ATTN_DAILY` の判定に従う |
| HIP（`STRATA_HIP_GFX906` でない build） | `gfx103x` なら on、それ以外は off | `1`, `1anything` は全対象デバイスで on | `0`, `0anything` は off。空文字、`true`, ` 1`, `2` は unset 相当となり、`gfx103x` の既定判定を使う |
| SYCL | 実行時に読み取られない | 該当なし | 該当なし |

CUDA/HIP の例外として、`STRATA_ATTN_PRE75=0` は先に off を返すため `STRATA_ATTN_DAILY=1` より優先する。標準 CUDA ではそれ以外の値は `daily_attn()` に委譲される。`daily_attn()` 自体は `STRATA_ATTN_DAILY` が文字列全体でちょうど `1` の場合だけ明示 on とし、それ以外（unset/空文字を含む）は device ごとの既定判定を使う（`engine/src/kernels/cuda/qsa_decode_attn.cu:902-923,935-940`）。

## 有効になる条件

- **CUDA experimental build:** `STRATA_ATTN_PRE75_BUILT` は CUDA では定義される。`STRATA_EXPERIMENTAL_SM60` 有効時、`pre75_attn()` は現在 device の compute capability が 7.5 未満かを判定し、該当 device の chunk kernel 選択に使われる（`engine/src/kernels/cuda/qsa_decode_attn.cu:503-505,936-964`）。
- **標準 CUDA build:** `STRATA_ATTN_PRE75=0` 以外の設定は `daily_attn()` の結果に従う。`STRATA_ATTN_DAILY=1` なら対象 kernel を使い、それ以外は `sm12x_default(...)` による device ごとの既定値に従う（`engine/src/kernels/cuda/qsa_decode_attn.cu:902-923,936-938`）。
- **HIP:** `STRATA_HIP_GFX906` を定義しない HIP build でこの kernel が組み込まれる。既定では device 名が `gfx103` で始まると有効。先頭 `1` は他の対象 wave32 device にも有効化し、先頭 `0` は無効化する。`STRATA_HIP_GFX906` build では `STRATA_ATTN_PRE75_BUILT` が定義されず、この選択コードは組み込まれない（`engine/src/kernels/cuda/qsa_decode_attn.cu:503-505,945-963`）。
- **別 kernel が先に選ばれる経路:** CUDA/HIP の batched chunk 処理では `STRATA_ATTN_LANECELL` が有効なら lane-cell kernel が先に使われる。CUDA の INT8 chunk-down 経路 (`attn_v3_on()`) も通常の pre75 chunk 選択を通らない（`engine/src/kernels/cuda/qsa_decode_attn.cu:1041-1042,1057-1064,1095-1116,1132-1142`）。
- **複数 slot / row:** pre75 kernel が有効でも `STRATA_ATTN_PRE75_SLOTS` が off なら fused slot 呼び出しは `false` を返し、呼び出し側は各 query を通常の batch 関数へ fallback する。rows 経路も per-row 呼び出しへ切り替える。これは pre75 kernel 自体の無効化ではない。明示的な `STRATA_ATTN_PRE75_SLOTS` は `atoi(v) != 0`、未設定なら `STRATA_BATCH_QSA_STREAM_OPT` の `atoi` 結果で判定する（`engine/src/kernels/cuda/qsa_decode_attn.cu:978-990,1167-1172,1252-1270`; 呼び出し側 `engine/src/core/verify.cpp:2435-2447,2466-2468`）。
- **SYCL:** `STRATA_EXPERIMENTAL_SM60` のときだけ `pre75_attn()` を定義するが、`rg` で確認できる同関数の参照は定義内と未展開の `STRATA_ATTN_CHUNK` マクロだけで、呼び出し箇所がない。SYCL の `qsa_decode_attn_batch` と `qsa_decode_attn_step` は通常の `attn_chunk_kernel` を直接起動する（`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:767-792,1001-1015,1307-1395`）。

## 実行時の詳細

CUDA/HIP の環境値は `pre75_attn()` の最初の実行時に一度読み取られ、プロセス内で cache される。後からプロセス環境を書き換えても再評価されない。GPU の compute capability / HIP arch 判定も `cc[64]` に device index ごとに cache される。CUDA の標準 build では `daily_attn()` の環境値も同様に一度 cache される（`engine/src/kernels/cuda/qsa_decode_attn.cu:902-923,930-964`）。

pre75 が選ばれると、各 K/V mode（FP16、INT8、Q4、INT8 K + Q4 V）について `attn_chunk_kernel_pre75` 系を起動し、既定分岐では `attn_chunk_kernel` 系を起動する。HIP の pre75 kernel は wave32 用のテンプレート引数で起動される。`qsa_decode_attn_step` は QSA decode の通常 attention 経路から呼ばれ、batch 経路も pre75 判定を chunk launch に渡す（`engine/src/core/layer.cpp:1287-1289`; `engine/src/kernels/cuda/qsa_decode_attn.cu:1038-1040,1101-1116,1132-1142,1309-1349`）。

## ログと測定値

この環境変数の値や選択 kernel を示す専用ログは確認できない。device の取得・属性問い合わせに失敗すると `pre75_attn()` は `false` を返し、CUDA runtime error state を消去する。kernel 起動後のエラーは `qsa_decode_attn_batch: %s` または `qsa_decode_attn: %s` を stderr に出して `exit(1)` する（`engine/src/kernels/cuda/qsa_decode_attn.cu:942-960,1143-1147,1350-1354`）。

`docs/SETTINGS.md` はこの変数を「NVIDIA and AMD, Intel Arc」と記載しているが、SYCL decode 側の関数に呼び出しがなく、現在確認したソースから Intel Arc 上での実効性は裏付けられない。`docs/OLDER_GPUS.md` と `docs/NVIDIA_V100.md` の説明は一部の GPU 条件を示す資料として確認したが、現行の挙動は上記ソース分岐に基づく。資料上の性能値は本調査で再測定していない（`docs/SETTINGS.md:28`; `docs/OLDER_GPUS.md:143`; `docs/NVIDIA_V100.md:42`）。

## 根拠

- `engine/src/kernels/cuda/qsa_decode_attn.cu:492-505` — kernel の build 条件。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:902-923,926-990` — `STRATA_ATTN_DAILY`、対象変数、slot fallback の判定。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:1038-1116,1132-1147,1150-1224,1227-1301,1309-1354` — chunk/slot/rows/step の実際の kernel 選択とエラー経路。
- `engine/src/core/layer.cpp:1287-1289`; `engine/src/core/verify.cpp:2435-2447,2466-2468` — decode および verify からの呼び出し。
- `engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:767-792,1001-1015,1307-1395` — SYCL 側の未使用関数と通常 kernel の起動。
- `docs/SETTINGS.md:28`; `docs/OLDER_GPUS.md:143`; `docs/NVIDIA_V100.md:42` — ソースと照合した説明資料。
