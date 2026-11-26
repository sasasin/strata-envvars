# `STRATA_DOORBELL_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL エンジンの doorbell handoff で、GPU が公開した payload（activation `x`、expert ID、存在する場合は routing weight）の checksum をホスト側で確認し、ring の通知後も payload が一致するまで待つ診断・整合性確認用の切り替えである。未有効時の `doorbell_wait_payload` は直ちに成功を返す。有効時は ring tag と checksum を検査し、既定 2 秒以内に一致しなければ呼び出し側へ失敗を返す（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:829-852`、timeout の既定値は `engine/include/strata/kernels/elementwise.hpp:140-144`）。

`doorbell_publish_res` が使われる verify 経路では、同じ環境変数を使って「全 payload を公開し checksum を付ける」側も切り替える。有効時は、全 routed expert が VRAM 常駐で通常なら省略される `x` のコピーも行う。無効時は、resident 状態を見て必要なときだけ `x` を公開する旧経路になる（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:676-719,800-826`）。この環境変数は生成 token や expert 選択を直接変更する設定ではなく、doorbell handoff の公開・検査方法を変える。

## 値と判定

読み取りは `std::getenv` の戻り値が null でないことに加え、最初の byte `v[0]` が文字 `'1'` かを比較する。文字列全体の数値 parse、空白除去、大文字小文字変換はしない。`doorbell_publish_res` と `doorbell_wait_payload` に独立した関数内 `static const bool` があり、それぞれ最初の呼び出し時に判定を cache する（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:803-804,844-845`）。

| ビルド／経路 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| SYCL の `doorbell_publish_res` | `full=false`。resident expert のみなら `x` の公開を省く | `1`、`10`、`1anything`（先頭が `'1'`） | 空文字、`0`、`true`、` 1`、`01`。いずれも全 payload 公開を選ばない |
| SYCL の `doorbell_wait_payload` | `check=false`。checksum 待機をせず `true` を返す | `1`、`10`、`1anything`（先頭が `'1'`） | 空文字、`0`、`true`、` 1`、`01`。いずれも checksum 検査をしない |

数値としての妥当性や境界はない。空文字は設定済みでも先頭 byte が終端文字なので無効。判定は大文字小文字を区別する形の文字比較であり、`TRUE` も有効値ではない。CLI 引数や設定ファイルによる上書き・優先順位はこの読み取り箇所にはない。

## 有効になる条件

- この読み取りは `engine/sycl/src/kernels/cuda/elementwise.dp.cpp` にあり、SYCL エンジンの doorbell 実装に限られる。リポジトリ内の同名参照を全検索した結果、他 backend の実行コードによる読み取りは見つからなかった。
- `doorbell_wait_payload` が呼ばれる session / verify の doorbell handoff 経路で checksum 検査が有効になる。通常の SYCL `doorbell_publish` 系は `x` と IDs（および該当形では weights）を公開する。`doorbell_publish_res` は verify で `remote_opt_` と `always_publish_` のいずれも有効でなく、`lean` でもない場合に選ばれる（`engine/sycl/src/core/verify.cpp:1622-1637`）。
- `doorbell_publish_res` が使われる場合、値が有効なら routed expert の常駐状態に関係なく `x` と IDs を公開し checksum を付ける。値が無効なら IDs は公開するが、`x` は routed expert に miss がある場合だけコピーされる（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:685-719`）。
- SYCL の CMake では `sycl_payload_pairs` テストに限り `STRATA_DOORBELL_CHECK=1` を設定している（`engine/sycl/CMakeLists.txt:659-662`）。これはテストの環境設定であり、通常実行時の既定値を変えるものではない。
- この変数による CLI 優先順位、OS 別の別判定、モデル状態以外の追加条件は実装にない。機能が呼び出されなければ値を読まない。

## 実行時の詳細

`doorbell_publish_res` の初回呼び出し時に `full` を cache し、kernel に渡す。`full=false` の kernel は IDs を mapped host memory に保存し、`d_res` の各 routed ID の常駐状況を調べる。`d_res` が null、ID が範囲外、または該当 expert が resident でない場合は `x` もコピーする。`full=true` では `x` と IDs 全体から checksum を計算し、ring とともに公開する（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:676-719,800-826`）。

`doorbell_wait_payload` も初回呼び出し時に独立して `check` を cache する。無効なら何も検査せず成功を返す。有効なら、まず ring slot の tag が期待する sequence number と等しいことを確認し、acquire fence の後に `x` と IDs、続いて weights あり／なしの checksum のどちらかを照合する。不一致なら最大 `timeout_ms` まで再読し、64 回の x86 pause を挟む。timeout の既定値は 2000 ms であり、コード上ではこの既定値を上書きする呼び出しはない（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:829-852`、`engine/include/strata/kernels/elementwise.hpp:140-144`）。

プロセス実行中に環境を変更しても、各関数の `static` 判定が初期化された後は反映されない。二つの cache は別々に初期化されるが、通常は同一プロセス環境をそれぞれの初回呼び出し時に読む。子プロセスへの転送や環境書き換えはこの実装にない。

関連設計資料 `docs/A770_SPEED_SPEC.md:735-737` には旧名 `STRATA_DOORBELL_NOCHECK` が記載される。現行 checkout の対象実装はその名前を読まず、`STRATA_DOORBELL_CHECK` を上記の checksum 検査と publish 分岐に使うため、ここでは現行ソースの挙動を記載した。

## ログと測定値

この環境変数自体の有効・無効を知らせるログはない。checksum が timeout した場合、session 経路は `session_loop: layer <n> rang but its payload never arrived whole` を error に設定して `false` を返し、generate の呼び出し元は `strata generate: session_loop: %s` を stderr に出して終了コード 1 を返す（`engine/sycl/src/core/session.cpp:1002-1008`、`engine/sycl/src/program/generate.cpp:13518-13521`）。verify 経路は `verify: layer <n> rang but its payload never arrived whole` を設定し、通常処理では `false`、pipelined 処理では `-1` を返す（`engine/sycl/src/core/verify.cpp:2693-2699,4362-4368`）。

ソースコメントは、Arc A750（i915）で uncached host memory 上の payload checksum を CPU expert layer あたり 2 回読むコストを、5 回の interleaved rounds で decode の 15–20% と記録している（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:841-843`）。コメントにはモデル、量子化、個別設定がないため、この数値はその条件を超えて一般化できない。コメントは guarded payload で stale data を観測しなかったとも記すが、独立した再測定値としては扱わない。

## 根拠

- `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:676-719,800-826` — `doorbell_publish_res` の値判定、resident 判定、payload と ring の公開。
- `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:829-852` — checksum の照合、cache、pause loop、timeout。
- `engine/include/strata/kernels/elementwise.hpp:140-144` — wait 関数の宣言と既定 timeout。
- `engine/sycl/src/core/verify.cpp:1622-1637,2693-2699,4362-4368` — producer の選択と verify 側の wait・失敗。
- `engine/sycl/src/core/session.cpp:1002-1008`、`engine/sycl/src/program/generate.cpp:13518-13521` — session 側の失敗伝播。
- `engine/sycl/CMakeLists.txt:659-662` — テスト専用の環境設定。
