# `STRATA_KV_COPY_RESIDENT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

バッチ slot とメイン session の間で K/V を直接コピーするとき、streaming K/V state の VRAM 常駐ページと対応 map もコピーするかを選ぶ変数。未設定または無効値では従来どおりコピー先の residency をリセットする。これは `conversation_kv_copy` 内の opt-in であり、通常の snapshot save/restore 経路は変更しない。`engine/src/core/conversation_snapshot.cpp:577-597, 625-661`。

## 値と判定

`copy_residency` の初回呼び出し時に `std::getenv` で読み、未設定でなく、空文字でなく、先頭文字が `'0'` でなければ有効とする。文字列全体の parse、数値変換、大小文字変換はしない。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `engine/src/core/conversation_snapshot.cpp` の実装 | 無効 | 先頭が `0` 以外の非空文字列（例: `1`, `true`, `false`, ` 0`） | 空文字、先頭が `0` の文字列（例: `0`, `0anything`, `00`, `00x`） |

したがって `false` や空白で始まる値も有効になり、`0anything` は無効になる。値域・境界値の数値判定はない。`static const bool on` の初期化結果を使い続けるため、プロセス起動後に環境値を変更しても反映されない。`engine/src/core/conversation_snapshot.cpp:588-592`。

## 有効になる条件

- `engine/src/program/generate.cpp` のバッチ slot 処理が K/V の直接コピーを選ぶ必要がある。`STRATA_SLOT_COPY_DIRECT` が同じ先頭文字ルールで有効な場合、slot への admission と checkpoint なしの slot hand-back は `direct_slot_copy` を通る。checkpoint 付き hand-back はさらに `STRATA_SLOT_CKPT_KV_DIRECT` が有効なとき `conversation_kv_copy` を呼ぶ。`engine/src/program/generate.cpp:16762-16766, 16783-16910`。
- `--batch` の slot を使うバッチ処理が動作していること。通常の checkpoint/KV の host image save/restore 経路では、この変数を読む `copy_residency` は呼ばれない。`engine/src/program/generate.cpp:16798-16825, 16852-16911`。
- コピー元・コピー先の両方が `kv_mode == 1` の streaming state で、slot 数・block 数が一致し、正数の slot と必要な map/device buffer がそろっていること。どれかを満たさなければ residency はコピーされず、コピー先の residency refresh に進む。`engine/src/core/conversation_snapshot.cpp:588-605, 653-661`。
- この最適化は `engine/src/core/conversation_snapshot.cpp` の CUDA/HIP 共通エンジン実装にある。SYCL は別実装 `engine/sycl/src/core/conversation_snapshot.cpp` を使い、対象名の読み取りはない。Metal の slot copy は `window_slot_copy_main` を呼んで戻るため、この `conversation_kv_copy` の分岐には進まない。`engine/cmake/strata_gpu_engine.cmake:310-316`, `engine/sycl/CMakeLists.txt:290-297`, `engine/metal/CMakeLists.txt:135-141`, `engine/src/program/generate.cpp:16798-16808, 16852-16860`。
- CLI 引数や他変数がこの値を上書きする処理はない。`STRATA_SLOT_COPY_DIRECT` と `STRATA_SLOT_CKPT_KV_DIRECT` は上記の直接コピー経路の選択条件であり、この変数だけではその経路を有効にしない。`engine/src/program/generate.cpp:16762-16766, 16865-16873`。

## 実行時の詳細

`conversation_kv_copy` はまず authoritative K/V pool のデータをコピーする。その後 `copy_residency` が有効かつ両 state の条件が合えば、streaming state の VRAM K/V ページと page table、slot map / stamp / reference、制御値をコピーし、通常の residency refresh を省く。コピーする map 制御値は epoch、clock hand、直近 call の miss と overflow。条件を満たさない場合や変数が無効の場合は、`refresh_residency` が `kv_mode == 1` の map を reset する。`engine/src/core/conversation_snapshot.cpp:577-621, 625-661`。

環境値は `copy_residency` の関数内 static に初回だけ cache される。読み取りはプロセス起動時ではなく、最初に `conversation_kv_copy` が呼ばれたとき。以降の変更は反映されない。`queued` コピーの場合も residency コピーを同じコピー方法で投入し、上位の slot copy が device 同期を行う。`engine/src/core/conversation_snapshot.cpp:588-592, 606-620`; `engine/src/program/generate.cpp:16767-16796`。

## ログと測定値

この変数の有効・無効を示す専用ログはない。residency 転送 API が失敗すると `conversation snapshot residency copy: ` に CUDA/HIP runtime のエラー文字列を付けて呼び出し元へ返す。slot hand-back では失敗が stderr の `strata batch: restoring slot %d failed (%s); reading the prompt` となり、プロンプト先頭から読み直す。batch admission の失敗は stderr の `strata serve: batch admission failed: %s` となり、その slot の cache を無効にする。`engine/src/core/conversation_snapshot.cpp:606-620`; `engine/src/program/generate.cpp:19757-19770, 23480-23489`。

## 根拠

- `engine/src/core/conversation_snapshot.cpp:577-621, 625-661` — residency コピー、値の判定、失敗文字列、K/V copy と refresh の順序。
- `engine/src/program/generate.cpp:16762-16796, 16798-16825, 16852-16911` — direct slot copy の選択、呼び出し経路、checkpoint 付き hand-back の追加条件。
- `engine/src/program/generate.cpp:19757-19770, 23480-23489` — copy failure の観測結果と fallback。
- `engine/cmake/strata_gpu_engine.cmake:310-316`, `engine/sycl/CMakeLists.txt:290-297`, `engine/metal/CMakeLists.txt:135-141` — backend ごとの source 構成。
