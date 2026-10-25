# `STRATA_TEST_PIN_BUDGET_MIB`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

テスト用の pinned-memory 上限を MiB 単位で設定します。上限を有効にすると、Strata の pinned-memory wrapper を通る host allocation と host registration を合算し、設定値を超える要求を CUDA の `cudaErrorMemoryAllocation` 相当として拒否します。Windows の WDDM で pinned memory の予算を使い切る状態を、Linux などでも再現するためのフックです。通常利用者向けの実メモリ上限設定ではなく、ソースコメントでも `TEST knob` とされています。

## 値と判定

`pin_detail::State` のコンストラクターが `std::getenv()` で読み、値が未設定または空文字なら `sim_budget` は初期値の 0（シミュレーション無効）のままです。空でない値は `std::strtoull(e, nullptr, 10)` で変換し、結果を `uint64_t` にしてから 20 bit 左シフトします。単位は MiB です。

| 値 | 判定結果 |
|---|---|
| 未設定、空文字 | 上限 0。シミュレーション無効 |
| `100` | 100 MiB の上限 |
| `100tail` | 先頭の数値部分 `100` を採用し、100 MiB |
| 数字で始まらない文字列（例: `abc`） | `strtoull` の変換結果 0 となり、シミュレーション無効 |
| 先頭空白の後に数値 | `strtoull` が数値を変換し、変換した MiB 数を使用 |
| `0` | 上限 0 となり、シミュレーション無効 |

全体が数値であることの検査、範囲チェック、エラー時の別値への fallback はありません。負数や `unsigned long long` の範囲を超える数値も、`strtoull` の戻り値をそのまま 64 bit unsigned 値として左シフトするため、通常の正の MiB 数と同じ意味になるとは限りません。設定値として使う場合は非負の 10 進整数を指定してください。

## 有効になる条件

- このフックは `include/strata/core/pin_budget.hpp` の CUDA pinned-memory wrapper にあります。ソース上のテストプログラム `src/core/pin_budget_test.cpp` も同じヘッダーを使います。
- `STRATA_TEST_PIN_BUDGET_MIB` を設定しても、wrapper を通らない CUDA allocation / registration を制限するものではありません。上限の対象はこのヘッダーの `pin_register()` と `host_alloc_guarded()` が追跡する要求です。
- 非ゼロのシミュレーション上限があると、Windows CUDA 以外でも `STRATA_PIN_RESERVE_MIB` が未設定の場合の soft reserve 既定値は 640 MiB になります。`STRATA_PIN_RESERVE_MIB` が明示設定されている場合は、その値が soft reserve です。soft reserve と hard reserve も追跡上限を消費するため、小さなテスト上限では reserve の取得や arena の pin が縮小・失敗し得ます。
- `STRATA_TEST_PIN_LEFT_KIB` が同時に設定されている場合、arena を開いた後に上限が `現在の追跡使用量 + 指定 KiB` に変更されます。これは別のテスト用変数であり、この文書の対象外です。

## 実行時の詳細

設定値は `pin_detail::State` の関数内 static singleton が初めて構築される時に読み込まれます。同じプロセスで後から環境変数を書き換えても上限は再評価されません。実行時の `generate` 経路では、expert arena を開く前に headroom reserve を取り、arena を開いた後に実際の pin 量を記録し、soft reserve を返します。engine が READY になった時点では headroom 状態を報告して hard reserve を解放します。

上限が 0 のとき、registration wrapper は通常の `cudaHostRegister()` へ進み、allocation wrapper も上限チェックを通さず通常の `cudaHostAlloc()` を呼びます。上限が非 0 のときは、成功した registration / allocation の byte 数を使用量に加算し、対応する unregister / free で差し引きます。新しい要求で使用量が上限を超える場合は拒否します。required host allocation では、reserve が残っていればそれを返して一度だけ再試行します。再試行も失敗した場合は呼び出し元に失敗が返り、通常のエラー処理が行われます。

シミュレーション中は stderr に `strata: test pinned budget ...` の使用量・peak 報告が出ます。headroom の確保・解放や retry に関するログも同じ pinned-memory 管理コードから出力されます。これは Strata wrapper が返す割り当て結果を再現する仕組みであり、OS や GPU driver 自身の実 pinned-memory 制限を変更するものではありません。

## 根拠

- `include/strata/core/pin_budget.hpp:20-22` — 目的とテスト専用フックであること。
- `include/strata/core/pin_budget.hpp:38-58` — 初期値、環境変数の読み取り、MiB から byte への変換、および初回 singleton 構築。
- `include/strata/core/pin_budget.hpp:60-87,100-117` — allocation / registration の追跡、上限超過時の拒否と解放時の減算。
- `include/strata/core/pin_budget.hpp:89-97,119-149,151-189,191-209` — reserve の既定値と取得、残量テストフック、報告、失敗時の reserve 解放と一度の retry。
- `src/program/generate.cpp:5800-5808,11021-11022` — generate 経路での reserve / arena 処理と READY 時の報告・hard reserve 解放。
- `src/core/pinned.cu:447,467,575,631,660-672` — expert arena の registration と unregister が wrapper を通る箇所。
- `src/core/session.cpp:545`, `src/core/verify.cpp:424`, `src/core/layer.cpp:588,896-898`, `src/core/mtp.cpp:97` — engine の required pinned allocation が wrapper を通る箇所。
- `docs/DETAILS.md:217-224` — pinned-memory headroom の設計説明と、この変数を test knob とする記述。仕様の値判定は実装を根拠とした。

