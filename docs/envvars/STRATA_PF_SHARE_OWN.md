# `STRATA_PF_SHARE_OWN`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

CPU が prompt の MoE 層で一部の expert rows を処理した場合に、GPU 側の残りの experts を Strata 独自の staged fused entry または int8 kernels で処理してよいかを決める。`src/prefill/prefill.cpp` が環境値を一度取得し、`include/strata/prefill/share_own_rule.hpp` の pure helper に渡す。CPU がその層で 1 行も取らなければ常に許可され、この変数は結果を変えない。値が許可しても各経路の他の条件を満たさなければ、その経路は選ばれない（`src/prefill/prefill.cpp:429-440, 5951-5965, 5966-5990`）。

## 値と判定

helper は文字列全体を比較し、数値変換や trim、大文字小文字変換はしない。`rows_cpu == 0` は環境値の確認より先に `true`。CPU が rows を取った層では、完全一致の `"0"` が独自 kernels を禁止し、完全一致の `"1"` が許可する。それ以外は build 既定に戻る（`include/strata/prefill/share_own_rule.hpp:20-30`）。

| ビルド条件 | unset | `rows_cpu > 0` で許可 | `rows_cpu > 0` で禁止 |
|---|---|---|---|
| `STRATA_PF_OWN_ONLY`（MMQ なし） | 許可 | `"1"` | `"0"` |
| MMQ あり | 禁止 | `"1"` | `"0"` |

空文字、`"true"`、`"yes"`、`"01"`、`"1x"`、`" 1"` はすべて「明示的な on/off ではない」値で、unset と同じ build 既定になります。従って MMQ なしでは許可、MMQ ありでは禁止です。`rows_cpu == 0` ならこれらを含むどの値でも許可結果です（`include/strata/prefill/share_own_rule.hpp:21-30`）。

`STRATA_PF_OWN_ONLY` は `STRATA_PREFILL_FUSED` が定義され `STRATA_PREFILL_MMQ` が定義されない build で設定されます。CMake の対象分岐は CUDA の `STRATA_MMQ` 有無、および HIP の `STRATA_PREFILL_MMQ` と `STRATA_MMQ` の組み合わせで選びます（`src/prefill/prefill.cpp:204-206`; `CMakeLists.txt:104-112, 611-619`）。

## 有効になる条件

- この判定が使われるのは、CPU pool が利用可能で CPU share が有効な prompt chunk で、CPU が実際にその層の expert rows を取った場合（`rows_cpu > 0`）。CPU share の pool は `cpu_pool_ != nullptr`、share 有効、`!stream_all`、`!pipe_chunked`、share が block されていない場合に確保を試み、CPU 候補選別には native expert layout などの追加条件があります（`src/prefill/prefill.cpp:4391-4401, 5586-5587, 5720-5753`）。関連する `STRATA_PREFILL_CPU_SHARE` が unset / `0` なら share は 0 ですが、同変数の既定 share が armed される実行経路もあります（`src/prefill/prefill.cpp:638-670`）。
- `"1"` は独自 kernels の可否だけを許可する。staged fused 経路には `!stream_all`、native layout、サポート対象の形式、peer・WMMA・Hadamard・group scratch・weight-stationary 等を使わないこと、gather と entry が有効であることなどの条件が別途あります（`src/prefill/prefill.cpp:5951-5965`）。
- int8 経路にも native layout、peer なし、group scratch なし、tail なし、weight-stationary なし、`STRATA_PREFILL_GROUP_GATHER` が有効、非空の expert order、format・chunk 条件などが必要です（`src/prefill/prefill.cpp:5966-5990`）。
- `"0"` は上記の staged fused / int8 独自経路を、CPU が rows を取った層では禁止する。`rows_cpu == 0` の層や、他の独立条件で既に対象外の経路には作用しません（`src/prefill/prefill.cpp:5958-5960, 5982-5985`; `include/strata/prefill/share_own_rule.hpp:26-30`）。
- CLI 引数や設定ファイルによるこの環境値自体の上書き処理は見つかりません。CPU share の量を決める `STRATA_PREFILL_CPU_SHARE` とは独立しており、対象変数は share が成立した後の GPU kernel 経路だけを判定します（`src/prefill/prefill.cpp:432-439, 5735-5753`）。

## 実行時の詳細

`share_keeps_own_kernels()` の関数内 `static const char*` 初期化で、初めて helper が呼ばれた時に `std::getenv` を実行して返されたポインタを保存します。値の判定自体は helper 呼び出しごとに行いますが、環境を再取得しないため、プロセス中に環境を変更してもこの static 初期化後の再読み取りはありません（`src/prefill/prefill.cpp:432-439`）。

CPU share が rows を取ると、helper の結果が staged fused entry の `fz_staged` 判定と int8 の `i8_l` 判定に入ります。許可された経路では GPU が残りの GPU rows を処理し、CPU rows は後で `Dm` の CPU rows 領域へコピーされて共通の combine に渡されます。helper は routed rows や CPU share の選択量を変えず、CPU と GPU の出力行を合流する配置も維持します（`src/prefill/prefill.cpp:5958-5990, 7060-7076, 7095-7099`; `include/strata/prefill/share_own_rule.hpp:1-6, 25-30`）。

## ログと測定値

この環境変数専用の有効・無効ログやエラーはありません。経路が実際に使われた場合は、別途その経路の一般ログとして `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` または int8 kernels の案内が出ることがありますが、この変数が判定を許可したことを示すログではありません（`src/prefill/prefill.cpp:5477-5482, 6042-6050`）。CPU share の pinned buffer が確保できない場合は別処理が share を止めて GPU に全 expert を処理させます（`src/prefill/prefill.cpp:5588-5596, 5617-5653`）。この変数固有の終了・失敗経路や、条件付き測定値は確認できません。

## 根拠

- 環境値の唯一の実読み取り箇所、build 既定の引き渡し: `src/prefill/prefill.cpp:429-440`。
- 値の完全一致・fallback 規則: `include/strata/prefill/share_own_rule.hpp:20-30`。
- own-only build の定義と CMake backend / MMQ 分岐: `src/prefill/prefill.cpp:204-206`; `CMakeLists.txt:104-112, 611-619`。
- CPU share 条件、候補の選択、独自 kernels への接続、CPU rows の合流: `src/prefill/prefill.cpp:638-670, 4391-4401, 5586-5587, 5720-5753, 5951-5990, 7060-7076, 7095-7099`。
