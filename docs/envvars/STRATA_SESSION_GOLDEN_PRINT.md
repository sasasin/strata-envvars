# `STRATA_SESSION_GOLDEN_PRINT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

会話セッションファイルの CPU 専用テスト `conversation_file_test` で、固定サンプルから書き出したファイル全体のサイズと `session_hash64` を標準出力へ表示する診断用環境変数である。通常の Strata 実行ファイルやサーバーのセッション保存処理を制御する環境変数ではない。

## 値と判定

| 状態 | 動作 |
| --- | --- |
| 未設定 | サイズとハッシュを表示しない。 |
| 任意の値が設定済み | 値の内容を問わず表示する。空文字も設定済みとして扱う。 |

実装は `std::getenv("STRATA_SESSION_GOLDEN_PRINT")` の null 判定だけを行い、文字列比較や数値変換はしない。したがって `0`、`false`、空文字も表示を有効にする。表示後も、固定サイズ `17878535` と固定ハッシュ `0x70f812b350360d09` の両方を満たすか確認するテストは常に実行され、環境変数によって検査が省略・変更されることはない。

## 有効になる条件

この参照は `src/core/conversation_file_test.cpp` のみで、CMake の `STRATA_BUILD_CONVERSATION_TESTS` オプションが有効なときに `conversation_file_test` 実行ファイルがビルド・登録される。オプションの既定値は `OFF`。通常の Strata 本体や `--serve` の実行経路ではこの変数を読み取らない。

## 実行時の詳細

テスト実行中、固定データを書き出した `good.bin` を読み直した直後にファイル全体のハッシュを計算し、その時点で環境変数を一度読み取る。設定されていれば stdout に `golden size %zu hash %016llx\n` の形式で表示する。その後、固定サンプルのサイズとハッシュの一致を検査するため、値の有無に関係なく不一致なら `check` が stderr に `FAIL: golden: the fixed sample's file bytes are unchanged` を出して終了コード 1 で終了する。成功時はテスト末尾で `conversation_file_test: %d checks passed` を表示する。

これはテスト実行時に一度だけ参照される。テストの実行中にプロセス環境を変更して再評価する処理はない。子プロセスへの設定転送もこのテストにはない。

## 文書との照合

`docs/DETAILS.md` はセッションファイルの保存・復元 API と運用時の動作を説明しているが、この診断用変数については記載していない。ソース上も本変数はテスト内の表示だけに使われ、セッションファイル形式や保存・復元動作を変えない。

## 根拠

- `CMakeLists.txt:112-131` — `STRATA_BUILD_CONVERSATION_TESTS` は既定 `OFF`。有効時に `conversation_file_test` を登録する。
- `src/core/conversation_file_test.cpp:96-98` — 固定サンプルの期待サイズ・ハッシュ。
- `src/core/conversation_file_test.cpp:153-182` — テストの固定ファイル生成、全体ハッシュ計算、環境変数の null 判定による表示、および常時実行される golden 検査。
- `src/core/conversation_file_test.cpp:39-42, 772-774` — 失敗時の stderr と終了、成功時の最終 stdout。
- `docs/DETAILS.md:1276-1294` — 運用時のセッションファイル API と engine プロトコル。`STRATA_SESSION_GOLDEN_PRINT` への言及はない。
