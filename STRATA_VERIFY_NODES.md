# `STRATA_VERIFY_NODES`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。作業ツリーは clean。外部ライブラリの環境変数は対象外。

## 役割

GPU verifier が新しく作成した decode-window graph の構成を stderr に出す診断用フックです。graph の node 数、node 種別ごとの個数、取得できる場合は kernel 名を表示します。HIP では値が 2 以上のとき、追加で graph node の列も表示します。この変数は graph の計算内容や verifier の実行選択を変えず、capture 後の観測ログだけを追加します。

## 値と判定

| backend | unset | 設定時 |
|---|---|---|
| CUDA | 無効 | 空文字を含め、値の内容によらず有効。`0` や `false` も有効 |
| HIP | 無効 | 空文字を含め、設定されていれば node 集計を有効化。`atoi(value) >= 2` の場合は node 列も追加 |
| SYCL | 無効 | 空文字を含め、値の内容によらず有効 |

CUDA と SYCL は `getenv(...) != nullptr` だけを判定し、文字列を parse しません。HIP も同じ存在判定で集計を有効にしたうえで、追加の node 列についてのみ `atoi` の結果を使います。したがって HIP では `2`, `2tail`, ` 2` など `atoi` が 2 以上を返す値が node 列を出し、空文字、`1`, `true`, `invalid` などは集計のみです。数値変換は文字列全体の妥当性を検査しません。

## 有効になる条件

- CUDA/HIP では、window graph の capture が成功し、新しい graph が作られる経路で有効です。`capture()` は既存 graph があれば先に return するため、その window の graph が既に cache されている場合は環境変数を設定しても診断を追加しません。
- SYCL の通常 graph capture でも、新しい graph の capture が成功した後に集計を表示します。stepped verifier の segment capture では segment 数を表示します。segment 列が既に cache されていれば再 capture しません。また `STRATA_VERIFY_EAGER` が設定され、graph capture 自体を省略する経路では node 集計はありません。
- これらのコードは verifier の window graph を capture する経路に属します。verifier が初期化されない、graph capture が実行されない、または capture が失敗する場合には node listing は出ません。

## 実行時の詳細

CUDA と HIP は `src/core/verify.cpp`、SYCL は `sycl/src/core/verify.cpp` で変数を直接読みます。env 判定を static cache するコードはありません。判定は graph ごとの capture 後に行われるため、未作成の window graph については capture 時点のプロセス環境が参照されます。capture 後に環境を変更しても cache 済み graph の診断は再実行されません。

- CUDA は node を走査して種別と kernel 名（CUDA Runtime 12.3 以上で取得できた場合）を数え、個数の多い順に最大 40 種を表示します。CUDA Runtime 12.3 以上では edge 数と programmatic dependency (PDL) edge の数、および kernel-to-kernel 以外の PDL edge 数も出します。
- HIP は node 種別・kernel 名ごとの個数を最大 80 種表示します。値の `atoi` 結果が 2 以上なら、さらに最大 400 node の列を stderr に出します。列名は 110 文字までです。
- SYCL は node 種別ごとの個数を最大 40 種表示します。graph node から kernel 名を取得する処理はなく、kernel は `kernel` として集計します。stepped capture 経路では、window graph の node 集計に加えて graph segment 数も表示します。

ログの先頭は `strata verify: the %d-token window graph has %zu nodes:` です。CUDA/HIP/SYCL の node 集計はいずれも stderr に出力されます。この診断用環境変数を記載した説明は `docs/DETAILS.md` では見つかりませんでした。同資料は別の verifier 計測用 `STRATA_VERIFY_PROFILE` を説明していますが、それとは独立した node listing です。

## 根拠

- `src/core/verify.cpp:1846-1872` — CUDA/HIP window graph capture、既存 graph の早期 return。
- `src/core/verify.cpp:1873-1903` — HIP の存在判定、`atoi >= 2` による最大 400 node の列、および集計。
- `src/core/verify.cpp:1905-1960` — CUDA node 集計、Runtime 12.3 以上の kernel 名と PDL edge 集計。
- `sycl/src/core/verify.cpp:1687-1727` — SYCL stepped capture と segment 数ログ。
- `sycl/src/core/verify.cpp:1734-1796` — SYCL graph capture と node 種別集計。
- `sycl/src/core/verify.cpp:1734-1742` — cache 済み graph および `STRATA_VERIFY_EAGER` 経路。
- `docs/DETAILS.md:299-306` — verifier の別診断 `STRATA_VERIFY_PROFILE` の説明。`STRATA_VERIFY_NODES` の記載はありません。
