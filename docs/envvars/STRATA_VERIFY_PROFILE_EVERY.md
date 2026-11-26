# `STRATA_VERIFY_PROFILE_EVERY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL verifier の GPU stage profiling が有効なとき、集計した window 数が指定数に達した段階で stderr に集計行を出す間隔を指定する診断用変数。計測値や verifier の計算・出力 token は変えず、プロファイル集計の表示タイミングだけを制御する。読み取り箇所は `engine/sycl/src/core/verify.cpp` の `Verifier::collect_profile()` と `Verifier::run()` 内の2箇所で、CUDA/HIP 実装にはこの名前の読み取りがない（`engine/sycl/src/core/verify.cpp:2337-2346, 2919-2935`）。

この機能が使われるには `STRATA_VERIFY_PROFILE` が設定されている必要がある。SYCL verifier 初期化時に `getenv(...) != nullptr` で有効化し、プロファイル用 GPU メモリの確保に失敗すると `prof_on_` を無効にする。したがって `STRATA_VERIFY_PROFILE` の空文字も設定済みとして扱われるが、この変数だけを設定してもプロファイルは始まらない（`engine/sycl/src/core/verify.cpp:816-829`）。

## 値と判定

両読み取り箇所とも `std::atoll` で `long long` に変換する。未設定なら `0`、変換後が `0` 以下なら interval 判定は通らず、この変数による定期ログは出ない。正数 `N` では集計 window 数が `N` 以上になったときに出力する。文字列全体の妥当性検査や後続文字の検査はなく、`atoll` の数値接頭部変換に従う。たとえば `32` と `32tail` はどちらも 32、`0`、`-1`、空文字、`true`、`tail32` は変換結果が正数にならず定期ログを有効にしない。先頭空白の後の符号・数字も変換対象になる。大きさの上限や範囲 clamp はコードにない（`engine/sycl/src/core/verify.cpp:2337-2345, 2926-2934`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL verifier の interval 集計 | `0` として扱い、interval ログなし | `1`, `32`, `32tail` | 空文字, `0`, `-1`, `true`, `tail32` |

2箇所の `static` は関数ごとに別の値を保持する。それぞれ `collect_profile()` または通常 `run()` の該当分岐が初めて評価された時に読み取り、その後の環境変更は反映されない（同上）。

## 有効になる条件

- SYCL backend の verifier 経路であること。この名前の実コード参照は SYCL ソースに限られ、SYCL CMake はエンジンを Linux x86_64 向けとして構成している（`engine/sycl/src/core/verify.cpp:2339, 2928`; `engine/sycl/CMakeLists.txt:255`）。
- `STRATA_VERIFY_PROFILE` が verifier 初期化時に設定済みで、プロファイル用 `sycl::malloc_device` が成功すること。未設定または確保失敗なら `prof_on_` が false となり、interval 判定箇所に到達しない（`engine/sycl/src/core/verify.cpp:816-829, 2919`）。
- `STRATA_VERIFY_PROFILE_EVERY` の `atoll` 結果が正数であること。未設定・空文字・0 以下・数字で始まらない値は間隔指定として機能しない（`engine/sycl/src/core/verify.cpp:2338-2343, 2927-2932`）。
- 通常の `run()` では `G == 1` のときだけこの変数の分岐を使う。`STRATA_VERIFY_EAGER` が設定されている通常 window 経路はこの間隔分岐を通らず、window ごとに `verify stages T=...` を出す。`collect_profile()` 内の `prof_S_ > 0` の batch-window 判定は別分岐であり、interval が正数なら batch 経路で集計ログを出す（`engine/sycl/src/core/verify.cpp:2337-2346, 2919-2935`）。
- CLI 引数やサーバー設定からこの値を設定・上書きする Strata 所有コードは見つからなかった。`STRATA_VERIFY_PROFILE` と、通常 `run()` の表示方式を変える `STRATA_VERIFY_EAGER` が関係する（同上）。

## 実行時の詳細

`Verifier::collect_profile()` は GPU stamp を host 側へコピーし（`STRATA_VERIFY_EAGER` 未設定時）、`accumulate_profile()` で stage ごとの累積値と window 数を更新する。`prof_S_ > 0` の batch window では interval 到達時に `verify stages batch window of %d rows (ms/window over %lld, GPU clock):` を stderr に出す（`engine/sycl/src/core/verify.cpp:2327-2346, 2350-2382`）。

通常 `Verifier::run()` の `prof_on_ && G == 1` 経路も集計後に interval を判定し、到達時に `verify stages T=%d (ms/window over %lld, GPU clock):` を stderr に出す（`engine/sycl/src/core/verify.cpp:2918-2935`）。出力時に `profile_report()` が平均値の文字列を作り、累積値と window 数をゼロに戻すため、正数 interval では出力後に次の集計が始まる（`engine/sycl/src/core/verify.cpp:2006-2029`）。

この環境変数を読むのは初回の該当関数実行時で、各関数の `static` に値を保持する。環境変数をプロセス稼働中に変更しても、その関数の interval には反映されない。既定値 `0` のままならこれらの interval ログは出ず、条件判定のために累積値がリセットされない。`STRATA_VERIFY_EAGER` が設定されている通常 `run()` の per-window ログは別経路なので、この interval の値では抑制されない（同上）。

## ログと測定値

該当 interval の到達時のみ stderr に、batch 経路では `verify stages batch window of ...`、通常 window 経路では `verify stages T=...` が出る。出力行には stage 別の `ms/window` と集計 window 数が含まれ、出力後に集計がリセットされる（`engine/sycl/src/core/verify.cpp:2342-2345, 2931-2934, 2006-2029`）。この環境変数自体について `docs/DETAILS.md` に設定方法や測定値の記載はない。同資料は `STRATA_VERIFY_PROFILE=1` による GPU profiling を紹介しているが、この変数の interval の説明ではない（`docs/DETAILS.md:364-366`）。

## 根拠

- `engine/sycl/src/core/verify.cpp:816-829` — `STRATA_VERIFY_PROFILE` による計測有効化と確保失敗時の無効化。
- `engine/sycl/src/core/verify.cpp:2327-2348, 2350-2382` — batch 集計時の読み取り、出力条件、累積。
- `engine/sycl/src/core/verify.cpp:2006-2029, 2918-2935` — 通常 window 経路の条件、ログ、出力後のリセット。
- `engine/sycl/CMakeLists.txt:255` — SYCL engine の対象 OS/architecture。
- `docs/DETAILS.md:364-366` — `STRATA_VERIFY_PROFILE` に関する説明との照合。
