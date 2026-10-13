# `STRATA_SSD_KEEPALIVE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・ドライバーの環境変数は対象外。

## 役割

PLE（n-gram テーブル）を SSD から直接読む `--ple-io direct` の経路で、行の読み取りがしばらく無いときに、テーブルの 4 KiB ページを 1 回読んで SSD を起こしたままにする時間（周期）を設定します。

目的は、行そのものの取得ではなく、ドライブのアイドル時の電力状態への遷移を防ぐことです。ソースの注釈では、一部の SSD は約 250 ms コマンドが無いと電力状態に入り、次の最初の読みが 50-150 ms 止まると説明されています（WD_BLACK SN7100、Windows 11。電源計画の NVMe idle timeout を変えても変わらなかった、と注釈に書かれています）。これはソースに記録された観測であり、こちらで再測定した事実ではありません。デコードでは行がすべて行キャッシュから出る数ラウンド後に読みが止まるため、その間に keep-alive 読みが周期ごとに走ります。

読み取りは `src/program/generate.cpp` の PLE 構築ブロック（`if (!o.ple_gguf.empty())`）の中にあり、エンジン起動時に一度だけ実行されます。値は `PleIoOptions::keepalive_ms` に入り、`PleTable::open` の後に `PleReader::set_keepalive()` へ渡されます。実装は `src/ngram/ple_reader.cpp`（SYCL 版は `sycl/src/ngram/ple_reader.cpp`）で、判定結果は `static` にキャッシュされず、reader の状態フィールド（`keep_us`）に保存されます。

Python サーバーはこの変数を読みません。サーバーはエンジン子プロセスへ `dict(os.environ)` を渡すので、親環境の値はエンジン側に届きます（`serve/server.py:2554-2564`）。

## 値と判定

`std::atof` を使った double 型の変換です。文字列全体が数値でなくても、先頭の数値部分だけを使い、後ろを無視します。空白は atof の前処理で飛ばされます。

| 状態 | 結果 |
|---|---|
| 未設定 | 100.0 ms（既定） |
| 空文字 | 100.0 ms（既定）。判定は `ka != nullptr && *ka` なので、空文字は設定済みでも既定になる |
| 正の数（例 `250`, `2.5`, `1e2`） | atof の値。小数 ms も受け付ける |
| 先頭が数値で後ろが文字（例 `50ms`） | 50.0 ms（後ろは無視） |
| 数値でない文字列（例 `abc`, `true`） | atof が 0.0 を返す → 無効 |
| `0` | 無効 |
| 負値（例 `-5`） | clamp により 0.0 → 無効 |
| 10000 を超える値 | clamp により 10000.0 ms |

範囲は `std::clamp(std::atof(ka), 0.0, 10000.0)`（`src/program/generate.cpp:3164`）。大文字小文字・文字列比較による ON/OFF 判定はありません。

関連するもう一方の値 `STRATA_SSD_KEEPALIVE_WINDOW`（最後の `issue()` からの秒数）は同じブロックで読まれ、既定 60.0、`std::clamp(std::atof(kw), 1.0, 86400.0)` です。この clamp の下限は 1.0 なので、`STRATA_SSD_KEEPALIVE_WINDOW=0` は無効ではなく 1.0 s になります（`src/program/generate.cpp:3165`）。

## 有効になる条件

値が有効でも、次の条件が揃わなければ keep-alive 読みは走りません。

- PLE テーブルが実際に使われている。`o.ple_gguf` が空だとこの環境変数は読まれません（`--no-ple` やテーブルなしの経路）。
- `PleIoOptions::mode == PleIo::Direct`。`--ple-io mmap` / `--ple-io ram` では `keepalive_ms` が 0 に固定されます（`src/program/generate.cpp:3166`）。
- I/O ワーカースレッドが有効であること。`--ple-sync-submit`（`o.ple_sync_submit`）は `io_thread = false` にし、同じ行で `keepalive_ms` を 0 にします。reader 側も `set_keepalive()` で `m.threaded` を要求します（`src/ngram/ple_reader.cpp:521`）。
- 少なくとも 1 回の `issue()` があること（`last_issue_us > 0`）。行が要求される前のアイドル状態では keep-alive は走らない。
- ウィンドウ内であること: `now - last_issue_us <= keep_window_us`。ウィンドウは最後の `issue()` からの経過時間であり、最後の読みからの時間ではありません。
- reader がエラー状態でないこと（`error` が空）。
- ワーカーがアイドルであること。キューに job が残っている、または in-flight / delayed が有る（`busy()`）間は keep-alive の判定自体が行われません（`src/ngram/ple_reader.cpp:303-308`）。
- 提出時に空きスロットがあること。

フォールバック: `--ple-io direct` の読み速度プローブ（`STRATA_PLE_PROBE` が未設定のとき）が 15000 rows/s 未満を出し、かつ `--ple-io` が明示指定でなかった場合、モードは mmap に切り替えられ `keepalive_ms = 0` になります（`src/program/generate.cpp:3186-3187`）。この場合、起動ログの keep-alive 行は出ません（モードが Direct でないため）。

一度 keep-alive 読みが失敗すると、そのプロセスでは無効になります。submit 失敗（`src/ngram/ple_reader.cpp:157-162`）でも completion の error（`src/ngram/ple_reader.cpp:209-214`）でも `keep_us = 0` になり、reader 自体は失敗しません。`set_keepalive()` は open 後に一度呼ばれるだけなので、無効になった後に環境変数を変えても復帰しません。

## 実行時の詳細

