# `STRATA_VERIFY_EARLY_PLE_FLAG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA/HIP verify window の all-resident graph が待つ PLE flag を、graph launch の前に host が立てるタイミングを選ぶ。mode 0 は従来どおり launch 後、mode 1 は毎回 launch 前、mode 2 は各 graph の初回 launch 前に flag を立てる。`engine/src/core/verify.cpp` の `early_ple_flag_mode()` と `Verifier::run()` が実装箇所である（`engine/src/core/verify.cpp:427-445, 3865-3877, 3979-3991`）。

## 値と判定

`std::getenv` の戻り値が null なら backend の既定値を使う。設定されていれば `std::atoi` の結果を 0 未満なら 0、2 より大きければ 2 に clamp する。数値全体の妥当性や末尾文字は検証しない。`atoi` は先頭の空白と符号を受け取り、数字列の後ろは無視する。空文字、数字で始まらない文字列、`true` / `false` は変換結果 0 になる。整数範囲外の文字列に対する `atoi` の結果はこのコードで保証されない（`engine/src/core/verify.cpp:435-443`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---:|---|---|
| `STRATA_USE_HIP` 定義 | 2 | `1` → 1、`2` 以上 → 2（例: `3`, `2tail`） | 0 以下 → 0（例: `0`, `-1`）、数値に変換できない値や空文字 → 0 |
| `STRATA_USE_HIP` 未定義 | 0 | `1` → 1、`2` 以上 → 2 | 0 以下 → 0、数値に変換できない値や空文字 → 0 |

具体例では `1suffix` は mode 1、` 2suffix` は mode 2、`3` は mode 2、`-4` は mode 0、`0anything` と空文字は mode 0 になる。大文字小文字は数値変換に関係しない。明示値は HIP の既定 2 も上書きし、空文字も「未設定」扱いにはならない（`engine/src/core/verify.cpp:435-443`）。

## 有効になる条件

- `Verifier::run()` の all-resident 経路であること。`ar_on()` は stage の全 expert が VRAM resident で、現在の window で `ar_off_` でない場合に限り true（`engine/include/strata/core/verify.hpp:596-603`）。初期選択には expert residency map が必要。`STRATA_VERIFY_ALL_RESIDENT` は未設定なら選択を許可し、設定時は `atoi` が 0 以外の場合だけ許可するため、`0`、空文字、数値に変換できない文字列で選択が無効になる。CLI による上書きはこの判定箇所にはない。loan、VRAM shrink、swap で expert が一時的に VRAM 外になるとその window は doorbell graph になり、この変数の分岐は動かない（`engine/src/core/verify.cpp:1377-1402, 3235-3251`）。
- HIP は `STRATA_USE_HIP` 定義時の既定値 2、CUDA 等の非-HIP build は既定値 0。Metal の `Verifier::run()` は別実装を実行して戻るため、この分岐は適用されない（`engine/src/core/verify.cpp:4-5, 3738-3819, 435-443`）。
- 今回の `run()` が prelaunch 済み (`pre`) でなく、`STRATA_TEST_VERIFY_STALL` が指定するテスト停止 window でないこと（`engine/src/core/verify.cpp:3862-3868`）。prelaunch 自体の launch は `Verifier::prelaunch()` が行い、この変数による flag の先行処理を通らない（`engine/src/core/verify.cpp:3710-3735`）。
- PLE の状態が準備済みで、この stage が layer 1 を含む場合だけ、launch 前に PLE rows を `gather_batch()` する。PLE が使われない場合も all-resident 経路では flag 自体を立てるが、PLE rows の gather は行わない（`engine/include/strata/core/verify.hpp:635`; `engine/src/core/verify.cpp:3851-3859, 3868-3877, 3979-3991`）。
- `run_slot_rows()` の batch window と `batch_serve()` は別経路であり、この mode を参照しない（`engine/src/core/verify.cpp:5370-5413, 5425-5433, 5675-5685`）。
- `STRATA_VERIFY_TIMEOUT_S` は host の layer wait の timeout を決める別設定で、この mode の選択値を変えない（`engine/src/core/verify.cpp:4001-4009`）。
- ソース全体で変数名を検索した結果、実読み取りは `engine/src/core/verify.cpp:437` のみ。共通 env helper や動的な名前渡しで読む箇所は見つからなかった。

## 実行時の詳細

`early_ple_flag_mode()` は関数内 `static const int` に結果を保存するため、環境値の読み取りは初回呼び出しの一度だけで、同一プロセス実行中の環境変更は反映されない。値は `Verifier::run()` の条件判定で使われる（`engine/src/core/verify.cpp:435-445, 3865-3868`）。

各 window はまず host flag を 0 に戻し、トークンごとの PLE row を準備する（`engine/src/core/verify.cpp:3563-3592, 3851-3860`）。その後 mode 1 は毎回、mode 2 は対応する graph の初回だけ、graph launch 前に（PLE が有効なら rows を gather して fence した後）host flag を 1 にする。launch 後の all-resident 分岐では、先に flag を立てていなければ PLE rows の gather 後に flag を立て、PLE がなければそのまま flag を立てる（`engine/src/core/verify.cpp:3865-3877, 3936-3942, 3979-3991`）。従ってこの変数が変えるのは host の PLE gather と flag raise の順序であり、mode 0 は launch call の後、mode 1/2 は call の前である。

mode 2 の「初回」は verifier が持つ window graph ごとに管理される。通常／doorbell graph、`sel_long_` の選択、window token 数 (`T`) に応じた追跡配列があり、graph の破棄・eviction 時には未起動状態へ戻る（`engine/include/strata/core/verify.hpp:688`; `engine/src/core/verify.cpp:3867, 5087-5096, 5112-5116`）。ただし early flag 条件自体は `ar_on()` が必要なので、対象となるのは all-resident graph である。

## ログと測定値

この変数専用のログはない。all-resident 切替時には独立して `strata verify: layers [...] ...` が stderr に出る。verify window が layer に到達しない場合などは通常の失敗経路として `verify: layer <n> never rang (...)` または `verify: timed out at layer <n>...` が返るが、これらの文言は変数値を識別しない（`engine/src/core/verify.cpp:3246-3250, 4023-4028, 4047-4061`）。本調査では新たな測定をしていない。

## 根拠

- 値の読み取り・既定値・clamp: `engine/src/core/verify.cpp:435-445`
- all-resident 選択と実行時の適用状態: `engine/src/core/verify.cpp:1377-1402, 3235-3251`; `engine/include/strata/core/verify.hpp:596-603`
- PLE rows と flag、launch 順: `engine/src/core/verify.cpp:3563-3592, 3851-3877, 3936-3942, 3979-3991`
- prelaunch・batch 除外と mode 2 graph bookkeeping: `engine/src/core/verify.cpp:3710-3735, 5370-5413, 5425-5433, 5675-5685, 5087-5096, 5112-5116`; `engine/include/strata/core/verify.hpp:688`
- 待ち失敗と観測文言: `engine/src/core/verify.cpp:4023-4028, 4047-4061`
