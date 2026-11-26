# `STRATA_NO_MMVQ_ROWS2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata の native multi-column MMVQ（複数列の量子化行列ベクトル積）で、条件を満たすときに出力行あたり 1 row の kernel を選ぶ設定です。通常の exact multi-column 経路は 2 行単位ですが、この変数が有効なら一定以上の入力長で 1 行単位の kernel を使います。CUDA/HIP 実装は `launch_multi_n`、SYCL 実装も同名関数で判定します（`engine/src/kernels/cuda/native_mmvq.cu:1677-1710`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2202-2278`）。

この設定は全ての MMVQ 呼び出しを変えるわけではありません。native Q8_0 の 1 列経路や、packed Q8_0・RDNA WMMA への早期分岐はこの判定を通りません。`ncols > 1` の native multi-column 呼び出しでも `g_multi_exact` が false なら、変数を読む前に別の常時 2 行経路へ戻ります（`engine/src/kernels/cuda/native_mmvq.cu:1685-1704,2581-2605,3699-3704`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2202-2224`）。

## 値と判定

判定は C 文字列の先頭文字だけを見ます。整数や真偽値として文字列全体を parse しません。CUDA/HIP の一般判定と SYCL 判定は、未設定・空文字・先頭が `0` の場合は 1 行化を要求せず、それ以外の非空文字列では要求します（`engine/src/kernels/cuda/native_mmvq.cu:1697-1702`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2228-2232`）。

CUDA/HIP の Q8_0 (`SmallTraits<Q80Block, 8>`) には加えて GPU 世代別の自動判定があります。そこでは未設定または空文字が自動判定を許し、先頭文字 `0` は自動判定を明示的に無効化します。その他の非空値は自動判定を許します（`engine/src/kernels/cuda/native_mmvq.cu:1388-1405`）。このため空文字は一般判定では OFF ですが、Q8_0 世代別自動判定は止めません。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA/HIP の通常の exact multi-column 判定、SYCL | 2 行を維持 | `1`, `true`, `2`, ` 1`, `1abc`（先頭文字が `0` 以外の非空文字列） | 空文字、`0`, `0anything` |
| CUDA/HIP の Q8_0 世代別判定 | 自動判定を許可 | `1`, `true`, `2`, `1abc`（自動判定を許可） | `0`, `0anything`（世代別自動判定を停止） |

全体文字列の妥当性、大文字小文字、数値範囲、後続文字、空白は検査されません。たとえば `false` や空白だけの値も、先頭が `0` でない非空値として扱われます。数値変換・clamp・無効値エラーはありません。

## 有効になる条件

