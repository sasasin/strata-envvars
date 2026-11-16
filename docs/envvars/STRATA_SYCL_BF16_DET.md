# `STRATA_SYCL_BF16_DET`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL エンジンの BF16 入力・FP32 出力 GEMM で、出力行数 `N` が小さい形状に Strata 内蔵の固定順序カーネルを使うかを選びます。未設定時もこの経路は有効です。値が非ゼロで、形状・アラインメント条件を満たすと oneMKL GEMM を呼ばず `strata_bf16_det::gemm` を起動します。`0` はこの選択を止め、後続の標準経路に進ませます（`sycl/src/prefill/gemm.dp.cpp:692-704,805-845,888-900`）。

対象は `sycl/CMakeLists.txt` に登録された SYCL エンジンの GEMM 実装です（`sycl/CMakeLists.txt:30-44`）。呼び出し元には SYCL プリフィルの BF16 投影処理があります（例: `sycl/src/prefill/prefill.cpp:2331-2336,3161-3171,3673-3682`）。CUDA/HIP 側の挙動をこの設定が制御する根拠はありません。

## 値と判定

`Gemm::bf16` の最初の実行時に `std::getenv` で読み、関数内 `static const int` に保存します。未設定または空文字なら `1`、それ以外は `std::atoi` の戻り値です。文字列全体の妥当性確認やエラー報告はありません（`sycl/src/prefill/gemm.dp.cpp:805-810,835-845`）。

| 値の例 | `det_mode` | 意味 |
|---|---:|---|
| 未設定、空文字 | 1 | 固定順序経路を有効にする。`N <= 64` が上限 |
| `0`、`0anything`、`false`、`true`、`abc` | 0 | 固定順序経路を選ばない。後続経路へ進む |
| `1`、` 1tail`、`-1`、`3` | それぞれ `atoi` の整数値 | 変換結果が非ゼロなら有効。ただし `2` 以外は `N <= 64` が上限 |
| `2`、`2tail` | 2 | `N <= 1 << 30` まで上限を広げる |

`atoi` は数値の先頭部分を変換するため、たとえば `2tail` は `2`、`0anything` は `0` になります。数値の後ろに文字があるかどうかの検査、大小文字の判定、明示的な範囲 clamp はありません。空白や符号などの細部も `atoi` の変換規則に従います。整数として解釈できない先頭は `0` になります（`sycl/src/prefill/gemm.dp.cpp:838-840`）。

## 有効になる条件

`det_mode` が非ゼロでも、次の全条件を満たす呼び出しだけが固定順序経路に入ります（`sycl/src/prefill/gemm.dp.cpp:807-810,839-844`）。

- `T > 0` かつ `N > 0`。満たさない場合 `Gemm::bf16` は先に戻ります。
- `K` が偶数である。
- 実際に使う入力 stride `xs` が偶数である。`ldx <= K` は先に `ldx = 0` に正規化され、`xs` はその場合 `K` です。
- `N <= 64`。ただし `det_mode == 2` のときは `N <= 1 << 30`。
- `X` と `W` のアドレスがそれぞれ 4 バイト境界に揃っている。

条件に合わない場合は、この変数による経路を使わず標準経路へ進みます。SYCL エンジンでは通常 `staged_gemm` が対象バッファを必要に応じて stage し、そうでなければ oneMKL の BF16 GEMM を呼びます（`sycl/src/prefill/gemm.dp.cpp:765-799,888-900`）。`STRATA_SYCL_GEMM_NO_STAGE` / `STRATA_SYCL_GEMM_STAGE` はこの後段の staging 判定に関係しますが、固定順序経路の条件には含まれません（同 `:768-779`）。

サーバー起動スクリプト `sycl/serve/strata-sycl.sh` は、ホスト環境の `STRATA_SYCL_*` を同スクリプト自身の設定として除外し、一般の `STRATA_*` 転送対象にも含めません。そのため、ホスト側でこの変数を設定して同スクリプト経由で起動しても、コンテナ内のエンジンには渡りません。直接エンジンを起動する場合は、そのプロセス環境の値が使われます（`sycl/serve/strata-sycl.sh:31-42,46-52`）。CLI 引数や設定ファイルによる上書きは、この読み取り箇所にはありません。

## 実行時の詳細

有効条件を満たすと `strata_bf16_det::gemm` が `T * ceil(N/4)` 個の 16 lane subgroup 単位で計算します。各 lane が `K/2` 個の BF16 ペアを順に処理し、各出力について FP32 fused multiply-add を行い、最後に subgroup 内で和を取り、`beta == 0` なら結果を書き込み、それ以外なら `beta * Y + sum` を書きます。その後 `Gemm::bf16` は return し、staging / oneMKL の経路を呼びません（`sycl/src/prefill/gemm.dp.cpp:699-743,837-844`）。

設定値は `Gemm::bf16` の初回呼び出しで一度だけ static に保存され、後からプロセス環境を変更しても同プロセスでは再評価されません（`sycl/src/prefill/gemm.dp.cpp:838`）。変数を子プロセスへ転送する処理は `Gemm::bf16` にはありません。前述の SYCL サーバー wrapper は当該名前をコンテナへ転送しません（`sycl/serve/strata-sycl.sh:33-42`）。

固定順序経路は BF16 積和の累積順序と実装を変えます。生成 token や選択結果が oneMKL 経路と必ず一致する、という保証はこのコードからは導けません。`0` または条件不成立時の fallback は、staging 判定の後に oneMKL BF16 GEMM を実行するコード経路です（`sycl/src/prefill/gemm.dp.cpp:888-900`）。

## ログと測定値

この環境変数の読み取りや固定順序経路の選択を示す専用ログはありません。固定順序経路を選べない理由も出力しません。fallback の staging バッファ確保に失敗した場合は `strata: WARNING: a GEMM operand lies past 4 GiB ...` を stderr に出して直接 GEMM に進みます（`sycl/src/prefill/gemm.dp.cpp:779-785`）。最終 oneMKL GEMM のエラーは `ck` 経由で `prefill gemm: cublasGemmEx: cuBLAS status %d` を stderr に出し、終了コード 1 で終了します（同 `:88-93,892-900`）。

ソースコメントには、Arc A750 の細い形状（`M=48,T=86,K=2560`、`M=4,T=86,K=10240`）で oneMKL の結果が起動ごとに異なったという記録と、試した形状で固定順序経路が単体計測で oneMKL より 3〜36 倍速かったという記載があります。コメントには計測環境・方法・回数の詳細がないため、これはソースに残る測定メモであり、一般的な性能保証ではありません（`sycl/src/prefill/gemm.dp.cpp:693-703`）。

## 根拠

- 候補の実読み取りと値判定、経路分岐: `sycl/src/prefill/gemm.dp.cpp:805-845`
- 固定順序 BF16 GEMM の計算と書き込み: `sycl/src/prefill/gemm.dp.cpp:699-743`
- fallback の staging と oneMKL 呼び出し: `sycl/src/prefill/gemm.dp.cpp:765-799,888-900`
- SYCL build の対象ファイル: `sycl/CMakeLists.txt:30-44`
- サーバー wrapper の環境変数転送: `sycl/serve/strata-sycl.sh:31-52`
