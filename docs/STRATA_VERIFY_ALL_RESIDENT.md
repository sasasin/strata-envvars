# `STRATA_VERIFY_ALL_RESIDENT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

speculative verification の初期化時に、対象 layer の全 expert が VRAM cache に常駐しているかを調べ、条件を満たす場合に all-resident（zero-doorbell）graph を使うか制御します。既定では検査を行います。`0` 相当の値を指定すると検査を無効にし、Verifier はこの経路を選びません。

この値は「全 expert を VRAM に載せる」設定ではありません。常駐状況の検査を許可するだけで、実際に全 expert が常駐している場合に限り all-resident 経路になります。

## 値と判定

CUDA と SYCL の実装はいずれも `std::atoi()` の結果が 0 でないかを判定します。文字列全体の妥当性検査はありません。

| 値 | 検査 | 結果 |
|---|---|---|
| 未設定 | 行う（既定） | 対象範囲の全 expert が常駐していれば `all_resident_` を有効化 |
| `0`、空文字、数値に変換できない文字列 | 行わない | all-resident graph を無効化 |
| `1`、`-1` など、`atoi()` が 0 以外を返す文字列 | 行う | 常駐状況に応じて有効化 |

`atoi()` は先頭の空白と符号を許し、数字列の後ろに文字があってもその部分を無視します（例: `1abc` は有効、`0abc` は無効）。大文字小文字は関係ありません。`atoi()` が 0 を返す不正値はエラーや警告を出さず、検査を無効にします。

## 有効になる条件

- `Verifier::init()` が呼ばれる speculative verification または batch verification の経路であること。通常の生成経路では `--spec` または batch 設定による verifier 初期化が該当します。
- expert cache が有効で、`VerifyHits` に host residency table (`h_res`)、device residency table (`d_res`)、VRAM cache base (`cache_base`) がそろっていること。`h_res` が null の場合は全常駐検査を行いません。
- 変数が未設定か、`atoi()` が 0 以外を返すこと。
- Verifier の担当範囲 `[lb_, le_)` にある全 layer・全 expert の host residency table 値が 0 以上であること。

いずれかの expert が非常駐（値が負）なら `all_resident_` は有効にならず、通常の doorbell graph 側になります。追加の device buffer 確保または residency table 転送に失敗した場合も、初期化中に `all_resident_` は解除されます。別設定の `STRATA_VERIFY_DEVICE_PLAN` は expert の全常駐を前提としない device planning の設定であり、この変数で all-resident が有効な場合はそちらを選びません。

## 実行時の詳細

環境変数は `Verifier::init()` 中に各 Verifier インスタンスごとに読みます。static cache ではありません。同じプロセスで後から初期化される別の Verifier は、その時点の値を読みますが、初期化済みインスタンスの選択は環境を書き換えても変わりません。通常の `Verifier::run()` は各 window の前に host residency table を再確認します。prompt loan、cache shrink、swap in-flight などで対象 expert が VRAM 外に出た場合、その window は doorbell graph へ切り替わり、常駐状態に戻ると zero-doorbell graph に戻ります。

有効な状態で初期化されると stderr の初期化ログに ` (100% VRAM resident: zero-doorbell graph)` が付きます。window ごとの切り替え時には `strata verify: layers [...] have experts out of VRAM (a prompt loan, a shrink or a swap): the doorbell graph runs the windows` または `strata verify: layers [...] are 100% VRAM resident again: the zero-doorbell graph` が出ます。all-resident graph の実行中に residency table と実態が食い違った場合は、`verify: the all-resident plan met an expert that is not in VRAM (the residency table changed during the window)` で window が失敗します。

## 根拠

- `src/core/verify.cpp:540-568,759-779` — CUDA verifier の初期化、前提となる expert tier、環境変数の判定と全常駐検査。
- `sycl/src/core/verify.cpp:466-490,701-730` — SYCL verifier にも同じ判定を実装。
- `src/core/verify.cpp:781-810`、`sycl/src/core/verify.cpp:723-779` — `STRATA_VERIFY_DEVICE_PLAN` との優先関係、追加リソース確保の fallback、stderr 初期化ログ。
- `include/strata/core/verify.hpp:397-405` — all-resident 状態と window 単位の off 状態。
- `src/core/verify.cpp:1827-1843,2141-2173,2285-2293` — 各 window の常駐状態再確認、graph 選択、window 中の不整合エラー。
- `src/program/generate.cpp:7607-7614`、`sycl/src/program/generate.cpp:7198-7205,12115-12133` — `Verifier::init()` を呼ぶ生成経路。
- `docs/A770_SPEED_SPEC.md:279-301`、`docs/INTEL.md:236-256` — all-resident graph が目標とする挙動や関連する SYCL 経路の説明。これらの資料は `STRATA_VERIFY_ALL_RESIDENT` の値判定を説明していないため、値の規則は上記実装を根拠とした。