- 呼び出しが Strata native MMVQ の複数列経路（`ncols > 1`）を通ること。1 列 kernel にはこの設定の判定がありません（`engine/src/kernels/cuda/native_mmvq.cu:2581-2605`）。
- `g_multi_exact` が true であること。false の場合は環境変数を読む前に 2 行 kernel へ戻ります。既定値は true で、API `native_mmvq_set_multi_exact` で変更できます（`engine/src/kernels/cuda/native_mmvq.cu:1242-1246,1685-1689,3272-3273`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1351,2209-2223,3375`）。
- 型ごとに `n_in / F::DIV >= F::BPI` を満たすこと。満たさない入力では環境値が有効でも 1 行 kernel にならず、2 行 kernel に進みます（`engine/src/kernels/cuda/native_mmvq.cu:1702-1710`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2232-2256`）。
- CUDA/HIP では通常の exact multi-column kernel が選ばれていること。先行する B6 kernel、sm_70 Q8 V70 kernel、Q8_0 packed kernel、RDNA Q8_0 WMMA kernelが処理を引き受けた場合は、この設定の行数選択を通りません（`engine/src/kernels/cuda/native_mmvq.cu:1560-1569,1659-1670,1681-1704,3699-3704`）。
- CUDA/HIP の Q8_0 世代別自動判定は、Q8_0 の通常経路に限られます。sm_86 は `n_out >= 2048`、gfx12 は `n_in <= 4096 && n_out >= 4096` で自動的に 1 行を選びます。sm_120 はさらに `STRATA_Q80_ROWS1` が非空かつ先頭文字が `0` 以外である必要があります。それ以外の世代はこの自動判定では選ばれません（`engine/src/kernels/cuda/native_mmvq.cu:1366-1405`）。この自動判定は `STRATA_NO_MMVQ_ROWS2` が未設定または空文字の場合にも働きます。
- SYCL では Q8_0 世代別自動判定を持たず、この変数の一般判定と入力長条件だけで 1 行にするか決めます（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2225-2256`）。
- Strata の CUDA エンジンは、全ての可視 CUDA device が同一 compute capability の場合に architecture defaults を適用します。sm_70 では `STRATA_DEFAULTS=026` でない場合、`STRATA_NO_MMVQ_ROWS2=1` が既定値として登録されます。既に `getenv` で非 NULL として見える値があれば（空文字として見える場合も）既定登録はスキップされます。混在 compute capability の複数 GPU ではこの architecture defaults 適用全体がスキップされます（`engine/src/core/nv_defaults.cpp:136-163,222-234`、`engine/src/program/generate.cpp:4421-4449`）。

## 実行時の詳細

CUDA/HIP の一般判定と SYCL 判定は、`launch_multi_n` 内の関数ローカル `static` に初回評価結果を保存します。初回に getenv した値が以後の呼び出しでも使われ、プロセス実行中に環境を変更してもこの判定には反映されません。CUDA/HIP の Q8_0 自動判定も別の関数ローカル `static` 値を初回評価時に保存します（`engine/src/kernels/cuda/native_mmvq.cu:1394-1397,1697-1701`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2228-2231`）。

1 行化が選ばれると、CUDA/HIP は `n_out` 個の block を起動し、SYCL は `n_out` 個の work-group を作ります。TSUM が有効な場合は TSUM 版 kernel、そうでなければ通常の exact 1-row kernel を選びます。条件を満たさない場合は 2 行単位で出力を処理します（`engine/src/kernels/cuda/native_mmvq.cu:1702-1710`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2232-2278`）。この分岐が変えるのは kernel の行当たり処理単位であり、CLI 引数で行数を上書きする処理はこれらの実装にはありません。

## ログと測定値

この行数選択そのものについて、Strata の実装は有効・無効を示す専用ログを出しません。sm_70 の CUDA architecture defaults が新たに適用された場合は、起動時に `strata: sm_70 (Volta): ... speed switches on by default ...` の行へ `STRATA_NO_MMVQ_ROWS2` を含む設定名一覧を出します。既にユーザーが変数を設定していた場合や、既定値リストが空の場合は、この設定が一覧に追加されません（`engine/src/core/nv_defaults.cpp:222-255`）。

`docs/DETAILS.md` は sm_70 の既定スイッチ一覧にこの変数を記載しています。実装と一致するのは sm_70 defaults が適用される条件であり、同資料の測定値はこの環境変数単体の性能差としては引用していません（`docs/DETAILS.md:1478-1488`）。

## 根拠

- `engine/src/kernels/cuda/native_mmvq.cu:1365-1405` — CUDA/HIP の Q8_0 世代分類・自動 rows1 判定。
- `engine/src/kernels/cuda/native_mmvq.cu:1677-1710` — CUDA/HIP の multi-column dispatch、値判定、1 行/2 行 kernel。
- `engine/src/kernels/cuda/native_mmvq.cu:2581-2605,3699-3704` — native small MMVQ と Q8_0 の呼び出し経路・早期分岐。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2202-2278` — SYCL の multi-column dispatch と行数判定。
- `engine/src/core/nv_defaults.cpp:136-163,222-255` — sm_70 既定値、利用者設定の優先、起動ログ。
- `engine/src/program/generate.cpp:4421-4449` — CUDA エンジンでの architecture defaults 適用条件と時期。
- `docs/DETAILS.md:1478-1488` — sm_70 既定スイッチの説明。
