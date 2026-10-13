# `STRATA_VERIFY_DEVICE_PLAN`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Speculative verification の各層で、GPU がルーティング済み expert の配置計画を作れるようにします。通常は GPU が router の結果と residency table を doorbell 経由でホストへ知らせ、ホスト側の expert pool が plan を作ります。有効にすると、Verifier が `resident_plan` を起動し、対象 group の expert が GPU から直接使える場合は device plan を使ってホストの plan 応答を省きます。CUDA/HIP と SYCL の実装があります。

キャッシュ全体の expert が対象 stage の VRAM に常駐している場合は `all_resident_` の別経路が使われ、この変数による device-plan 分岐は無効です。この変数が有効でも、各 group の expert が必要な device/host mirror に存在しない場合は通常の host doorbell 経路に戻ります。

## 値と判定

Verifier の初期化時に `std::getenv()` で読み、`std::atoi(v) != 0` を有効条件にします。文字列全体の数値 parse ではなく、`atoi` が変換する先頭の数値部分を使います。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、先頭が数値として解釈できない文字列、`0`、`0suffix` | 無効（`atoi` が 0） |
| `1`、`-1`、`2`、`1suffix`、先頭の空白後の非ゼロ整数 | 有効（`atoi` の結果が非ゼロ） |

大文字小文字による判定はありません。読み取りは Verifier の `init()` ごとに行われます。また SYCL の expert-source 経路は初回呼び出し時に同じ値を `static const bool` に保存します。実行中に環境を変更すると、読み取り箇所によって反映時期が異なるため、起動前に設定する必要があります。

## 有効になる条件

- Verifier が profile で埋めた VRAM expert tier を持つ必要があります。`init()` は `hits.d_res`、`hits.cache_base`、正の `hits.blob` がない場合に失敗します。
- `all_resident_` が false で、`set_always_publish(true)` が設定されていない場合にだけ `device_plan_` が true になります。全 expert 常駐の判定は、既定では host residency table の `[lb_, le_)` の全層・全 expert を調べます。`STRATA_VERIFY_ALL_RESIDENT=0` ならその検査を無効化します。
- `device_plan_` に必要な `skip_` バッファや slot offset の device copy を確保できない場合、初期化コードは `device_plan_` を false に戻します（CUDA では `cudaGetLastError()` を消費し、SYCL では allocation/copy の成否を使います）。この fallback 専用ログはありません。
- `STRATA_ADAPT_OVERLAP` の adaptive overlap gate は、device-plan layers が有効だと `set_adapt_gate()` に拒否されます。`--pipeline-windows` に伴う `set_always_publish(true)` 経路では device plan が無効になります。
- SYCL の `resident_plan` は VRAM にない expert について host mirror table も確認します。mirror pointer があれば device plan を作れます。CUDA/HIP 側の kernel は residency slot が負の expert があれば group plan を断念して `skip=0` にし、host 経路へ戻します。

## 実行時の詳細

CUDA/HIP と SYCL の Verifier は `init()` 中に設定値を読み、`device_plan_ = !all_resident_ && !always_publish_ && (v != nullptr && std::atoi(v) != 0)` とします。device plan が有効なら `skip_` を確保し、`resident_plan()` に layer の routed expert IDs、device residency table、cache base、slot offsets を渡します。SYCL はさらに対応する layer の mirror table を参照します。kernel は ID を plan にまとめ、GPU 上の expert pointer と出力先を設定します。

group 全体の plan が作れた場合、Verifier は host から plan を受け取る doorbell wait/copy を `skip_` の値に応じて省きます。CUDA/HIP kernel は VRAM residency が欠けた group で `skip=0` を返し、その group は通常どおり host plan と CPU share を待ちます。SYCL kernel は VRAM または host mirror にない expert があれば同様に fallback します。SYCL の `STRATA_VERIFY_NO_HOST` を同時に有効にすると、Verifier は層ごとの host handoff をせず window 全体の完了を待つ lean 経路を使えますが、その経路は `device_plan_`、`STRATA_VERIFY_LEAN`、他の verifier 条件にも依存します。

SYCL の `sycl/serve/strata-sycl.sh` はこの変数を既定値 `1` として engine container に渡します。親環境や server config の `env` による同名設定はその既定を上書きします。スクリプトは値が `0` または空文字の変数を container に渡さないため、その場合 engine 側では unset となり、この機能は無効です。通常の engine では未設定が無効です。

この値専用の有効・無効ログは見当たりません。Verifier の共通 stderr 行 `strata verify: window up to ...` は出ますが、`all_resident_` の場合だけ `(100% VRAM resident: zero-doorbell graph)` が付きます。SYCL で `STRATA_VERIFY_NO_HOST` と `STRATA_VERIFY_DEBUG` も有効な場合は、window 後に `verify dbg: ... skip[]=` を stderr に出します。

## 根拠

- `src/core/verify.cpp:759-810`, `sycl/src/core/verify.cpp:701-780`: 全常駐判定、環境値 parse、条件、buffer allocation と失敗時の無効化、初期化ログ。
- `src/core/verify.cpp:1477-1486`, `sycl/src/core/verify.cpp:1335-1344`: layer の plan 分岐と `resident_plan` 呼び出し。
- `src/kernels/cuda/verify_kernels.cu:1065-1093`: CUDA/HIP kernel が residency miss で group を fallback させる判定。
- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2081-2135`: SYCL kernel の VRAM/host mirror 判定と fallback。
- `src/core/verify.cpp:1595-1639`, `sycl/src/core/verify.cpp:1453-1493`: skip flag、通常の host plan・CPU share との分岐。
- `include/strata/core/verify.hpp:249-259`: `set_always_publish()` と adaptive gate が device plan に与える条件。
- `sycl/src/core/verify.cpp:803-809,2178-2185`: SYCL の lean 条件と `STRATA_VERIFY_NO_HOST` の適用範囲。
- `sycl/src/core/expert_source.cpp:2706-2710`: SYCL expert-source 側の初回読み取りキャッシュ。
- `sycl/serve/strata-sycl.sh:22-40`: SYCL server wrapper の既定値、上書き、0/空文字の除外。
- `docs/INTEL.md:232-249`: SYCL での起動例と、GPU が各層を計画する機能としての説明。性能値は本書では記載していません。
