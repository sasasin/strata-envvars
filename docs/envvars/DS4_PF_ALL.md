# `DS4_PF_ALL`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DSV41 のファイル mmap 経由の expert 読み出しで、Windows が次に使うメモリ範囲を prefetch する際、常駐済み範囲も含めるかを制御します。Windows では既定で常駐済みと判定された範囲を除外し、この変数を非 0 相当で設定すると全範囲を prefetch します。Linux ではこの変数を読み取らず、常に全範囲を prefetch する経路です。

## 値と判定

Windows の `os::prefetch_cold()` が初めて呼ばれたとき、関数内の `static const bool` 初期化で `getenv("DS4_PF_ALL")` を一度評価します。値は文字列比較ではなく `atoi(v) != 0` で判定します。

| 状態 | Windows での判定 | 動作 |
|---|---|---|
| 未設定 | false | 各範囲を常駐判定し、常駐していない範囲だけ prefetch |
| 空文字 | false（`atoi` は 0） | 同上 |
| `0` または `0abc` | false | 同上 |
| `1`、`-1`、`2tail` など、`atoi` の結果が非 0 | true | 常駐判定をせず、全範囲を prefetch |
| `abc` など、`atoi` の結果が 0 | false | 常駐していない範囲だけ prefetch |

`atoi` が先頭の空白や符号付き整数を変換し、整数の後ろの文字を検査しない規則に従います。数値変換のオーバーフロー時の結果は C ライブラリの `atoi` に委ねられており、コードは別途検証しません。Linux では `#if defined(_WIN32)` の外側の分岐により変数を読みません。

## 有効になる条件

- 値の判定と resident 範囲の除外は Windows ビルドでのみ適用されます。
- 対象は DSV41 の prefetch 要求です。`src/CMakeLists.txt:809` は `strata-dsv41` に `src/dsv41/ds4_model.cu` を含めています。
- `prefetch_cold()` の呼び出し元は、CPU lane が mmap された expert 重みを使う前の要求、lookahead 用 prefetch thread の要求、そして `DS4_IQ_PF_COLD` の分岐からの要求です。
- `DS4_IQ_PF_COLD` が未設定、または `atoi` 結果が 0 のとき、IQ expert の処理は直接 `os::prefetch()` を使うため、そこでは `DS4_PF_ALL` の resident 判定は通りません。`DS4_IQ_PF_COLD` が設定されて `atoi` 結果が非 0 の場合は `os::prefetch_cold()` を呼び、Windows では本変数の判定が適用されます。
- `prefetch_cold()` は呼び出し時点で収集された範囲だけを対象にします。CPU lane の同期要求では `store` がなく、expert が RAM tier にない場合に各 expert の3行列が候補になります。

## 実行時の詳細

Windows で本変数が未設定または `atoi` 結果 0 の場合、各範囲について `resident_sampled()` が最大8ページをサンプルし、すべてが常駐と判定された範囲を候補から外してから `prefetch()` を呼びます。非 0 の場合はサンプリングを省き、渡された全範囲を `prefetch()` に渡します。判定結果は関数内 static に保存されるため、最初の `prefetch_cold()` 呼び出し後にプロセス環境を変更しても反映されません。

Windows の `prefetch()` は範囲を `WIN32_MEMORY_RANGE_ENTRY` 配列にして `PrefetchVirtualMemory()` に渡します。その戻り値は確認されず、失敗時のログや別の処理はこのコードにはありません。Linux では各範囲をページ境界に合わせて `madvise(..., MADV_WILLNEED)` に渡します。本変数によるログ出力はありません。

`docs/DETAILS.md` に `DS4_PF_ALL` の説明は見つかりませんでした。上記の挙動はソース上の分岐に基づきます。

## 根拠

- `src/dsv41/ds4_os.hpp:307-325`: `prefetch()` が Windows で `PrefetchVirtualMemory()`、その他で `madvise(MADV_WILLNEED)` を呼ぶ箇所。
- `src/dsv41/ds4_os.hpp:346-370`: resident 判定の実装。Windows は最大16サンプルを確認し、既定の `samples=8` では8ページを確認。
- `src/dsv41/ds4_os.hpp:372-389`: `DS4_PF_ALL` の読み取り、`atoi` 判定、Windows と非 Windows の分岐。
- `src/dsv41/ds4_model.cu:5649-5657`: CPU lane の MXFP4 expert 範囲を集めて `prefetch_cold()` を呼ぶ箇所。
- `src/dsv41/ds4_model.cu:5743-5752`: `DS4_IQ_PF_COLD` の判定と `prefetch()` / `prefetch_cold()` の選択。
- `src/dsv41/ds4_model.cu:6380-6391`: lookahead の prefetch thread から `prefetch_cold()` を呼ぶ箇所。
- `src/CMakeLists.txt:809`: `strata-dsv41` ターゲットのソース構成。
