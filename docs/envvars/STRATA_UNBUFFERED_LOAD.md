# `STRATA_UNBUFFERED_LOAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

expert ファイルを読むとき、OS のファイルキャッシュを経由しない読み取りを選ぶかどうかを指定する。Windows の direct read と Linux の `O_DIRECT` を使う `FileExpertSource` の file tier、および Windows の resident expert arena 初回読み込みで判定に使われる。ファイルキャッシュを使うかという I/O 経路の選択であり、モデルや expert の選択結果は変更しない。後述のとおり、arena 初回読み込みの Linux/SYCL 経路では値が `true` でも実読み込みは buffered fallback になる。`engine/src/core/expert_source.cpp:963-972,2842-2858`、`engine/src/core/pinned.cu:1433-1439,1358-1365`、SYCL 側 `engine/sycl/src/core/expert_source.cpp:395-402,1094-1105`、`engine/sycl/src/core/pinned.dp.cpp:608-615,683-689`。

## 値と判定

読み取りは `getenv` で、未設定または空文字列なら自動判定へ進む。空でない値は文字列全体を parse せず、先頭 1 文字だけを検査する。先頭が `0` なら false、それ以外なら true。空白除去、大文字小文字変換、数値・真偽値としての妥当性検査はない。

| 実行経路 | unset / 空文字 | 空でない値が true | 空でない値が false |
|---|---|---|---|
| Windows の resident arena 初回読み込み | file-cache 状態と空き RAM の自動判定 | `1`, `true`, `false`, `2`, ` 1` など先頭が `0` 以外の値 | `0`, `0anything` など先頭が `0` の値 |
| Windows/Linux の mmap file tier（resident budget 指定時） | OS ごとの自動判定 | 同上。file-cache 判定を上書きして direct read を試す | 同上。file-cache 経路を選ぶ |
| CUDA/HIP の Windows/Linux `--ssd-experts` | 対象外（強制 direct read の試行） | 環境変数の値にかかわらず direct read を試す | 環境変数の値にかかわらず direct read を試す |
| Linux の resident arena 初回読み込み（CUDA/HIP/SYCL） | buffered 読み込み | 判定値は true になるが direct 読み込み実装がなく buffered fallback | buffered 読み込み |

値判定の実装は CUDA/HIP 共通の `engine/src/core/pinned.cu:1433-1439` と SYCL の `engine/sycl/src/core/pinned.dp.cpp:683-689`、file tier の `engine/src/core/expert_source.cpp:969-972,2867-2872` および `engine/sycl/src/core/expert_source.cpp:401-404,1113-1118`。

## 有効になる条件

- **resident arena の初回読み込み**: `--mmap-experts` を選ばない通常の arena 読み込み経路で `experts_unbuffered` が呼ばれる。Windows では true のとき `experts.bin` の aligned read や GGUF shard の読み込みに `FILE_FLAG_NO_BUFFERING` を使う。Linux の CUDA/HIP と SYCL では同じ helper が true を返し、reader 数も増やすが、`load_experts_direct` は `_WIN32` 専用で Linux では失敗値（error 文字列なし）を返すため、buffered reader に切り替わる。従ってこの経路で Linux の `=1` は実読み込みを direct にしない。`engine/src/core/expert_source.cpp:6781-6782,6837-6847`、`engine/src/core/pinned.cu:1358-1365,1427-1430`、SYCL `engine/sycl/src/core/expert_source.cpp:3471-3498`、`engine/sycl/src/core/pinned.dp.cpp:608-615,677-681`。
- **mmap file tier**: `--mmap-experts` と `--resident-budget-gib N`（`N > 0`）の組み合わせで、起動時の `set_unbuffered` と RAM copy 構築後の `recheck_unbuffered` が判定する。Windows/Linux で direct I/O が可能。予算がない `--mmap-experts` は file cache を expert tier として使うため、非空かつ先頭が `0` 以外の値でも無視され、その場合 `strata generate: the file tier reads through the file cache (STRATA_UNBUFFERED_LOAD=... ignored: without --resident-budget-gib the file cache holds the experts)` を出す。`--stream-experts` の SYCL 経路は `mmap` 分岐を通らず、この変数を参照しない。`engine/src/program/generate.cpp:8621-8628,8654-8674`、SYCL `engine/sycl/src/program/generate.cpp:4711-4725,4726-4757`。
- **CUDA/HIP の `--ssd-experts`** は `--mmap-experts` を有効にして resident budget を 0 にし、`set_unbuffered(..., force=true)` を通る。ここではこの変数の `0` も含め値を読み取らず、direct read を試す。失敗時は file-cache 経路に戻る。CLI の `--resident-budget-gib 0` もこの `ssd_experts` 経路を選ぶ。`engine/src/program/generate.cpp:4236-4257,8654-8658`、`engine/src/core/expert_source.cpp:2842-2858`。
- unset / 空文字の file-tier 自動判定は Windows ではファイルキャッシュの probe と空き RAM を使う。Linux では利用可能 RAM と expert read set の見積もりを使い、`STRATA_FILE_TIER_HONEST`、`STRATA_FILE_CACHE_OLD_RULE`（`STRATA_HIP_GFX906` build macro が既定値に影響）、条件付きの `STRATA_FILE_TIER_PROBE` がその自動判定に関与する。`STRATA_UNBUFFERED_LOAD` に非空値がある場合はこれらの自動判定を先に短絡して上書きする。`engine/src/core/expert_source.cpp:963-1038`。

