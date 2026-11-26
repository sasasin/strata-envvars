# `STRATA_IO_PF_THREADS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux の file tier で I/O prefetch が有効なときに、`FileExpertSource` が起動する I/O worker thread 数を指定する。worker は expert blob の `pread` を使った先読みや、現在の層で必要な未キャッシュ blob の読み込みを担当する。正の数値を指定するとその数だけ worker を作り、それ以外は 8 個にする。通常の生成結果やスレッド数以外の設定をこの変数が直接変更する処理はない（`engine/src/core/expert_source.cpp:1261-1310`）。

## 値と判定

呼び出し元は `std::getenv` で値を得て、未設定なら `0`、設定済みなら `std::atoi` の結果を `set_io_prefetch` に渡す。`set_io_prefetch` は `threads > 0` の場合だけその整数を採用し、それ以外は 8 にする。従って未設定・空文字・`0`・`0anything`・`true`・`-3` はいずれも 8 worker、`1` は 1 worker、`12tail` は 12 worker になる。`atoi` は先頭の空白と符号に続く十進数字列を変換し、数字の後ろは検査しない。正の値に上限 clamp はない。整数型で表せない入力の結果は C ライブラリの `atoi` の範囲外変換に依存するため、ここでは有効値として扱わない（`engine/src/program/generate.cpp:8701-8703,10364-10367`; `engine/src/core/expert_source.cpp:1282-1283`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux で I/O prefetch が有効 | 8 worker | `atoi` が正となる整数（例: `1`, `8`, `12tail`） | `atoi` が 0 以下（例: 空文字, `0`, `0anything`, `true`, `-2`）は 8 worker |
| I/O prefetch が無効、または Linux 以外 | この変数は読まれず影響しない | 該当なし | 該当なし |

## 有効になる条件

- `generate` / `serve` の生成経路で file-backed `FileExpertSource` が使われること。通常は `--mmap-experts`（およびそれを有効にする関連 file-tier モード）で、resident arena を使う経路ではこの設定を利用しない（`engine/src/program/generate.cpp:8621-8628,8688-8703`）。
- I/O prefetch 自体が有効なこと。Linux では `STRATA_IO_PREFETCH` が未設定または空文字なら `src.linux_io_defaults()` に従う。値が非空なら `atoi` が非ゼロのとき有効で、`0` などは Linux の既定有効化も抑止する。既定有効化は GGUF をその場で読む場合、または experts.bin のページ cache に十分な余裕がある場合に適用される（`engine/src/program/generate.cpp:8693-8703`; `engine/src/core/expert_source.hpp:1081-1093`）。
- `FileExpertSource::set_io_prefetch` は Linux のみ worker を起動する。非 Linux では引数を使わず、prefetch の状態も有効にしない（`engine/src/core/expert_source.cpp:1264-1266,1309-1312`）。
- file tier が unbuffered 読み込み中なら `set_io_prefetch` は有効化を中止する。ファイル descriptor を開けない場合も同様に戻る。明示的に `STRATA_IO_PREFETCH` を要求していた場合、呼び出し元は「`STRATA_IO_PREFETCH=1 is not available here...`」を stderr に出す（`engine/src/core/expert_source.cpp:1264-1277`; `engine/src/program/generate.cpp:8722-8724`）。
- file tier idle policy が有効で、GPU cache が全 expert を保持している間、既定動作で開始した prefetch は一時停止される。`STRATA_IO_PREFETCH` で明示的に有効にした場合はこの既定停止の対象外。後で cache から expert が外れたとき、停止していた既定 prefetch を再開し、その時点でこの変数を再読する。`STRATA_FILE_TIER_IDLE=0` はこの停止・再開ポリシーを無効化する（`engine/src/program/generate.cpp:10251-10285,10343-10377`）。

## 実行時の詳細

初回の値読み取りは file tier の起動時で、関数内 static cache はない。`set_io_prefetch` は既存 worker を停止してから設定を適用し、Linux で必要な file descriptor を開いた後、`threads > 0 ? threads : 8` を worker 数に設定してその数の thread を起動する。従って正の値はスレッドプールの大きさを直接変える（`engine/src/program/generate.cpp:8701-8704`; `engine/src/core/expert_source.cpp:1261-1310`）。

serve の file tier idle policy が既定 prefetch を停止した後に再開するときは、`STRATA_IO_PF_THREADS` を再び `getenv` する。環境値をプロセス実行中に外部から変更した場合、その変更が反映される機会はこの停止後の再開に限られ、通常は起動時の値が使われる。再開判定は GEN / GENI request の開始時に行われる。停止・再開判定の呼び出しは serve request 経路にあり、通常の単発 generate は初期化時に読み取る（`engine/src/program/generate.cpp:10343-10377,18808-18812`）。子プロセスへの転送はこのコードにない。

worker 数は実際の読み取り・先読みの並列度に影響する。I/O prefetch は層の未キャッシュ expert や router lookahead が予測した次層の expert を whole-blob `pread` で扱い、先読み worker として使われる（`engine/src/core/expert_source.hpp:1012-1022`; `engine/src/core/expert_source.cpp:2451-2475,3487-3490`）。

## ログと測定値

初期化ログは有効時に「`... read by %s I/O threads (STRATA_IO_PF_THREADS, default 8)`」または Linux 既定動作の説明を stderr に出す。ここで `%s` には設定値の生文字列が入り、未設定なら `8`。そのため `0` や空文字を指定して内部で 8 worker に fallback した場合、ログ上の表示は実際の worker 数と一致しないことがある（`engine/src/program/generate.cpp:8705-8718`）。再開時は thread 数の設定と worker 起動を行うが、この変数の値を表示する専用ログはない（`engine/src/program/generate.cpp:10364-10368`）。

この変数のスレッド数を比較した Strata の測定値は、調査対象ソースと関連する `docs/DETAILS.md` に記載されていないため記載しない。`DETAILS.md` は既定 8 を示すにとどまる（`docs/DETAILS.md:302-310`）。

## 根拠

- 読み取り、既定 I/O prefetch 判定、初期化ログ: `engine/src/program/generate.cpp:8688-8724`
- serve 中の既定 prefetch 停止・再開と再読: `engine/src/program/generate.cpp:10251-10285,10341-10377,18808-18812`
- 値を thread 数へ変換し worker を起動する処理、Linux 限定: `engine/src/core/expert_source.cpp:1261-1312`
- worker 数の役割と Linux default 条件: `engine/src/core/expert_source.hpp:1012-1022,1081-1093`
