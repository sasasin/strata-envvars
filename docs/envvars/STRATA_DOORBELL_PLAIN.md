# `STRATA_DOORBELL_PLAIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

SYCL エンジンの doorbell が host-mapped payload（activation、expert ID、routing weight）を書き込むとき、通常の store を使うか、uncached write hint を使うかを選ぶ。値は host 側の launcher で決まり、doorbell publish kernel に渡される。リングの flag／sequence の store 方法はこの変数では切り替わらない。実装は `strata::doorbell_plain_payload()` と `strata::sys_store_mapped(bool, ...)` にある（`engine/sycl/include/strata/sycl_doorbell.hpp:101-113`、`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:745-806`）。

## 値と判定

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `doorbell_plain_payload()` の初回評価 | `intel_gpu_driver() == "i915"` の場合だけ plain store、それ以外は uncached write hint | 値の先頭文字が `1`（例: `1`, `10`, `1anything`） | 空文字、`0`、`true`、` 1` など、先頭文字が `1` 以外 |

`getenv` の戻り値が null かを先に判定し、設定されていれば文字列全体を parse せず `e[0] == '1'` だけを見る。したがって空文字は設定済みの override として `false` になり、i915 の自動選択にも戻らない。大文字小文字、空白、数値としての妥当性は検査しない（`engine/sycl/include/strata/sycl_doorbell.hpp:107-112`）。

この override は自動判定を置き換える。unset 時の driver 名は `intel_gpu_driver()` が `/sys/class/drm` の Intel vendor device の driver symlink から一度取得し、該当情報がなければ空文字を返す（`engine/sycl/include/strata/sycl_queue.hpp:95-117`）。

## 有効になる条件

- 対象コードは分離された SYCL エンジン（`STRATA_ENABLE_SYCL`）にあるため、CUDA / HIP / Metal の通常経路には適用されない（`engine/CMakeLists.txt:23-31`）。
- doorbell payload を publish する SYCL 経路で使われる。single-token の layer publish と verifier の publish が該当する（`engine/sycl/src/core/layer.cpp:418-425`、`engine/sycl/src/core/verify.cpp:1612-1636`）。doorbell がない場合や verifier の all-resident / lean 経路で publish 自体が呼ばれない場合は効果がない（同 `verify.cpp:1633-1636`）。
- verifier の stepped capture 中は別の host-side flag も OR される。`STRATA_VERIFY_STEPPED` により `capture_segments()` を使い、`window_host_uncached()` が false の場合、capture 中に `g_plain_payload` が true となる。その場合 `STRATA_DOORBELL_PLAIN=0` でも plain store が選ばれる。`STRATA_VERIFY_HOST_UNCACHED` は stepped 時の `window_host_uncached()` を true にできる（`engine/sycl/src/core/verify.cpp:309-317, 2051-2057, 2098-2102`、`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:642-645, 749-806`）。
- `STRATA_DOORBELL_PLAIN=1` は driver や stepped 条件にかかわらず plain store を選ぶ。コードコメントは i915 では通常 store が使われ、xe では uncached hint が必要としている（`engine/sycl/include/strata/sycl_doorbell.hpp:101-105`）。

## 実行時の詳細

`doorbell_plain_payload()` 内の function-local `static const bool` が最初に呼ばれた時に環境変数と driver fallback を評価し、そのプロセス内で cache する。後から環境を変更してもこの選択は変わらない。各 publish launcher はその結果と `g_plain_payload` を OR し、値を kernel 引数に渡す（`engine/sycl/include/strata/sycl_doorbell.hpp:107-113`、`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:745-806`）。

kernel 内では `plain=true` の payload 要素を `*p = v` で書き、false なら `sys_store_mapped(p, v)` に委譲する。後者は通常、uncached write hint を使い、`STRATA_DOORBELL_ATOMIC_STORE` が定義された build では system-scope atomic store を使う。したがって本変数が選択するのは payload store の経路であり、build macro が無効側の実装を変える（`engine/sycl/include/strata/sycl_doorbell.hpp:67-99, 104-105`）。publish kernel は同じ payload の checksum を作ってリングを commit する（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:647-674, 676-719`）。

値による CLI 引数や他の設定ファイルとの優先順位はない。直接の環境変数 override が driver による既定判定を上書きし、stepped capture の一時 flag がその結果と OR される。

## ログと測定値

この環境変数専用のログや無効値警告はない。payload が publish されたが検証で完全な payload と認められない場合、通常 verifier 経路では `STRATA_DOORBELL_CHECK=1` の checksum 待ちが timeout すると `verify: layer <番号> rang but its payload never arrived whole` を返す（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:839-852`、`engine/sycl/src/core/verify.cpp:2693-2699`）。この検査自体は `STRATA_DOORBELL_CHECK` が設定されない限り即座に成功扱いとなるため、上記の失敗経路は常時有効ではない。

## 根拠

- `engine/sycl/include/strata/sycl_doorbell.hpp:101-113` — plain/uncached 選択と環境変数の読み取り。
- `engine/sycl/include/strata/sycl_queue.hpp:95-117` — driver の取得方法と未検出時の値。
- `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:642-645, 745-806` — 一時 flag、publish launcher、kernel 引数への受け渡し。
- `engine/sycl/src/core/verify.cpp:309-317, 1612-1636, 2051-2057, 2098-2102, 2693-2699` — verifier の publish 経路、stepped capture、payload 検査結果。