- 周期は「最後に出た読み（行読みでも keep-alive 読みでも）からの経過時間」で測られます。`keepalive_due(now)` は `last_read_us + keep_us` を返し、`keep_us` は ms × 1000 の µs です（`src/ngram/ple_reader.cpp:182-185`）。
- ワーカーはアイドル待機中に `keepalive_due` を見て、時刻が来ていれば job を 1 個キューに入れ、来ていなければ `wait_for`（最低 1000 µs）で寝ます（`src/ngram/ple_reader.cpp:303-308`）。
- 読む対象はテーブル内の 1 ページ（4096 B）で、毎回異なるページが選ばれます。xorshift64 の疑似乱数で `[table_offset/PAGE, (table_offset + n_rows*row_bytes)/PAGE)` の範囲から 1 ページを選びます。これはコントローラのバッファではなく実際に読ませるためです（`src/ngram/ple_reader.cpp:187-198`）。seed は open 時に `0x9E3779B97F4A7C15ull ^ now_us()`。
- keep-alive 読みは行キャッシュに入れられず、結果は捨てられます。統計上、`reads`・`bytes`・遅延リング（percentile）には入りません。`keepalive_reads` と `keepalive_us_max` だけに加算されます（`src/ngram/ple_reader.cpp:172-175,208-217`）。
- ウィンドウを過ぎた後は keep-alive は停止します。次の `issue()` で `last_issue_us` が更新され、ウィンドウ外だった場合は `rearm` が true になり、job が無くても（行がすべてキャッシュヒットで `has_jobs` が false でも）`cv_work.notify_one()` でワーカーを起こして keep-alive が再開します（`src/ngram/ple_reader.cpp:428-430,471-478`）。
- keep-alive 読みは I/O ワーカースレッド上に出ます。このスレッドは open 時に補助 CPU に pin されます（`src/ngram/ple_reader.cpp:367`）。

## 観測できる結果

起動時（PLE テーブルを開いた後）に stderr へ出ます。keep-alive が有効なとき:

```
strata generate: the SSD is kept awake while rows are read: one page of the table after 100 ms without a read, until 60 s after the last request (STRATA_SSD_KEEPALIVE=0 turns it off)
```

値を設定した場合はこの数値が変換結果の `%.0f` / `%.0f` として出ます（小数は丸めて表示）。Direct モードで無効になったとき（`0`、非数値、負値、または `--ple-sync-submit`）は別の行が出ます:

```
strata generate: SSD keep-alive off: the SSD may fall asleep between reads
```

mmap / ram モードではこの行も出ません。

`--stats` の終了時レポート（`PleTable::io_report()`）には、keep-alive 読みが 1 回以上あったときだけ末尾に追加されます:

```
, SSD kept awake by 12 reads (slowest 1.4 ms)
```

`reset_stats()` は keep-alive のカウンタも消します（`src/ngram/ple_reader.cpp:538-544`）。

## 文書と測定値の照合

`docs/DETAILS.md` にこの環境変数の記載はありません。SSD の n-gram テーブルをバッファを使わずに読む説明（`docs/DETAILS.md:1831-1833`）と、回転式ディスクに関する警告（`docs/DETAILS.md:1814`）はありますが、keep-alive の値・既定・測定はソースの注釈と起動ログからのみ確認できます。根拠となる測定（約 250 ms コマンドが無いと 50-150 ms の読み停止、WD_BLACK SN7100 / Windows 11）は `include/strata/ngram/ple_reader.hpp:75-80` と `src/program/generate.cpp:3157-3160` の注釈に書かれた条件であり、他の機種での効果はソースから確認できません。

リポジトリ内のテスト（`src/ngram/ple_reader_test.cpp:307-355`）は、周期どおりに読みが出る、ウィンドウ後は止まる、キャッシュヒットだけの `issue()` でも再開する、ワーカースレッド無しでは走らない、失敗で無効になる、`reset_stats()` でカウンタが消える、という挙動を確認しています。これは実装の根拠ではなく現行コードの裏付けとして扱いました。

SYCL 版は CUDA 版と同じ判定・同じログ文字列です（`sycl/src/program/generate.cpp:2983-2993,3042-3047`）。HIP ビルドは `src/program/generate.cpp` を使うため、判定は CUDA 版と同一です。

## 根拠

- 読み取り・変換・clamp・強制的な無効: `src/program/generate.cpp:3149-3167`
- 起動ログ: `src/program/generate.cpp:3216-3221`
- プローブによる mmap へのフォールバック時の無効: `src/program/generate.cpp:3174-3199`
- `PleIoOptions` の既定（`keepalive_ms = 0`, `keepalive_window_s = 60`）: `include/strata/kernels/ngram.hpp:149-164`
- `set_keepalive()` の呼び出し（Direct モードのみ）: `src/kernels/ngram.cpp:314-327`
- `set_keepalive()` の `threaded` 条件とウィンドウ: `src/ngram/ple_reader.cpp:517-525`
- 状態フィールド: `src/ngram/ple_reader.cpp:117-122`
- 期限判定: `src/ngram/ple_reader.cpp:180-185`
- ページ選択とキュー入れ: `src/ngram/ple_reader.cpp:187-198`
- 統計の区別と失敗時の無効: `src/ngram/ple_reader.cpp:148-178,200-218`
- ワーカーのアイドル判定と待機: `src/ngram/ple_reader.cpp:299-327`
- ウィンドウ過ぎ後の再開始: `src/ngram/ple_reader.cpp:428-430,471-478`
- 統計の出力: `src/kernels/ngram.cpp:554-568`, `src/program/generate.cpp:13349`
- 設計意図の注釈: `include/strata/ngram/ple_reader.hpp:75-81`
