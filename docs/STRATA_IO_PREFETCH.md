# `STRATA_IO_PREFETCH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

Linux の mapped file tier で、expert の読み出しをページフォールトに任せる経路から、ファイル全体を `pread` する I/O worker 経路へ切り替える opt-in 変数です。対象は `--mmap-experts` の `FileExpertSource` です。値を省略した既定状態では無効です。

有効時、未キャッシュの expert を worker が読みます。router lookahead が使える経路では、予測した後続 layer の expert も I/O worker に先読み要求します。`experts.bin` では既定で読み込んだページを page cache に入れ、kernel は従来どおり mapping を参照します。`STRATA_IO_PF_STAGE` が非ゼロなら未キャッシュの blob を stage buffer に読み、必要な layer はその読み込みを待ちます。GGUF shard の in-place 経路では stage buffer を使う設定になります。

## 値と判定

`src/program/generate.cpp` で `getenv` の結果を `std::atoi(v) != 0` として判定します。値全体の検証や許可値一覧はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、数字に変換できない文字列、先頭の数値部分が `0` | 無効（`atoi` が 0 を返す） |
| 先頭の空白・符号の後に非ゼロ整数がある値 | 有効。`1abc` のように整数の後ろに文字があっても、数値部分が非ゼロなら有効 |
| 負の非ゼロ整数 | 有効 |

`atoi` を用いるため、完全な数値文字列かどうかは検査しません。範囲外整数の変換結果は C/C++ の `atoi` の制約に従い、コード上で追加の範囲処理はありません。

## 有効になる条件

環境変数を読むのは `o.mmap_experts` が真で、`FileExpertSource::open()` が成功し、unbuffered 設定を処理した後だけです。通常の arena source 経路ではこの変数を読みません。

変数が非ゼロでも、次の条件を満たさないと `src.io_prefetch()` は有効になりません。

- Linux ビルドである。
- mapped source の `base_` が有効で、ファイル `paths_` が空でない。
- `direct_` が空である（unbuffered file reader ではない）。
- source が各ファイルを `O_RDONLY | O_CLOEXEC` で開ける。いずれかの open に失敗すると、それまでに開いた fd を閉じて無効のまま戻る。

非 Linux では setter は何もせず、unbuffered 経路でも無効です。要求値が非ゼロなのに有効化されなかった場合、stderr に `STRATA_IO_PREFETCH=1 is not available here (Linux mapped file tier only, not with unbuffered reads); the file tier reads as before` を出します。Linux で有効化できた場合は有効ログが出ます。HIP の AMD iGPU で adaptive tier も有効な場合、Radeon 780M のメモリー圧迫時に GPU reset が見られたという警告を出しますが、処理は要求どおり続けます。

## 実行時の詳細

`FileExpertSource::set_io_prefetch()` は初期化時に worker thread 数を設定します。関連する `STRATA_IO_PF_THREADS` が正の整数ならその値、未設定・0・負値なら既定 8 です（この変数の個別仕様は対象外）。同じ初期化時に `STRATA_IO_PF_AHEAD` と `STRATA_IO_PF_STAGE` も読みます。`STRATA_IO_PF_AHEAD=0` は予測先読み queue を止めますが、要求 layer の demand read 自体は無効にしません。

`STRATA_IO_PREFETCH` の判定は source 初期化時の一回です。実行中に環境を書き換えても再評価しません。`set_io_prefetch()` は Linux でファイル descriptor と worker pool を準備し、`io_pf_` と `io_stats_` を有効にします。各 layer では `prefetch()` が未キャッシュの要求 expert を worker に渡し、router lookahead が予測した expert も、read-ahead が有効なら queue に入れます。`experts.bin` の通常設定では worker が `pread` でページ cache を満たし、kernel 側は mapping を参照します。stage 設定では未キャッシュ expert の blob を buffer に読み、blob 要求側は worker の読み込み完了を待つ場合があります。

有効化に失敗した場合の処理は従来の mapped file tier の読み方に戻ります。`STRATA_IO_STATS` は prefetch が OFF のときだけ別途読まれて統計を有効にします。prefetch が ON の場合は setter が統計も有効にし、request ごとの I/O ログと最後の集計に page-cache hit/miss、pread、先読みの used/unused/dropped 件数、decode 中の fetch wait を表示します。

## 文書と測定値

`docs/DETAILS.md` はこの経路を Linux の opt-in とし、既定設定と `STRATA_IO_PF_STAGE=1` の A/B 測定を報告しています。記載条件は各条件 10 組の interleaved run、200-token greedy median、各 run 前に page cache を drop、cgroup でメモリー制限です。RTX 3060 32 GB / IQ3_XXS では既定 -3.4%、stage +25.7%、RTX 3060 16 GB / IQ3_XXS では既定 -1.8%、stage -32.6%、Radeon 780M iGPU 16 GB / Q2_0（adaptive tier off）では既定 -0.7%、stage -19% と記載されています。これらは文書にある条件での結果です。資料はまた、warm page cache では改善余地がなく、既定 OFF と説明しています。

同資料には、greedy IQ3_XXS と Q2_0 で prefetch OFF/ON の hash が一致したとの記録があります。これは資料に記載されたモデル・実行条件の照合結果であり、ここで別途測定・再検証したものではありません。ソースのコメントも blob の bytes が同じだと説明しています。

## 根拠

- `src/program/generate.cpp:4620-4637,4644-4648,4667-4698` — `--mmap-experts` の source 初期化、unbuffered 判定後の環境変数読み取り、ログ、AMD iGPU 警告、および `STRATA_IO_STATS` との分岐。
- `src/core/expert_source.cpp:636-669` — Linux 条件、mapped source / unbuffered 条件、fd open、thread 数、関連設定の読み取りと worker 起動。open 失敗時は `io_pf_` を有効化しない。
- `src/core/expert_source.cpp:702-803,1426-1455,2116-2155,3406-3435` — read-ahead worker、demand prefetch、lookahead warm、mapped/staged blob の受け渡しと統計。
- `include/strata/core/expert_source.hpp:717-742,824-849` — 機能の Linux file-tier スコープ、関連設定と統計項目。
- `src/program/generate.cpp:5498-5524,12308-12339,13213-13239` — lookahead の有効化・深さ設定、および request/最終 I/O 統計ログ。
- `docs/DETAILS.md:225-245` — opt-in の説明、A/B 測定条件・値、hash 一致と AMD iGPU 上の caveat。
