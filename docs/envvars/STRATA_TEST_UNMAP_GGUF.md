# `STRATA_TEST_UNMAP_GGUF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Linux の `FileExpertSource` がネイティブモデルの GGUF shard を mmap している状態から、読み取り用 file descriptor を残さずに GGUF view を `munmap` するテスト用スイッチ。Windows の unmap 経路を Linux 上で通すためのもので、設定しても RAM/VRAM の expert 配置や unbuffered 読み取りを有効にはしない。unbuffered 読み取りがすでに使われている場合に、以後の expert 読み出しが mmap view に依存しない状態を作る。読み取りと処理は `FileExpertSource::drop_mapping` にある（`engine/src/core/expert_source.cpp:2910-2960`）。

## 値と判定

非 Windows 分岐で `std::getenv` した後、空文字を除外し、`std::atoi` の結果が 0 かどうかで判定する。文字列全体の検証はしない。`atoi` は先頭の空白と符号を受け付け、10 進数字の先頭部分を変換するため、`1`, `2`, `-1`, `+1`, ` 1`, `1junk` は非ゼロになり有効、`0`, `0junk`, `true`, `false`, 空文字、数字で始まらない文字列は無効。大文字小文字は結果に影響しない。整数変換の範囲外入力の結果はコードで保証されていない（`engine/src/core/expert_source.cpp:2944-2949`）。

| ビルド / 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Windows の `drop_mapping` | 該当なし | 該当なし。この分岐では変数を読まず、Windows の unmap 処理を行う | 該当なし |
| Linux の `drop_mapping` | 無効 | `atoi(value) != 0` となる非空文字列（例: `1`, `-1`, `1junk`） | `atoi(value) == 0` または空文字（例: `0`, `0anything`, `true`） |

## 有効になる条件

- `strata generate` が `FileExpertSource` を使うこと。`--mmap-experts`、`--ssd-experts`、または resident budget を使う経路などで file source が選ばれる。ネイティブ pack で `experts.bin` がなく、ネイティブ GGUF を開くと `role_ptr_` が設定される（`engine/src/program/generate.cpp:4218-4253,8621-8647`; `engine/src/core/expert_source.cpp:1570-1579,1806-1813,1875-1882`）。
- Linux で file tier の unbuffered 読み取りが有効になり `direct_` が空でないこと。通常は `--resident-budget-gib` 等で `resident_budget > 0` のとき `set_unbuffered` が file tier の判断を行い、`--ssd-experts` は強制的に unbuffered を要求する。`STRATA_UNBUFFERED_LOAD` が空でない値なら、その先頭文字が `0` かどうかでこの判断を上書きし、`0` で始まれば unbuffered にならない。`--mmap-experts` だけで unbuffered が有効でなければ、この変数は view を閉じない（`engine/src/program/generate.cpp:8654-8658`; `engine/src/core/expert_source.cpp:959-972,2766-2817,2842-2858,2947-2949`）。
- 起動処理の後段で `srcp == &src`, `src.unbuffered()`, `!src.is_unmapped()` が成立し、`STRATA_KEEP_MAPPING` が未設定であること。`STRATA_KEEP_MAPPING` が空文字でも `getenv(...) == nullptr` 判定を通らないため、設定されていればこの呼び出しは抑止される（`engine/src/program/generate.cpp:12259-12265`）。
- `experts.bin` を読む経路では `role_ptr_` が空で、この変数による unmap は実行されない。Windows では `drop_mapping` の別実装に入り、変数値にかかわらず unbuffered file 読み取りがある場合に view を閉じる（`engine/src/core/expert_source.cpp:2910-2949`）。
- この変数単独で unbuffered file 読み取りを開始することはない。CLI 引数や他の設定によって `direct_` が用意されなければ、`the reads are not unbuffered` の理由で view は維持される（同 `2947-2950`）。

## 実行時の詳細

`FileExpertSource::open_gguf` は GGUF shard を mmap し、expert の各 role の位置を `role_ptr_` に保持する。後で unbuffered 読み取りが成立し、上記の `generate` 呼び出し条件に入ると `drop_mapping` が環境変数をその時点で読み、`atoi` 判定を行う。値は static cache されず、この関数呼び出し時のプロセス環境を参照する。実行中に値を変えても、unmap 後に同じ処理が再評価されるわけではない（`engine/src/core/expert_source.cpp:1806-1882,2944-2960`; `engine/src/program/generate.cpp:12259-12265`）。

有効値かつ `role_ptr_` と `direct_` がある場合、各 shard に対して `munmap` が成功したものを closed とし、対応する fd を `close` して `-1` にする。全 shard の処理後に `unmapped_` を立てる。以後 `copy_from_files` は direct read を試み、GGUF view を使う fallback は `unmapped_` を見て失敗を返すため、expert bytes の供給は unbuffered read に依存する（`engine/src/core/expert_source.cpp:2947-2960,1886-1934`）。この変数は model output や expert 選択を変える処理を含まない。

unset / 空文字 / `atoi` が 0 / GGUF でない場合は `not Windows` を理由に false を返す。`direct_` が空なら `the reads are not unbuffered` で false、すでに閉じていれば `already closed` で true。`munmap` が失敗すると `munmap failed` で false を返し、呼び出し元は失敗をログに記録する。関数自体は起動を中止させない（`engine/src/core/expert_source.cpp:2947-2960`; `engine/src/program/generate.cpp:12261-12265`）。

## ログと測定値

呼び出し元は stderr に `strata generate: the mapped view of the experts is closed (%s)` または `strata generate: the mapped view of the experts stays open (%s)` を出す。unmap に成功した場合の理由文字列は、たとえば `2 GGUF shard(s) unmapped (STRATA_TEST_UNMAP_GGUF); every expert outside RAM and VRAM is read unbuffered`（shard 数に応じて数値が変わる）。無効値や GGUF 以外では括弧内は `not Windows`、direct read がなければ `the reads are not unbuffered`、`munmap` 失敗時は `munmap failed` となる（`engine/src/core/expert_source.cpp:2947-2960`; `engine/src/program/generate.cpp:12261-12265`）。この変数についての測定値は記載されていない。

## 根拠

- 値判定、shard の unmap、理由文字列: `engine/src/core/expert_source.cpp:2910-2960`
- GGUF mmap と role pointer: `engine/src/core/expert_source.cpp:1806-1882`
- file source / unbuffered 経路と CLI 条件: `engine/src/program/generate.cpp:4218-4253,8621-8658`
- unmap の呼び出し条件と stderr: `engine/src/program/generate.cpp:12259-12265`
- unmap 後の direct read と mmap fallback の抑止: `engine/src/core/expert_source.cpp:1886-1934`
