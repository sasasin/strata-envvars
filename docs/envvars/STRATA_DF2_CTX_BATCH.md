# `STRATA_DF2_CTX_BATCH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

DFlash2 drafter の `context()` が8行を超える tap/context 更新を、最大64行単位のまとめ処理で実行するかを選ぶ。既定ではまとめ処理を使い、`0` で始まる値を指定すると従来の最大8行単位の処理へ戻る。まとめ処理側も同じ DFlash2 context 更新を行うが、量子化・GEMM・K/V ring 更新を最大64行のバッファで進める。実装は CUDA/HIP 共通の `engine/src/core/dflash2.cpp` にある。 (`engine/src/core/dflash2.cpp:1044-1053`, `engine/src/core/dflash2.cpp:1082-1114`, `engine/src/core/dflash2.cpp:1129-1142`)

この環境変数は DFlash2 の drafter が実際に `context()` を呼ぶときだけ関係する。通常の MTP や DFlash2 を使わない実行では参照されない。DFlash2 は `--draft dflash2` 等で選択する機能であり、serve では tap を DFlash2 に渡し、prompt 行数分の `context()` を呼ぶ経路がある。 (`engine/include/strata/core/dflash2.hpp:1-16`, `engine/src/program/generate.cpp:13505-13516`, `engine/src/program/generate.cpp:13528-13534`, `engine/src/program/generate.cpp:20362-20367`)

## 値と判定

`context()` 内の関数ローカル `static const bool` 初期化で `std::getenv` を一度呼び、環境変数が未設定なら有効、設定済みなら先頭文字が `'0'` 以外のとき有効とする。文字列全体の比較や数値変換はしない。したがって空文字は有効、`0`・`0anything` は無効、`00` も無効、`1`・`10`・`true`・`false`・先頭が空白の値は有効である。大文字小文字は判定に影響しない。 (`engine/src/core/dflash2.cpp:1048-1051`)

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP build で DFlash2 `context()` に入る | 有効 | 空文字、`1`、`10`、`true`、`false`、` 0` | `0`、`0anything`、`00` |

## 有効になる条件

- DFlash2 がビルドされている CUDA または HIP backend が対象。CMake は DFlash2 の実装を CUDA/HIP build に含め、Metal と SYCL build には含めない。 (`engine/cmake/strata_gpu_engine.cmake:6-13`)
- DFlash2 drafter が開始・設定され、tap rows の更新として `Dflash2Drafter::context()` が呼ばれる必要がある。`--draft` などは DFlash2 を選択する条件であり、この環境変数の値を上書きする CLI 引数は `context()` の実装にはない。実装はプロセス環境を直接読む。CLI/serve の呼び出し元が DFlash2 を選択・準備する流れは `engine/src/program/generate.cpp:13505-13516`、`engine/src/program/generate.cpp:13528-13534` にある。
- `context()` の `n` が `kRows`（8）より大きいこと。8以下なら環境変数にかかわらず通常の経路を使う。 (`engine/include/strata/core/dflash2.hpp:39`, `engine/src/core/dflash2.cpp:1052`, `engine/src/core/dflash2.cpp:1129-1142`)
- `STRATA_DF2_PROFILE=1` で profiling が有効なときはまとめ処理を使わない。profiling は drafter の stream 初期化時に別の環境変数を読み `prof_` を設定する。 (`engine/src/core/dflash2.cpp:296`, `engine/src/core/dflash2.cpp:1052`)
- まとめ用 device buffer / event の確保が成功する必要がある。確保に失敗すると、この環境変数の有効値にかかわらず通常の経路へ進む。 (`engine/src/core/dflash2.cpp:98-126`, `engine/src/core/dflash2.cpp:1052`)

## 実行時の詳細

値の判定は最初に `context()` が実行された時点で行われ、関数ローカル static に保持される。同じプロセス内で後から環境を変更しても判定は変わらず、複数の drafter instance も同じ cache を共有する。まとめ用リソースは、判定が有効で `n > 8` となる最初の呼び出しで `ensure_ctx_batch()` が遅延確保し、その後は `ctx_batch_` を再利用する。確保失敗時は allocation を解放して `false` を返すため、その呼び出しは8行単位の通常経路へ進み、後の呼び出しで再試行できる。失敗時に `err` は設定されない。 (`engine/src/core/dflash2.cpp:98-126`, `engine/src/core/dflash2.cpp:1044-1053`)

まとめ処理は入力を `CtxBatch::kB` = 64 行以下の塊に分け、位置を作り、tap rows を量子化し、FC projection と RMS/quantize を行う。必要な位置について K/V を作成して ring に記録し、終わりに stream を同期する。ring log が無効で、その塊が ring に必要な位置を含まない場合は、その塊の処理を飛ばす。まとめ処理に入らない場合は最大8行ずつ `record_context()` を実行する。 (`engine/src/core/dflash2.cpp:70-82`, `engine/src/core/dflash2.cpp:1052-1058`, `engine/src/core/dflash2.cpp:1082-1127`, `engine/src/core/dflash2.cpp:1129-1142`)

## ログと測定値

この環境変数の値を表示するログはない。まとめ用リソースの確保に失敗したときも、エラーを `err` に記録せず通常経路へ移る。まとめ処理中に CUDA/HIP runtime の同期・event 操作が失敗した場合は `dflash2: <runtime error>` が `err` に入り、例外が投げられた場合は例外文が `err` に入る。呼び出し元はこの失敗を伝播し、generate の一部経路では `strata generate: <error>` を stderr に出して終了コード1を返す。 (`engine/src/core/dflash2.cpp:118-123`, `engine/src/core/dflash2.cpp:1064-1068`, `engine/src/core/dflash2.cpp:1116-1122`, `engine/src/program/generate.cpp:24898-24904`)

`docs/SETTINGS.md` はこのスイッチを NVIDIA/AMD 向けの on/off 設定として掲載し、設定すると以前の挙動に戻ると説明している。調査した実装は unset を含む先頭文字 `'0'` 以外をまとめ処理 on とする。`docs/DETAILS.md` にはこの環境変数に関する個別の動作説明や測定値は見当たらない。 (`docs/SETTINGS.md:352-368`)

## 根拠

- `engine/src/core/dflash2.cpp:1044-1053` — 値判定、行数・profile・確保成功の条件。
- `engine/src/core/dflash2.cpp:70-126` — 64行バッチ構造と遅延確保、失敗時処理。
- `engine/src/core/dflash2.cpp:1082-1142` — まとめ処理と通常処理。
- `engine/include/strata/core/dflash2.hpp:37-42` — `kRows` が8であること。
- `engine/cmake/strata_gpu_engine.cmake:6-13` — CUDA/HIP に DFlash2 を含める build 条件。
- `engine/src/program/generate.cpp:13505-13534`, `engine/src/program/generate.cpp:20362-20367`, `engine/src/program/generate.cpp:24898-24904` — DFlash2 の context 呼び出しとエラー伝播。
- `docs/SETTINGS.md:352-368`, `docs/DETAILS.md:1208-1225` — 設定一覧との照合。DETAILS の該当範囲は別設定の説明で、この変数の記述ではない。
