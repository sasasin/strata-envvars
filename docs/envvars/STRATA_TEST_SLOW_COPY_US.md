# `STRATA_TEST_SLOW_COPY_US`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA/HIP エンジンの会話 checkpoint をホストメモリ上で複製するとき、複製の各約 1 MiB 区間の後に指定マイクロ秒だけ待つフックです。コピー内容や checkpoint の選択は変えず、区間ごとの待ち時間を加えます。コメントは「tests only」としていますが、この値を読むコードにテスト専用の `#if` や build macro ガードはなく、`strata_engine` に含まれる共有実装です。実際に効くのは checkpoint / snapshot のコピー関数が呼ばれたときです（`engine/src/core/conversation_copy.hpp:167-183,206-216`、`engine/cmake/strata_gpu_engine.cmake:305-316`）。

## 値と判定

`test_slow_copy_us()` が `std::getenv` で読み、`std::atol` で `long` に変換します。文字列全体の検証、`errno` 確認、範囲制限はありません。`atol` が読める先頭の符号付き整数部分だけを使い、先頭の空白は許容し、後続の非数字は無視します。得た値が `> 0` の場合だけ待ちます（`engine/src/core/conversation_copy.hpp:169-171,182,215`）。

| 条件 | 未設定 | 待ちが有効になる値の例 | 待ちが無効になる値の例 |
|---|---|---|---|
| この CUDA/HIP コピー実装 | `0`（待ちなし） | `1` は区間ごとに 1 µs、`12tail` は 12 µs、`  +12x` は 12 µs、`2.5` は 2 µs | 空文字、`0`、`0anything`、`true`、`-1` は変換結果が正にならず待ちなし |

数値として読めない先頭部分は `atol` により `0` です。`long` の表現範囲外の文字列に対する `atol` の結果は安全に扱うコードがなく、この実装では有効な設定値として保証されません（`engine/src/core/conversation_copy.hpp:169-170`）。

## 有効になる条件

- `engine/src/core/conversation_copy.hpp` を含む CUDA/HIP の `strata_engine` が使われること。この名前の読み取りはリポジトリ内で同ファイルの 1 箇所だけにあり、SYCL / Metal 側の別実装では見つかりません（`engine/src/core/conversation_copy.hpp:169-170`、`engine/cmake/strata_gpu_engine.cmake:310-316`）。
- checkpoint の保存・snapshot・交換で、`copy_checkpoints_beating` または `copy_beating` / `assign_beating` が実行され、対象 vector に少なくとも 1 区間の要素があること。呼び出し元には会話の park、セッション保存、park 済み会話の交換があります（`engine/src/core/conversation_state.cpp:563-592,703-721,829-845`、`engine/src/program/generate.cpp:14467-14482,18687-18703,19803-19809`）。空の vector はループに入らず、この値を読む呼び出しも起きません。
- CLI 引数による上書きや、この値の既定値を変える別環境変数はありません。読み取りはプロセス環境から直接行われます（`engine/src/core/conversation_copy.hpp:169-171`）。

## 実行時の詳細

最初に非空のコピー区間で `test_slow_copy_us()` が呼ばれると、関数内 `static` に変換値を保存します。その後のコピーでは同じ値を使い、プロセス実行中に環境を変更しても反映されません。未設定ならキャッシュされる値は `0` です（`engine/src/core/conversation_copy.hpp:169-171,175-183`）。

`copy_beating` と `assign_beating` は各 vector を最大およそ 1 MiB 相当の要素数に分けて複製し、各区間の複製後に値が正なら `sleep_for(microseconds(us))` を呼び、その後 `progress_beat()` を行います。最後の短い区間にも待ちが入ります。checkpoint 内の複数 vector と再帰的な `stage_parts` それぞれで同じ処理を行います。park 済み会話の交換では checkpoint に加えて live の `ids` と `images` も `copy_beating` で複製されます（`engine/src/core/conversation_copy.hpp:175-216,188-203,220-250`、`engine/src/core/conversation_state.cpp:842-845`）。

この処理はコピーを遅らせますが、コピーする配列の値は通常どおり複製されます。`progress_beat()` は進捗カウンターを増やします（`engine/include/strata/core/progress.hpp:56-70`）。serve watchdog は進捗が止まった時間を監視し、既定で 60 秒間 heartbeat がなく、I/O 猶予も適用されない場合は stderr に停止メッセージを出して `abort()` します。したがって、非常に長い待ちの最中に他の進捗がなく watchdog の期限に達すれば、追加待ちが停止経路に関係します。これはこの変数固有のログやエラーではありません（`engine/src/program/generate.cpp:16261-16271,16287-16321`）。

## ログと測定値

この変数を読み取ったことや待ちを加えたことを示す専用ログはありません。上記 watchdog 条件に該当すると、実装は `strata serve: no progress for %lld s during a request (%s) - stopping the engine so the server starts it again (issue #29)` を stderr に出し、GPU wait を解放して `abort()` します（`engine/src/program/generate.cpp:16313-16321`）。

この変数を使った性能測定値は `docs/DETAILS.md` に見つかりません。同資料の会話コピー表は別の `STRATA_CKPT_*` / `STRATA_PARK_*` スイッチの測定であり、本変数の測定値としては扱いません（`docs/DETAILS.md:1784-1800`）。

## 根拠

- 環境読み取り・変換・キャッシュ: `engine/src/core/conversation_copy.hpp:167-171`
- 区間分割・追加待ち・進捗通知: `engine/src/core/conversation_copy.hpp:175-216`
- checkpoint vector の複製と再帰処理: `engine/src/core/conversation_copy.hpp:188-252`
- snapshot / session / swap の呼び出し元: `engine/src/core/conversation_state.cpp:563-592,703-721,829-845`、`engine/src/program/generate.cpp:14467-14482,18687-18703,19803-19809`
- CUDA/HIP エンジンへの組み込み: `engine/cmake/strata_gpu_engine.cmake:305-316`
- heartbeat の実装と serve watchdog: `engine/include/strata/core/progress.hpp:56-75`、`engine/src/program/generate.cpp:16261-16321`
- 関連コピー機能の資料との照合: `docs/DETAILS.md:1784-1800`
