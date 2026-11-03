# `STRATA_RESIDENT_PLAN_COMPACT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版の resident routing plan kernel が使う work-group の thread 数を、routing entry 数に合わせて小さくします。未設定時は無効で、通常の 128 threads を使います。有効時は entry 数を 32 の倍数へ切り上げた数（最小 32）を使います。これは plan の作り方を変える設定ではなく、`resident_plan` の kernel 起動サイズを選びます。

この読み取りは `sycl/src/kernels/cuda/verify_kernels.dp.cpp` にだけあります。ファイル名に `cuda` を含みますが、これは SYCL build に含まれる migrated kernel です。Strata の通常 CUDA 実装 `src/kernels/cuda/verify_kernels.cu` にはこの環境変数の読み取りがありません。

## 値と判定

共通 helper `bm_default_on` は、空でない値なら先頭文字だけを調べ、`'0'` 以外を有効とします。この呼び出しでは `bm_default=false` を渡すため、未設定または空文字は無効です。文字列全体の parse、数値変換、大文字小文字の判定はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（helper が既定値 `false` を返す） |
| 先頭文字が `0` | 無効（例: `0`, `0anything`） |
| 空でなく、先頭文字が `0` 以外 | 有効（例: `1`, `2`, `true`, `false`, 空白で始まる文字列） |

CLI 引数による上書きや、別の環境変数との優先順位はこの読み取り箇所にはありません。`bm_default_on` の通常の Battlemage 既定値も、この呼び出しでは明示的な `false` により使われないため、環境変数を設定しなければ GPU 世代にかかわらず無効です。

## 有効になる条件

- SYCL build の resident plan 実装を実行すること。通常 CUDA の `src/kernels/cuda/verify_kernels.cu` にはこの設定は接続されていません。
- `resident_plan` が呼ばれること。SYCL verifier は all-resident (`ar_on()`) 経路、または `STRATA_VERIFY_DEVICE_PLAN` が非 0 で device plan が成立した経路でこの関数を呼びます。
- device plan 経路は all-resident 経路でなく、`always_publish_` でもないことが条件です。初期化時の device plan 用メモリ確保に失敗した場合は `device_plan_` が解除されます。

値が有効でも、これらの verifier 経路に入らなければ環境変数の判定も work-group サイズの変更も起きません。all-resident の有効化には `STRATA_VERIFY_ALL_RESIDENT` と residency table の状態が関係し、device plan には `STRATA_VERIFY_DEVICE_PLAN` が関係します。両変数の値判定はそれぞれの実装に従います。

## 実行時の詳細

`resident_plan` の最初の呼び出しで `static const bool compact` が初期化され、その値がプロセス内で後続の呼び出しにも使われます。そのため、その後に環境を変更しても再評価されません。複数の SYCL device / queue を使う場合も static 値は共有され、最初に呼ばれたときの値が使われます。

有効時の thread 数は `max(32, ceil(n_entries / 32) * 32)` です。無効時は常に `kResidentPlanMax`（128）。kernel 本体は `tid < n` の entry だけを処理し、entry の順序から expert group と plan を作ります。コンパイル時に `kVerifyMaxT * 10 <= 128` が検査され、通常の最大 entry 数が work-group 上限を超えないようにしています。

この環境変数専用のログ、警告、失敗分岐はありません。`resident_plan` は起動後 `check("resident_plan")` を呼びますが、このファイルの `check` は SYCL の例外方式に関する移行注記を残した no-op です。環境変数の値が失敗を直接起こす処理は確認できません。

## 根拠

- 候補名の完全一致検索では、実装読み取りが `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2467` の 1 箇所、説明表が `docs/INTEL.md:541` の 1 箇所でした。`setup.py`、`serve`、その他の Strata ソースでの同名読み取りはありません。
- 先頭文字判定と Battlemage fallback: `sycl/include/strata/sycl_queue.hpp:159-166`。呼び出し時に `bm_default=false` を指定: `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2467`。
- thread 数の選択、SYCL kernel 起動、起動後の `check`: `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2460-2485`。`check` の no-op 実装: 同ファイル `:40-52`。
- 128 thread 上限と entry 数の compile-time 条件: `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2143-2150`。
- 呼び出し条件となる all-resident / device plan の設定と allocation fallback: `sycl/src/core/verify.cpp:740-765,784-807`。`resident_plan` の呼び出し: 同ファイル `:1421-1430`。
- SYCL all-resident と device plan の経路説明、および device-plan 時の layer 処理: `sycl/src/core/verify.cpp:2324-2329,1549-1577`。
- `docs/INTEL.md:541,547-549` はこの設定を Battlemage 既定 OFF と分類し、測定構成では neutral またはやや遅い設定群に含めています。コード上の既定 OFF と一致します。独立した性能値は本調査では追加していません。
