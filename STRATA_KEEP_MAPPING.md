# `STRATA_KEEP_MAPPING`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--mmap-experts` のファイルソースで unbuffered I/O が選ばれたとき、既定ではメモリマップ済みの expert ファイル／GGUF shard の view を閉じる処理を試みます。`STRATA_KEEP_MAPPING` を設定するとその処理をスキップし、mapped view を保持します。コードコメントは、Windows の NTFS で同一ファイルへの unbuffered read が mapping の存在中に直列化されるための A/B 用スイッチと説明しています。環境変数による通常利用者向け設定というより、`generate` のファイル tier に対する診断・比較フックです。

## 値と判定

値の parse はありません。`std::getenv("STRATA_KEEP_MAPPING") != nullptr` だけで設定有無を判定します。

| 状態 | 動作 |
|---|---|
| 未設定 | 他の条件も満たす場合、`drop_mapping()` を呼ぶ |
| 任意の値 | `drop_mapping()` を呼ばず mapping を保持する。`1` 以外、`0`、空文字も同じ |

空文字は「設定済み」なので処理を抑止します。大文字小文字、数値変換、範囲制限、別の設定値との優先順位はありません。参照: `src/program/generate.cpp:6816-6822`。

## 有効になる条件

分岐には、`srcp == &src` と `src.unbuffered()` も必要です。したがって、`--mmap-experts` を使わない経路（resident arena 等）、通常の mmap/file-cache 読み込み、および別の source に置き換わった経路では、この変数は分岐に影響しません。`srcp = &src` は `--mmap-experts` の `FileExpertSource` を開いた場合に設定されます（`src/program/generate.cpp:4620-4637,4699-4700`）。

`src.unbuffered()` は direct file handle が開かれていることを表します。`--mmap-experts` で resident RAM budget が指定された場合に unbuffered file tier を選ぶ処理が走ります。Windows は `experts_unbuffered()` の判定、Linux は `STRATA_UNBUFFERED_LOAD` または利用可能メモリと file-cache 判定によります。budget がない場合はこのモードで unbuffered read を選ばず、明示された `STRATA_UNBUFFERED_LOAD` も無視する旨をログに出します（`src/program/generate.cpp:4638-4653`; `src/core/expert_source.cpp:495-530`）。

## 実行時の詳細

分岐は `generate` の初期化中に通常の `getenv` として評価され、static cache されません。該当箇所に到達する時点の環境値が使われます。条件を満たして変数が未設定なら `src.drop_mapping(why)` を呼び、stderr に `strata generate: the mapped view of the experts is closed (...)` または `... stays open (...)` を出します。設定されていればこのログも出ません。参照: `src/program/generate.cpp:6816-6822`。

`drop_mapping()` の実装は platform で異なります。Windows では unbuffered handle があり、source が GGUF shard または通常の mapping として開かれている場合、view と対応する file/mapping handle を閉じ、以後 RAM/VRAM にない expert を unbuffered read する状態にします。unmap に失敗した場合は false を返し、mapping を保持した旨の理由がログに出ます（`src/core/expert_source.cpp:1686-1719`）。Linux では通常は何も閉じず `not Windows` を理由に false を返します。`STRATA_TEST_UNMAP_GGUF` が設定され、空でなく `atoi` が 0 以外で、GGUF shard の source であり、unbuffered handle もある場合にだけ、テスト用の unmap 経路を進めます（同 `:1720-1726`）。つまり `STRATA_KEEP_MAPPING` unset だけで Linux の mapping が閉じるわけではありません。

保持される mapping は file tier の fallback として残ります。対象の expert 読み取りが direct read 経路で失敗した場合に mapping から読む fallback があるため、mapping を閉じる処理を抑止するかどうかは、その fallback が利用できる状態にも関係します（`src/core/expert_source.cpp:1217-1218,2529-2542`）。この環境変数自体による値の設定、警告、ログはありません。

## 根拠

- `src/program/generate.cpp:4620-4637,4699-4700` — `--mmap-experts` の source 設定。
- `src/program/generate.cpp:4638-4653` — resident budget と unbuffered file tier の選択。
- `src/program/generate.cpp:6816-6828` — 環境変数の有無による mapping close の呼び出しとログ。
- `src/core/expert_source.cpp:495-530` — Windows/Linux の unbuffered 判定。
- `src/core/expert_source.cpp:1686-1726` — `drop_mapping()` の Windows/Linux 実装差。
- `src/core/expert_source.cpp:1217-1218,2529-2542` — unmap 後と mapping からの blob 取得条件。
- `docs/DETAILS.md:225-232` — Linux の file-tier mmap と I/O prefetch の説明。`STRATA_KEEP_MAPPING` の説明はなく、この変数の挙動は上記コードから確認した。
