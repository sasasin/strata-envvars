# `STRATA_PARK_HOST_MEMCPY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

会話 snapshot の K/V を park（保存）・restore（復元）するとき、streamed K/V または draft ring のホスト側にある 4 部分を `std::memcpy` でコピーする経路を選ぶ。保存時は `ConversationBuffer` の確保とコピー方式を切り替え、復元時は同じ 4 部分をホストメモリ間でコピーする。通常経路にある CUDA copy 呼び出しをこの 4 部分では使わない。インデックス用の第 5 部分やモデル計算を切り替える設定ではない。`conversation_kv_save` と restore 関数で参照される（`engine/src/core/conversation_snapshot.cpp:274-283,418-465,664-699`）。

## 値と判定

`park_host_memcpy_on()` が `std::getenv` で値を読み、先頭文字だけで判定する。文字列全体の parse、空白除去、大文字小文字変換はしない。unset と空文字、また先頭文字が `0` の値は OFF。それ以外の先頭文字なら ON（`1`, `true`, `false`, `2`, ` 0`, `0anything` の例はそれぞれ ON, ON, ON, ON, ON, OFF）。数値妥当性や残りの文字列は検査しない（`engine/src/core/conversation_snapshot.cpp:277-283`）。

| ビルド・実行条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `conversation_snapshot.cpp` を含むビルド | OFF | 空でなく先頭文字が `0` 以外 | 空文字、先頭文字が `0` |

## 有効になる条件

- `QsaState::kv_mode != 0` のときだけ保存・復元経路で使用される。値が ON でも `kv_mode == 0` なら通常のコピー経路を使う（`engine/src/core/conversation_snapshot.cpp:441,449,680,726`）。
- このファイルに OS / backend / build macro による環境変数判定のガードはない。CUDA/HIP 共通の engine ソースに加え、SYCL と Metal のビルド定義にも同ファイルが含まれる（`engine/cmake/strata_gpu_engine.cmake:310-314`, `engine/sycl/CMakeLists.txt:290-296`, `engine/metal/CMakeLists.txt:135-141`）。ただし実際に経路へ入る条件は上記の `kv_mode` 判定であり、各 backend での対応モードの可否はこの環境変数の読み取り箇所では決めていない。
- restore で画像が `STRATA_PARK_VRAM_MIB` の VRAM slot にある場合は、slot からの転送が先に選ばれ、この host memcpy 経路を通らない（`engine/src/core/conversation_snapshot.cpp:666-699,704-745`）。
- 保存時に 4 MiB 単位へ分けて並列コピーする worker 数は、別変数 `STRATA_PARK_COPY_THREADS` で決まる。これは未設定なら 8、値を `atoi` し 1〜16 に clamp（0 以下や不正文字列は 8）して static cache する（`engine/src/core/conversation_snapshot.cpp:285-291,376-391`）。

## 実行時の詳細

環境変数は `park_host_memcpy_on()` の最初の呼び出し時に一度読み、関数内 `static const bool` に保持する。保存・復元ごとの再読込ではなく、プロセス起動後に環境を変更しても反映されない（`engine/src/core/conversation_snapshot.cpp:277-283`）。

保存時、`conversation_kv_save` は `fast_host = 設定 ON && kv_mode != 0` を計算し、配列の先頭 4 部分で `resize_for_overwrite` を行う。再利用済み prefix の後ろを host copy span に積み、span があれば `parallel_host_memcpy` でコピーする。既存 prefix はそのまま再利用する。第 5 部分はこの分岐の対象外で、通常の save 処理へ進む（`engine/src/core/conversation_snapshot.cpp:436-465,528-534`）。snapshot save は各 layer と draft layer についてこの関数を呼ぶ（`engine/src/core/conversation_state.cpp:639-646,677-680`）。

復元と prefix 復元では、VRAM slot がない場合に先頭 4 部分を host span として `parallel_host_memcpy` し、第 5 部分は `transfer` でコピーする。設定 OFF または `kv_mode == 0` なら全部分を通常の `transfer` 経路でコピーする。復元後は residency を更新する（`engine/src/core/conversation_snapshot.cpp:664-699,702-745`）。並列 pool は最初の非空コピーで作られ、プロセス中に再利用される。span が 1 個以下、または worker がない場合は呼び出し側スレッドがコピーする（`engine/src/core/conversation_snapshot.cpp:328-350,376-391`）。

## ログと測定値

この変数の値を表示する専用ログはない。保存経路で必要な入力 pointer がない場合は `conversation snapshot: missing state buffer` を error に設定して失敗する。復元時の第 5 部分など通常の transfer が失敗した場合は `conversation snapshot copy: <CUDA error>` を設定する。上位の snapshot save は `false` を返し、通常 restore は `ConversationRestore::transfer_failed` を返す（`engine/src/core/conversation_snapshot.cpp:264-271,449-462,680-699,726-745`; `engine/src/core/conversation_state.cpp:641-645,899-912`）。この変数による性能測定値は、対象 commit のコードおよび参照した `docs/DETAILS.md` に見つからなかった。

## 根拠

- 値の読み取り・判定・cache: `engine/src/core/conversation_snapshot.cpp:277-283`
- worker pool と chunked host copy: `engine/src/core/conversation_snapshot.cpp:285-291,300-391`
- 保存時の適用範囲と第 5 部分の通常処理: `engine/src/core/conversation_snapshot.cpp:436-465,528-534`
- restore / prefix restore と VRAM slot・通常 transfer の分岐: `engine/src/core/conversation_snapshot.cpp:664-699,702-745`
- snapshot save / restore の呼び出し元と失敗結果: `engine/src/core/conversation_state.cpp:639-646,677-680,899-912`
- ビルドへの組み込み: `engine/cmake/strata_gpu_engine.cmake:310-314`, `engine/sycl/CMakeLists.txt:290-296`, `engine/metal/CMakeLists.txt:135-141`