## 実行時の詳細

この変数を読む箇所に static cache はない。arena は `ArenaExpertSource::open` 中の初回読み込み時、file tier は `set_unbuffered` および RAM copy 後の `recheck_unbuffered` 時に `getenv` を評価する。file tier の再判定では、非空値があれば自動判定を再実行せず、現在 `direct_` が開いているかを返すため、同一プロセス内で環境値を変更しても既存の I/O mode を切り替えない。unset / 空文字の場合は RAM copy の実サイズと残りの expert bytes に基づいて再判定し、必要なら direct handle を開閉する。`engine/src/core/expert_source.cpp:2842-2903`、SYCL `engine/sycl/src/core/expert_source.cpp:1094-1139`。

Windows の file tier は `FILE_FLAG_NO_BUFFERING`、Linux は `O_DIRECT` で handle を開く。Linux の自動判定は `STRATA_FILE_TIER_HONEST`（unset または先頭が `0` 以外なら追加の memory sample）、`STRATA_FILE_CACHE_OLD_RULE`（非空値の先頭文字が `0` 以外なら旧 room rule）、`STRATA_FILE_TIER_PROBE`（先頭が `0` なら drive probe を抑止）と `STRATA_HIP_GFX906` の build 条件に影響される。対象変数に非空値があればこれらの判定より優先する。`engine/src/core/expert_source.cpp:978-1038`。

## ログと測定値

file tier の初期判定は `strata generate: the file tier reads unbuffered (%s)` または `... through the file cache (%s)` を stderr に出し、理由文字列に `STRATA_UNBUFFERED_LOAD=<値>` を含める。RAM copy 後も同様の行を再出力し、選択が変化すれば `(changed)` が付く。直接 open に失敗した場合、Windows は `cannot open ... unbuffered (error N)`、Linux は `cannot open ... with O_DIRECT (...)` を理由に加え、file cache に戻る。`engine/src/program/generate.cpp:8654-8658,12223-12229`、`engine/src/core/expert_source.cpp:2773-2805`。

resident arena の読み込みでは `strata generate: expert arena read unbuffered (%s)` が出る。Windows の direct 読み込みでファイル open / read に失敗すると arena load が拒否され、呼び出し元はエラーを stderr に出して終了する。Linux のこの経路は上記の buffered fallback があっても `unbuffered` と表示する場合があるため、このログだけでは実際に direct read されたとは判断できない。`engine/src/core/expert_source.cpp:6840-6852`、`engine/src/core/pinned.cu:1383-1410`。

## 根拠

- 環境変数の直接参照全件（実装）: `engine/src/core/pinned.cu:1433-1439`、`engine/sycl/src/core/pinned.dp.cpp:683-689`、`engine/src/core/expert_source.cpp:963-972,2867-2872`、`engine/sycl/src/core/expert_source.cpp:395-404,1113-1118`、`engine/src/program/generate.cpp:8670-8673`、`engine/sycl/src/program/generate.cpp:4753-4756`。
- 一覧上の分類は `docs/SETTINGS.md:347`。現行ソースでは Windows/Linux の expert read policy として実装されており、一覧記載の NVIDIA/AMD/Intel Arc のみという分類を限定条件とは確認できない。
- `docs/QUANTS.md:132-141` と `docs/TROUBLESHOOTING.md:263-269` は RAM budget 下での利用例と過去測定を記載する。測定条件・世代が現行コードの全経路を覆うものではないため、本書では性能値や一般的な速度効果として採用しない。
