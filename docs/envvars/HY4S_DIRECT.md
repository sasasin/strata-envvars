# `HY4S_DIRECT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

`HY4S_DIRECT` は、Hy4-Flash SYCL 系の旧式 CPU routed-expert 実装 `hy4s::CpuExperts` が、page cache にない expert body を読み込む際に `O_DIRECT` を使うかを指定する。設定されていない場合は Section 4 の大きさと利用可能 RAM から決まる自動値を使い、設定されている場合は自動値を上書きする。`O_DIRECT` 読み込みが実際に起きるのは `copy_body` でキャッシュミス等の条件を満たした場合だけである（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:333-346,563-620`）。

この `CpuExperts` は `sy_gpuexp_test` が使う legacy 経路である。通常の SYCL 推論初期化と serve は `hy4::CpuExperts` を使い、GPU experts も unified 初期化を選ぶため、この変数の読み取り箇所を通らない（`engine/src/hy4flash/sycl/sy_gpuexp_test.cpp:61-78`、`engine/src/hy4flash/sycl/sy_gpuexp.h:38-43`、`engine/src/hy4flash/sycl/sy_main.cpp:280-304`、`engine/src/hy4flash/sycl/sy_serve.h:259-283`、`engine/src/hy4flash/sycl/sy_gpuexp.cpp:672-705`）。

## 値と判定

`CpuExperts::open` で `std::getenv` の結果を確認し、設定されていれば `e[0] == '1'` だけで判定する。文字列の全体 parse はなく、値の後続文字、大文字小文字、数値としての妥当性は検査しない。明示的な空文字は「設定あり」だが先頭文字が `'1'` でないため無効（false）になる。`HY4S_WARM_GB` は自動値の計算に関わるが、`HY4S_DIRECT` が設定されるとこの自動値より優先される（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:333-346,480-493`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `hy4s::CpuExperts::open` を使う実行経路 | `bypass_ = f < 0.85`。`f` は `min(1, ram_budget_bytes()/Section 4 bytes)` | 先頭文字が `1`。例: `1`、`10`、`1anything` | 空文字、`0`、`true`、` 1`。先頭文字が `1` 以外なら false |

先頭文字判定のため、`01` は false、`1 ` は true となる。設定値に境界数値・負値としての扱いはなく、いずれも先頭文字だけで決まる（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:342-346`）。

## 有効になる条件

- `hy4s::CpuExperts::open` が呼ばれる必要がある。現行ソースでは実行例として `sy_gpuexp_test` がこのクラスを開く。通常の `sy_main` と server は unified `hy4::CpuExperts` の初期化経路を使う（`engine/src/hy4flash/sycl/sy_gpuexp_test.cpp:68-78`、`engine/src/hy4flash/sycl/sy_main.cpp:280-304`、`engine/src/hy4flash/sycl/sy_serve.h:259-283`）。
- 実際の direct read には、synthetic pool でないこと、`O_DIRECT` 用 fd `fdd` の取得成功、expert body の offset・byte 数・宛先が 4096 byte 境界に揃うこと、および body が page cache に常駐していないことが必要。常駐していれば値が有効でも `memcpy` になる（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:352-369,565-580`）。
- `HY4S_DIRECT=1` は RAM 自動判定に関係なく `bypass_` を true にするが、上記の I/O 条件が満たされなければ読み込み方式は変わらない。`HY4S_DIRECT=0` や空文字は自動判定を false に上書きするため、RAM 自動判定が direct を選ぶケースでも無効化する（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:342-346`）。
- `HY4S_WARM_GB` は `ram_budget_bytes()` の RAM 予算に影響し、未設定時の `f < 0.85` 判定を間接的に変えうる。`HY4S_DIRECT` が設定されている場合はその判定結果を上書きする（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:342-346,480-493`）。

## 実行時の詳細

設定はファイルを開く `CpuExperts::open` の中で一度評価され、結果をインスタンスの `bypass_` に保存する。`copy_body` は各 expert body のコピー時にその保存値を参照するため、同じインスタンスを開いた後の環境変更は反映されない。CLI 引数による上書き経路はこの関数の引数にはない（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:333-346`、`engine/src/hy4flash/sycl/hy4s_cpuexp.h:52-67`）。

`copy_body` は、条件を満たす未常駐 body について `bypass_` が true なら page-aligned bounce buffer に `pread` し、全 byte を読み切れた場合に宛先へコピーして direct 読み込み byte 数を加算する。direct fd が使えない、bounce buffer を確保できない、または direct read が全量に達しない場合は mapped body から `memcpy` する。`bypass_` が false の cache miss は通常 fd から buffered `pread` し、全量取得できれば miss byte 数を加算する。いずれも resident body や条件不成立時は mapped body から `memcpy` し cached byte 数を加算する（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:565-624`）。

`open` では direct fd の取得失敗だけでは初期化エラーにせず、`fdd < 0` のため後の direct 読み込み条件を外して `memcpy` に進む。通常 fd が開けない場合は `open failed`、Section 4 が page aligned でない場合は `Section 4 not page aligned`、mapping に失敗した場合は `mmap failed: <strerror>` が返る（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:347-368`）。

## ログと測定値

`HY4S_DIRECT` の値や選択結果を直接表示するログはない。warm 処理を呼んだ場合、同クラスは `[cpuexp] warm: read ...` を stderr に出すが、これは warm した byte 数・時間の表示であり、この変数で direct read が成功したことを示すログではない（`engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:496-552`）。direct / buffered / cached 経路の byte 数は `direct_read_bytes()`、`miss_read_bytes()`、`cached_read_bytes()` で取得できる（同 `:622-624`）。

## 根拠

- `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:333-346` — RAM 由来の既定値と `HY4S_DIRECT` の取得・判定。
- `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:352-369` — expert directory・alignment 検査、通常 fd / direct fd / mapping の初期化と失敗経路。
- `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:480-493` — RAM 予算と `HY4S_WARM_GB`。
- `engine/src/hy4flash/sycl/hy4s_cpuexp.cpp:563-624` — body copy の cache 判定、direct / buffered fallback と counters。
- `engine/src/hy4flash/sycl/sy_gpuexp_test.cpp:61-78`、`engine/src/hy4flash/sycl/sy_gpuexp.h:38-43`、`engine/src/hy4flash/sycl/sy_main.cpp:280-304`、`engine/src/hy4flash/sycl/sy_serve.h:259-283`、`engine/src/hy4flash/sycl/sy_gpuexp.cpp:672-705` — legacy test entry point と通常の unified 経路の区別。
