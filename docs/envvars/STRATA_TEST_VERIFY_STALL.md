# `STRATA_TEST_VERIFY_STALL`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

検証処理（`Verifier`）の指定した window で、最後の層の完了フラグをホストから通知しないテスト用フックです。GPU 側をフラグ待ちの状態にして、window の待機や stalled-engine watchdog による GPU wait の解放を調べるために使われます。コメントでも `test hook` と明記されており、通常利用者向けの性能・機能設定ではありません。

この名前を読む箇所は CUDA/HIP 共用の `src/core/verify.cpp` と SYCL 実装 `sycl/src/core/verify.cpp` の各1か所です。ソースツリー内の他の直接参照はありません。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | `g_test_stall` は `0`。フックは無効。 |
| 空文字、数値として読めない文字列 | `std::atoll` の変換結果が `0` となり、フックは無効。 |
| 正の整数 `N` | 各 `Verifier` の `windows + 1 == N` となる N 番目の window でフックを有効化。 |
| `0` または負数 | `g_test_stall > 0` の条件を満たさず、無効。 |

変換は `std::atoll` であり、文字列全体が整数かどうかを検証する処理ではありません。符号や先行空白を含む10進整数として変換され、数値部分の後ろに文字がある場合もその部分までの変換結果が使われます。大文字小文字の比較はありません。値は namespace scope の `const` 初期化で読み取られるため、プロセスの起動時に一度だけ評価され、起動後の環境変更は反映されません。

## 有効になる条件

- 検証 window を実行する経路でのみ効果があります。
- window 番号は `Verifier` の `windows` カウンターを基準にした1始まりです。複数 stage の layer split では verifier ごとにカウンターがあるため、指定した N がプロセス全体でただ一度だけ起きるとは限りません。
- CUDA/HIP 共用コードでは、指定 window の all-resident 経路で通常先に立てるフラグを立てず、ホスト側の層ごとの処理へ進みます。最後のステップを除く通常の処理後フラグは立てます。
- SYCL では対象 window に限り `stepped_ar` を無効化します。all-resident の通常早期フラグ通知も抑止し、最後の層のフラグを立てません。`STRATA_VERIFY_NO_HOST` が有効な経路ではホストが各層を処理するループ自体がスキップされるため、window 内の待ち方はその設定にも依存します。
- フックが止めるのは完了フラグの通知です。window が最後まで進むか、watchdog が作動するかは実行経路と他の設定に依存します。

## 実行時の詳細

CUDA/HIP 共用コードでは `test_stall` を `g_test_stall > 0 && windows + 1 == g_test_stall` で決めます。該当 window では最終ステップの `*flag = want` を飛ばします。GPU がその flag を待ち続ける状態を作り、後続の stream 同期が完了しなくなります。

SYCL でも同じ条件で対象 window を選び、層処理ループ末尾の最終 flag 書き込みを省きます。SYCL の stepped all-resident 経路では、対象 window に限って stepped 実行を選ばず、停止を発生させる経路に入ります。

server 経路の stalled watchdog は既定で request 中の進捗が60秒止まると停止処理に入り、診断を stderr に出した後 `release_gpu_waits(stderr)` を呼び、検証処理が待つ flag を解放してから engine を abort します。`STRATA_WATCHDOG_S` による時間変更などは watchdog 側の別設定です。フック自体はログを出さず、対象 window が停止することが観測結果です。watchdog による終了時には `strata serve: no progress for ...` 等の診断と GPU wait 解放のログが出ます。

## 根拠

- `src/core/verify.cpp:385-390`: CUDA/HIP 共用実装のテストフック説明、環境変数読み取り、`std::atoll` 変換。
- `src/core/verify.cpp:2301-2302, 2313-2314, 2401`: 対象 window の判定、通常の flag 通知分岐、最後の flag 書き込み抑止。
- `sycl/src/core/verify.cpp:306-311`: SYCL 実装の読み取りと変換。
- `sycl/src/core/verify.cpp:2042-2044, 2185-2200, 2296`: 対象 window での stepped 経路調整、all-resident 分岐、最終 flag 書き込み抑止。
- `src/program/generate.cpp:9659-9667` および `sycl/src/program/generate.cpp:8656-8662`: stalled watchdog の診断、GPU wait 解放、engine 停止。
- `docs/` 内にこの環境変数の直接説明は見つかりませんでした。値の意味は上記ソース実装に基づきます。
