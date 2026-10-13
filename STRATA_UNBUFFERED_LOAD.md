# `STRATA_UNBUFFERED_LOAD`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

expert をモデルファイルから読み込む際、OS のファイルキャッシュを経由しない direct / unbuffered I/O を選ぶかどうかを指定します。主に Windows の通常 RAM expert arena の初期読込、および Windows/Linux の `--mmap-experts --resident-budget-gib N` による file tier の読込に関わります。どの経路でも同じ機能になるわけではなく、特に Linux の通常 RAM arena 読込では direct reader が実装されていないため、指定が実際の I/O に反映されません。

## 値と判定

環境変数の文字列全体や数値としての妥当性は検査せず、先頭文字だけを見ます。`getenv()` が null、または値が空文字なら明示指定として扱わず、自動判定（またはその経路の既定）へ進みます。

| 値 | `experts_unbuffered()` / Linux file tier の判定 |
|---|---|
| 未設定、空文字 | 自動判定。経路と OS により結果が異なる |
| 先頭文字が `0`（例: `0`, `0abc`） | unbuffered を強制しない。false を返す |
| 空でなく先頭文字が `0` 以外（例: `1`, `true`, `false`, `2`, ` 1`） | unbuffered を要求する。大文字小文字、後続文字、数値形式は不問 |

従って `STRATA_UNBUFFERED_LOAD=false` は「無効」ではなく有効側です。`STRATA_UNBUFFERED_LOAD=0anything` は無効側です。空文字は `0` と同じ強制 OFF ではなく、自動判定です。

## 有効になる条件

- `--mmap-experts` の file tier で resident RAM budget が正（`--resident-budget-gib N`）なら、`FileExpertSource::set_unbuffered()` が変数を調べます。Windows と Linux ではこの経路に direct I/O の実装があります。正の値側を指定しても、ファイルを direct で開けない場合などは mapped/file-cache 読込に戻ります。未設定・空文字の場合は OS/メモリ状況から自動選択します。
- `--mmap-experts` でも resident budget がない場合、ファイルキャッシュが expert tier そのものとして使われるため、値による切替はしません。値が空でなく先頭文字が `0` 以外なら、stderr に「`ignored: without --resident-budget-gib the file cache holds the experts`」と出します。`0` 始まりや空文字ではこの警告も出ません。
- 通常の RAM expert arena 読込では、Windows で direct 読込選択が使われます。値が設定されていれば `0` 始まり以外で direct を選び、`0` 始まりで buffered を選びます。未設定・空文字なら Windows の probe と RAM 状況から決定します。
- Linux の通常 RAM arena では、`experts_unbuffered()` の明示値判定自体は共通コードで行いますが、選択後に呼ばれる `load_experts_direct()` は `_WIN32` 専用です。`STRATA_UNBUFFERED_LOAD=1` などで direct 側が選ばれても、ロード側は空の失敗結果を返し、呼び出し元が buffered `load_experts_ranges()` にフォールバックします。現行コード上、この経路では実データの direct I/O は行われません（ログの選択表示と実際の読込方法が食い違う場合があります）。
- Linux の file tier の自動判定は、利用可能 RAM、RAM copy に必要な量、ファイルから読む expert 量を使って page cache が読み返し対象を保持できるかを判定します。CUDA 実装はさらに 1 GiB の余裕、5% の余裕率、最低 3 GiB の閾値を `file_cache_keeps()` に渡します。SYCL 実装は同 helper の既定条件を使います。明示値があるとこの自動判定を迂回します。

## 実行時の詳細

`--mmap-experts` で resident budget を指定した場合、起動時に `set_unbuffered()` が expert file 全体のバイト数を調べ、RAM budget と expert 総量の小さい方を RAM copy の見積りに使います。file tier に残る expert の量と合わせて選択し、true なら direct file handle を開きます。CUDA 実装では Windows は `FILE_FLAG_NO_BUFFERING`、Linux は `O_DIRECT` で開きます。開けない場合は理由を `why` に付けて file-cache 読込にします。起動後に resident RAM copy の構築が終わると、Windows/Linux では `recheck_unbuffered()` が実際の copy 量と file tier に残る expert 量で再判定し、必要なら direct handle を開くか閉じます。環境変数は各判定時に再読込され、static cache はありません。

通常 RAM arena の Windows 起動では、未設定時に `experts_unbuffered()` が各ファイルからランダムな 64 KiB read を最大16回試し、読み出しが cache 相当か、および arena とファイルを RAM に保持できるかを見て選びます。強制 ON なら読み手数を少なくとも16にし、expert file の direct reader を使います。`experts.bin` の層範囲が4 KiB境界に揃わないなど direct read の前提を満たさない場合は buffered reader へ移ります。強制 OFF は buffered reader を選びます。Windows 以外の自動判定はこの関数では buffered を返します。

結果は stderr の起動ログに現れます。file tier は `strata generate: the file tier reads unbuffered (...)` または `through the file cache (...)`、通常 arena は `strata generate: expert arena read unbuffered (...)` または `through the file cache (...)` です。file tier の direct open に失敗した場合は `why` に `cannot open ... with O_DIRECT` 等の理由が付加されます。Linux 通常 arena の明示 ON は前述のとおり実体が buffered fallback でも arena 読込ログが `unbuffered` と表示されうるため、ログだけから実 I/O を断定できません。

## 文書との照合

`docs/TROUBLESHOOTING.md` は 0.1.40 / 0.1.40.1 では `=0` が buffered、`=1` が unbuffered を強制すると説明しています（同ファイル 105–111 行）。現行ソースも空でない値の先頭文字が `0` かで強制指定を判定しますが、空文字は自動判定であり、file tier では `--resident-budget-gib` が必要です。また、Linux の通常 RAM arena は実際の direct reader を使わないため、この古い説明を全経路へ一般化できません。`docs/DETAILS.md` には現行の当変数の値判定や全経路の適用条件をまとめた説明は見当たりませんでした。

## 根拠

- `src/core/pinned.cu:520-592,595-662` — direct reader は Windows 実装、env の先頭文字判定、Windows の自動 probe、その他 OS の buffered 既定。
- `src/core/expert_source.cpp:495-531,1083-1099,1102-1132,1589-1622` — CUDA file tier の env 判定、OS 別自動選択、設定と再判定、direct handle の open/fallback。
- `sycl/src/core/expert_source.cpp:380-412,1083-1132` — SYCL file tier の同等経路と Linux/Windows ガード。
- `src/program/generate.cpp:4689-4704,6870-6881` — `--mmap-experts`、resident budget 条件、警告ログ、RAM copy 構築後の再判定。
- `sycl/src/program/generate.cpp:4204-4235,6486-6497` — SYCL generate 経路の同等条件とログ。
- `src/core/expert_source.cpp:1612-1622` — Linux の file tier が `O_DIRECT` でファイルを開く箇所。
- `src/core/expert_source.cpp:4553-4593` — CUDA 通常 RAM arena の `experts_unbuffered()` 結果による読み手数と direct/buffered reader の選択およびログ。
- `sycl/src/core/expert_source.cpp:3458-3502` — SYCL 通常 RAM arena の同じ選択経路。
- `docs/TROUBLESHOOTING.md:105-111` — 旧バージョンについての説明。
