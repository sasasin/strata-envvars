# `STRATA_KEEP_IO_PRIORITY`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Windows で Strata プロセスが起動元から継承した I/O 優先度を保つための opt-out です。既定ではプロセスの I/O 優先度を調べ、Normal より低ければ Normal に戻します。`STRATA_KEEP_IO_PRIORITY` が `1` で始まる場合は、この補正を行いません。Strata が設定するのはプロセス自身の I/O 優先度であり、モデル読み込みなどの優先度を個別に指定する設定ではありません（`src/platform/io_priority.cpp:18-22,29-43`）。

## 値と判定

文字列全体や数値としての妥当性は検査せず、`std::getenv()` の結果が存在し、先頭文字が `'1'` かだけを比較します。

| 状態 | Windows での処理 |
|---|---|
| 未設定 | I/O 優先度を通常化する処理を続ける |
| 空文字 | 先頭文字は `'1'` でないため、通常化する処理を続ける |
| `1` で始まる値（例: `1`, `10`, `1anything`） | 直ちに `-1` を返し、優先度の照会・変更を行わない |
| その他の設定値（例: `0`, `true`, `false`, ` 1`） | I/O 優先度を通常化する処理を続ける |

したがって `0` だけが無効値という判定ではありません。空白、大文字小文字、後続文字の解釈や値の範囲チェックもありません（`src/platform/io_priority.cpp:18-22`）。

## 有効になる条件

- 環境変数を読む分岐は `_WIN32` のときだけコンパイルされます。Windows 以外では引数のログを未使用として扱い、常に `-1` を返します（`src/platform/io_priority.cpp:18-20,44-47`）。
- `strata` の生成エンジンは `main()` の冒頭で呼び出します（`src/program/generate.cpp:3180-3189`）。`strata-dsv41` もビルドされている場合、その `main()` 冒頭で呼び出します（`CMakeLists.txt:934-945`, `src/dsv41/ds4_main.cpp:2487-2489`）。
- CLI 引数、モデル状態、GPU backend、他の環境変数による上書き条件はこの関数にはありません。`strata-dsv41` は `STRATA_BUILD_DSV41` が有効で、かつ `STRATA_HIP_GFX906` でない場合にビルドされます（`CMakeLists.txt:934-945`）。

## 実行時の詳細

環境変数は `restore_normal_io_priority()` の呼び出しごとに読み取られ、static cache はありません。通常の `strata` と `strata-dsv41` は起動時に一度呼び出します。その時点で値が `1` から始まる場合、戻り値 `-1` は呼び出し元で使われず、ログも出ません（`src/platform/io_priority.cpp:18-22`, `src/program/generate.cpp:3189`, `src/dsv41/ds4_main.cpp:2489`）。

Windows で補正を続ける場合、実装は `ntdll.dll` と `NtQueryInformationProcess` / `NtSetInformationProcess` を取得し、情報クラス 33 の値を照会します。DLL や関数を取得できない場合、照会が失敗した場合、または返却サイズが `ULONG` に満たない場合は `-1` を返し、警告は出しません。取得値が 2 以上なら変更せず、その値を返します。2 未満なら 2（Normal）への設定を試みます（`src/platform/io_priority.cpp:22-34`）。

設定に失敗すると、`log` が非 null の場合に stderr（通常呼び出しの既定値）へ次の警告を書き、変更前の値を返します。設定に成功すると、同じく `log` が非 null の場合に補正した旨を stderr に出し、変更前の値を返します。どちらの行も `restore_normal_io_priority()` の既定引数は `stderr` です（`include/strata/platform/io_priority.hpp:15-19`, `src/platform/io_priority.cpp:34-43`）。呼び出し側は戻り値を利用していません（`src/program/generate.cpp:3189`, `src/dsv41/ds4_main.cpp:2489`）。

## 根拠

- 環境変数の唯一の本番読み取り箇所と Windows 限定分岐: `src/platform/io_priority.cpp:18-22,44-47`。
- 優先度の照会・通常化・失敗／成功ログ: `src/platform/io_priority.cpp:22-43`。
- 通常エンジンの起動時呼び出し: `src/program/generate.cpp:3180-3189`。
- DSV41 エンジンの任意ビルド条件と起動時呼び出し: `CMakeLists.txt:934-945`, `src/dsv41/ds4_main.cpp:2487-2489`。
- 候補名の他の参照はヘッダーの説明と Windows 専用テストです（`include/strata/platform/io_priority.hpp:1-19`, `tests/platform/io_priority_test.cpp:22-42`）。テストは環境変数を `1` に設定した場合に低い値が維持されることを記述していますが、本番挙動の根拠は上記実装です。
