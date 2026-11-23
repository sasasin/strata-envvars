# `STRATA_TEST_POOL_DELAY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL のテスト用ビルドで、指定した verify window の CPU pool 処理後に待ち時間を挿入する fault-injection hook です。`STRATA_SYCL_TEST_HOOKS` が有効なビルドにだけ環境変数の読み取りがコンパイルされ、リリース用 engine にはこのスイッチがありません。通常の配布実行で使う設定ではありません（`engine/sycl/CMakeLists.txt:63-68`、`engine/sycl/src/core/verify.cpp:403-417`）。

## 値と判定

関数内の `static` 初期化時に `std::getenv` で値を一度読み、`std::sscanf(e, "%lld:%lld:%lld", ...) == 3` かつ第 3 値 `MS > 0` のときだけ hook を有効にします。3 つの変換後に文字列全体を検査しないため、3 番目の整数の後ろにある文字は無視されます。整数変換は `%lld` によるもので、真偽値・小数点形式の parser や範囲 clamp はありません（`engine/sycl/src/core/verify.cpp:406-413`）。

| 条件 | unset | 有効になる値の例 | sleep しない値の例 |
|---|---|---|---|
| `STRATA_SYCL_TEST_HOOKS` あり | 無効 | `0:1:10`（window 0、step 1 の後に 10 ms）、` 0: 1: 10tail`（数値変換が 3 つ成功し MS が正） | 空文字、`0:1:0`、`0:1:-1`、`x:1:10`、`0 :1:10` |
| `STRATA_SYCL_TEST_HOOKS` なし | 読み取り処理なし | 該当なし | すべての値（空関数） |

`getenv` が null の未設定と空文字はいずれも無効です。各 `%lld` は符号付き整数を読み、数値変換の前の空白は読み飛ばしますが、区切りの `:` はその位置に必要です。たとえば `0:1:10junk` は 3 変換が成功して受理され、`0 :1:10` は最初の数値と `:` の間に空白が入るため失敗します。window と step は指定整数との完全一致で照合されるため、負数は通常の非負カウンターとは一致しません。`MS` が 0 以下なら hook は有効になりません（`engine/sycl/src/core/verify.cpp:409-413`）。

## 有効になる条件

- SYCL backend を含み、CMake の `STRATA_SYCL_TEST_HOOKS=ON` で構築した engine が必要です。この CMake option の既定値は `OFF` です（`engine/sycl/CMakeLists.txt:63-68`）。
- `STRATA_TEST_POOL_DELAY` が上記の形式で読み取られ、正の `MS` が指定されている必要があります。
- 渡された `window` と `step` が設定した `W` と `K` に一致したときだけ sleep します。各呼び出し元は window カウンターと step カウンターを渡します（`engine/sycl/src/core/verify.cpp:2703-2708`、`3764-3768`、`4036-4042`、`4369-4375`）。
- GPU 側の bounded wait による失敗を発生させる試験では、小さい `STRATA_SPIN_MAX` と組み合わせる想定です。これは sleep の実行条件ではなく、コメントが記す fault-injection の試験条件です（`engine/sycl/src/core/verify.cpp:403-405`）。
- 他 backend、または test hook なしの build では、この変数だけを設定しても影響しません。

## 実行時の詳細

`test_pool_delay(window, step)` は SYCL verify 処理内の 4 経路から呼ばれ、CPU pool callback の後、`wait_failed` などの失敗確認の前に実行されます。対象は通常 window（`k`）、batch（`k`）、batch の逐次処理（`b_k_`）、pipelined window（`fl_k_`）です。該当する呼び出しでは `std::this_thread::sleep_for(std::chrono::milliseconds(tms))` を行います（`engine/sycl/src/core/verify.cpp:406-417`、`2700-2708`、`3761-3768`、`4036-4042`、`4369-4375`）。

環境変数は関数内 `static const bool on` の初回初期化時に一度読みます。同時に `tw`、`tk`、`tms` も設定されるため、そのプロセスで後から環境を変更しても反映されません。build で hook を除外した場合は本体が空で、引数を破棄するだけです（`engine/sycl/src/core/verify.cpp:406-416`）。

指定した処理が GPU の bounded wait を超えると、後続の `wait_failed` が期限切れ記録を検出し、`err` に `verify: the GPU stopped waiting for ...; the window was discarded` という内容を設定します。必要な drain が 5 秒以内に終わらない場合は `; the GPU did not finish within 5 s, so this verifier takes no further windows` が追記されます。各呼び出し元は失敗を返します。hook 自身はログを出さず、環境変数を読み取ったことを示す stdout/stderr 出力もありません（`engine/sycl/src/core/verify.cpp:477-499` および各呼び出し箇所）。

## ログと測定値

この hook 自身のログ出力や測定値はありません。GPU wait の期限切れ時には上記のエラー文字列が `err` に設定されます（`engine/sycl/src/core/verify.cpp:477-499`）。

## 根拠

- `engine/sycl/CMakeLists.txt:63-68` — test hook 用 CMake option、既定 `OFF`、compile definition。
- `engine/sycl/src/core/verify.cpp:403-417` — test hook の説明、値の読み取りと判定、sleep、および hook 無効時の空処理。
- `engine/sycl/src/core/verify.cpp:2700-2708`、`3761-3768`、`4036-4042`、`4369-4375` — verify 処理からの全呼び出し箇所と pool 処理との順序。
- `engine/sycl/src/core/verify.cpp:477-499` — bounded wait の失敗記録から `err` に設定される内容と drain 失敗時の追記。
