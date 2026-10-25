# `STRATA_IO_PF_THREADS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux の mapped file tier I/O prefetch が作る I/O ワーカー数を指定します。この変数だけでは prefetch は有効になりません。`--mmap-experts` 経路で `STRATA_IO_PREFETCH` が `atoi` で 0 以外になるときにだけ読み取られ、`FileExpertSource` に渡されます。設定数のワーカーは expert blob の demand read と、router が予測した後続 layer の read-ahead を処理します。後続 layer の予測深度は別設定の `STRATA_IO_PREFETCH_DEPTH` が扱います。

## 値と判定

`std::atoi` で文字列を整数変換し、結果が正ならその値を使います。未設定時は `0` を渡し、FileExpertSource 側の既定値 8 が適用されます。設定済みでも変換結果が 0 以下なら同じく 8 です。

| 環境変数の値 | `atoi` の結果 | ワーカー数 |
|---|---:|---:|
| 未設定 | 呼び出し側が `0` を渡す | 8 |
| `8` | 8 | 8 |
| `3workers` | 3 | 3 |
| `  +4tail` | 4 | 4 |
| 空文字、`0`、`abc` | 0 | 8 |
| `-2` | -2 | 8 |

文字列全体の数値検証はなく、先頭から整数として変換できる部分が使われます。したがって `3workers` は 3 です。正の上限値や clamp は実装にありません。`atoi` で表現できない範囲の入力について、コードは独自のエラー処理を設けていません。

## 有効になる条件

- `strata generate` が `--mmap-experts` の FileExpertSource 経路を使うこと。
- `STRATA_IO_PREFETCH` が設定され、`atoi(value) != 0` となること。この条件を満たさなければ `STRATA_IO_PF_THREADS` は読み取られません。
- Linux ビルドで、FileExpertSource に有効な mapped base と file paths があり、unbuffered 用の `direct_` が空であること。
- ファイルごとの読み取り descriptor を開けること。descriptor の open に失敗すると prefetch 設定は有効にならず、ワーカーも起動しません。

Linux 以外では `set_io_prefetch` は `on` とスレッド数を無視し、I/O prefetch を有効にしません。unbuffered reads の経路でも有効化されません。呼び出し側はこの場合 stderr に `strata generate: STRATA_IO_PREFETCH=1 is not available here (Linux mapped file tier only, not with unbuffered reads); the file tier reads as before` を出します。この文言は descriptor open 失敗時にも同じく使われ、失敗理由を区別しません。

## 実行時の詳細

設定は `strata generate` の FileExpertSource 準備時に一度読み取られ、`set_io_prefetch(true, ...)` に渡されます。関数は既存の I/O worker を止めてから Linux 条件を確認し、I/O 用 descriptor を開き、渡された値が正ならそれを、そうでなければ 8 を `io_threads_` に保存します。その数だけ worker thread を起動します。この設定値をリクエストごとに読み直す処理はありません。

ワーカーは I/O queue から layer/expert の仕事を取り出します。現在の layer の uncached expert reads や router により予測された後続 layer の expert を読み、設定に応じて page cache を満たすか staging buffer に置きます。予測が実際に行われるか、どの layer を読むかは prefetch/lookahead の別条件にも依存します。設定数は queue 容量や予測深度を変更しません。

有効時の起動ログは `file tier io prefetch ON ... read by %s I/O threads (STRATA_IO_PF_THREADS, default 8)` です。ここで `%s` に環境変数の生文字列を出すため、たとえば `3workers` を指定するとログには `3workers` と表示されますが、実際のワーカー数は `atoi` の結果である 3 です。未設定時は `8` と表示されます。prefetch が有効にならない場合、このスレッド数ログは出ません。

## 根拠

- `src/program/generate.cpp:4667-4678` — `STRATA_IO_PREFETCH` の有効判定、`STRATA_IO_PF_THREADS` の取得と `atoi`、設定成否に応じたログ。
- `src/core/expert_source.cpp:636-669` — Linux 条件、file descriptor の準備、正値または既定 8 の選択、worker 数分の thread 起動。非 Linux の no-op も同箇所。
- `src/core/expert_source.cpp:690-771` — worker queue の処理と読み取り。
- `src/core/expert_source.cpp:1426-1483, 2136-2139` — demand と先読みの仕事が queue に渡される経路。
- `src/program/generate.cpp:5510-5518` — `STRATA_IO_PREFETCH_DEPTH` は別変数として lookahead depth を設定。
- `docs/DETAILS.md:225-232` — Linux file-tier I/O path の概要と既定 8 の説明。測定表は I/O prefetch 条件の比較であり、`STRATA_IO_PF_THREADS` の値ごとの性能差は示していません。
