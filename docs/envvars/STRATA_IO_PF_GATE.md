# `STRATA_IO_PF_GATE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux の mapped file tier で I/O prefetch が動作しているとき、decode 中の先読みと未キャッシュ expert の `pread` を、page cache の空き容量と先読みの有用性に応じて止めたり再開したりします。ゲートが閉じても expert の読み込み自体は続き、mapping から読みます。prompt の読み込みはこのゲートでは止めません。

## 値と判定

`FileExpertSource::set_io_prefetch()` が Linux で I/O prefetch を開始するときに読みます。まず既定で有効にし、環境変数が未設定または空文字ならそのままです。空でない値は `std::atoi` で変換し、結果が 0 なら無効、それ以外なら有効です。文字列全体の検証、大小文字の扱い、値域 clamp はありません。

| 環境値 | 判定 |
|---|---|
| 未設定、空文字 | 有効（既定） |
| `0`、`00`、`false`、数字で始まらない文字列 | 無効（`atoi` が 0） |
| `1`、`-1`、`2tail`、先頭空白の後の `+1` | 有効（`atoi` が非 0） |

整数として表現できない範囲の入力に対する `atoi` の結果は保証しません。関連する `STRATA_IO_PF_GATE_LO` / `_HI` は容量比の閾値、`STRATA_IO_PF_GATE_USEFUL` は先読み有用率の閾値を指定します（それぞれ初期値 0.55 / 0.65 / 0.10）。この文書ではそれらの変数自体の全規則は扱いません。

根拠: `src/core/expert_source.cpp:1114-1118,1141-1155`。

## 有効になる条件

- `strata generate` が mapped file tier（`--mmap-experts`）を使い、Linux で `FileExpertSource::set_io_prefetch(true, ...)` を呼ぶ必要があります。I/O prefetch が無効ならこの変数は読まれず、ゲートも動きません (`src/program/generate.cpp:5608-5624,5655-5670`)。
- I/O prefetch が Linux の mapped file tier でない場合、または unbuffered reader の場合は `set_io_prefetch()` が開始前に戻ります。Linux 以外の実装は引数を使わず終了します (`src/core/expert_source.cpp:1114-1119,1161-1164`)。
- I/O prefetch 自体は、明示的な `STRATA_IO_PREFETCH` の非 0 値、または Linux の `linux_io_defaults()` によって開始します。後者は GGUF を直接読む場合は Linux file defaults が成立する場合、`experts.bin` は page-cache room ratio が初期判定の 0.55 以上の場合です。`STRATA_IO_PREFETCH=0` はゲートより上位で I/O prefetch 自体を止めます (`src/program/generate.cpp:5660-5668`; `include/strata/core/expert_source.hpp:1010-1022`)。
- ゲート既定値は開です。容量や有用率が条件を満たさないと実行中に閉じます。`STRATA_IO_PF_GATE=0` はその動的制御を無効にし、ゲートを常時開にします。

## 実行時の詳細

設定値は I/O prefetch 初期化時に `gate_on_` に保存され、各 `FileExpertSource` インスタンスの初期化後は環境を読み直しません。decode dispatch は `DecodeScope` で decode thread を印付けします。新しい decode window の開始時に gate が有効なら `gate_capacity()` と `gate_tick()` を呼びます。容量判定は窓カウンターの初回および16窓ごとに行われ、`gate_cache_room()` が Linux cgroup v2 の使用可能量（祖先を含む最小 room）を取得できない場合は `/proc/meminfo` の `MemAvailable` を使います。取得不能、または expert 総量が 0 の場合は現在の状態を維持します (`src/core/expert_source.cpp:1920-1974,1976-2004,3276-3292`; `src/program/generate.cpp:4812-4814`)。

容量比は `room / expert_bytes` です。開いているゲートは比率が `gate_lo_` 未満で閉じ、閉じているゲートは `gate_hi_` を超えると開きます。初期値は 0.55 と 0.65 で、境界値ちょうどでは閉じ側に留まります。さらに開いている場合、16窓分の read-ahead が 128 MiB 未満、またはそのうち使われた割合が `gate_min_useful_` 未満なら閉じます。先読みの計測が 64 MiB 未満なら有用率は更新されません。容量でなく有用性が理由で閉じた場合、256窓後に一度 probe として再開し、同じ条件で再評価します (`src/core/expert_source.cpp:1976-2004`)。

閉じたときの効果は decode 経路に限られます。

- Router lookahead の予測深度を通常の設定値から1層に下げます。通常深度の詳細は `STRATA_IO_PREFETCH_DEPTH` 等の設定に依存します (`src/core/expert_source.cpp:3175-3179`)。
- `warm()` は I/O worker への先読みを行わず、GGUF mapping がある場合は `madvise` のヒントへ進みます。スケジュール付き予測も通常の `warm()` へ fallback します (`src/core/expert_source.cpp:1081-1083,2956-2989`)。
- demand read は uncached span を `pread` せず、mapping から `memcpy` します。page-cache hit は通常どおり扱われます (`src/core/expert_source.cpp:1735-1768`)。

起動ログは `gate_on_` の状態に応じ「only while ... and it pays」または「always」と表示します。request I/O stats が有効なときは cache room ratio、先読み使用率、decode 読み込みの page-cache hit EWMA、open/closed 状態、closed window 数、切替回数を stderr に出します。`gate_tick()` が計算する held-share EWMA は表示用であり、開閉判定には使われません (`src/program/generate.cpp:5671-5684,15424-15429`; `src/core/expert_source.cpp:1903-1917`)。

`docs/DETAILS.md` は同機能の測定を記録しています。RTX PRO 5000 で12 GB GPU相当を模擬した Q2_0 GGUF、cgroup RAM 制限、page cache を各 engine 起動前に破棄した条件では、32 GB RAM で既定構成の decode が 1.70 / 2.56 / 2.88倍、16 GB では 1.16 / 1.25 / 1.25倍と報告されています。別途 RTX 3060 12 GB の結果も記載されています。これらは文書記載条件の測定値であり、ゲート単独の効果や他環境の性能を示す値ではありません (`docs/DETAILS.md:272-298`)。

## 根拠

- `src/core/expert_source.cpp:1114-1155` — Linux file tier の I/O prefetch 初期化、既定値と環境値の判定。
- `src/program/generate.cpp:5608-5624,5655-5690` — file tier 選択、I/O prefetch の開始条件、起動ログ。
- `include/strata/core/expert_source.hpp:995-1009,1010-1028,1031-1046` — ゲートの API、Linux 既定条件、初期値。
- `src/core/expert_source.cpp:1735-1768,1897-2004,3175-3179,3276-3292` — decode 判定、I/O 経路、開閉条件、window timing。
- `src/program/generate.cpp:15424-15429` — request stats の表示。
- `docs/DETAILS.md:272-298` — 設計説明と、測定条件が記された結果。
