# `STRATA_PLE_AUTO_RAM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは clean（`## main...origin/main`）。

## 役割

PLE（n-gram）テーブルの読み込み方式が既定の direct で、`--ple-io` が明示されていないときに、メモリ量の条件を満たせばテーブルを mmap し、全体を RAM に lock する residency policy を許可または禁止します。これは読み込み方式を必ず RAM にする指定ではなく、値が許可でも PLE テーブル、expert arena、メモリ余裕などの条件が揃ったときだけ切り替わります。

候補一覧 `docs/envvars/000_envvers.md:1276` に記載された名前は、`src/program/generate.cpp:4751` で実際に `std::getenv("STRATA_PLE_AUTO_RAM")` により読み取られます。ほかの一致箇所はコメント、テスト、文書です。環境変数名を動的に渡す helper 経由の読み取りはありません。

## 値と判定

読み取った値は `ple_auto_ram_allowed()` が `std::atoi(env_value) != 0` で判定します。文字列全体の検証やエラー報告はありません。

| 値 | policy の許可判定 |
|---|---|
| 未設定 | `STRATA_DEFAULTS=026` が有効なら不許可、それ以外は許可 |
| 空文字 | `atoi("") == 0` のため不許可 |
| 先頭の空白・符号の後に非ゼロの十進整数がある値（例: `  +2tail`, `-1`） | 許可。`atoi` が変換できる先頭の整数部分だけを使う |
| `0`、`-0`、数値に変換できない文字列（例: `false`, `on`） | 不許可（`atoi` の結果が 0） |
| 数字の後ろに文字が続く値（例: `1abc`, `0anything`） | 数字部分で判定。前者は許可、後者は不許可 |

`atoi` による変換なので、全体が整数であるかの検査、範囲 clamp、無効値への fallback はありません。`atoi` の表現範囲を超える入力の結果は移植可能な値として保証されません。判定結果だけでは RAM 化を保証しません。

未設定時の `STRATA_DEFAULTS=026` 判定は別の helper が行います。同変数は `026`、`0.2.6`、`v0.2.6` の完全一致だけを認識し、unset・空文字・`0` などは 026 としません。その値は `static const` により最初の呼び出し時に一度だけ cache されます。明示された `STRATA_PLE_AUTO_RAM` はこの master switch より優先します（`include/strata/core/defaults_026.hpp:21-29`, `include/strata/core/ple_residency.hpp:30-35`）。

## 有効になる条件

policy の判定と RAM 化には、次の条件が必要です。

- PLE GGUF が指定され、テーブルを direct mode で開けている。PLE テーブルの初期化ブロック内で判定する（`src/program/generate.cpp:4714-4735,4748-4753`）。
- `--ple-io` が指定されていない。`--ple-io mmap` / `ram` は初期 mode が mmap になり、明示 `--ple-io direct` も policy 分岐を通らないため、いずれもこの環境変数による自動 RAM 化を抑止する（`src/program/generate.cpp:598-599,3060-3063,4749`）。
- 値判定が許可され、テーブルサイズが 0 でなく、native expert layout から算出した expert arena のサイズが 0 でない。
- `available_host_bytes()` が値を返し、その値がテーブル＋expert arena＋8 GiB 以上である。加算 overflow や不明な値・サイズは不許可。available は会話メモリ用 sampler の値で、Linux では MemAvailable/cgroup/設定上限を考慮し、Windows では利用可能物理メモリ等を使います。ほかの OS では sampler が値を返さず、この判定は通りません（`src/program/generate.cpp:4753-4761`; `include/strata/core/ple_residency.hpp:23-27`; `include/strata/core/conversation_memory.hpp:10-30,82-85`; `src/core/conversation_memory.cpp:280-297`）。

## 実行時の詳細

対象値は `src/program/generate.cpp` の PLE 初期化中に一度読み、ここでは `static` cache されません。許可され、メモリ条件も満たす場合、Strata は最初に開いたテーブルを閉じ、mmap mode と `lock=true` で開き直します。成功すれば以後の PLE 読み込みはこの設定を使い、stderr に `strata generate: --ple-io ram chosen by the residency policy ...` を出します（`src/program/generate.cpp:4751-4774`）。

開き直しに失敗すると `resident PLE table failed (...); keeping direct reads` を stderr に出して direct mode に戻します。戻した direct open も失敗すれば `strata generate: <error>` を出して終了コード 1 を返します（`src/program/generate.cpp:4775-4783`）。条件不成立時に、この policy 固有の理由ログはありません。

RAM lock の失敗は policy の許可判定とは別です。テーブル open は lock を試み、lock できなければ警告を出してページを touch し、通常の mmap として続行します。Windows では `strata: PLE table lock failed (...)`、POSIX では ``strata: PLE table mlock failed (...; raise `ulimit -l`): its pages stay faulted in but may be reclaimed`` が出ます（`src/kernels/ngram.cpp:409-432,434-463`）。

`--serve` で会話 cache 容量を自動設定する場合、policy が実際に lock したテーブルのために cache が小さくなると、後段で lock を返して cache 容量を計算し直すことがあります。このとき `strata serve: PLE table lock given back: ...` が出ます。明示 `--ple-io ram` と明示 `--conversation-cache-mib N` はこの調整対象ではありません（`src/program/generate.cpp:10404-10427`）。

## 文書との照合

`docs/AMD_HIP.md:304,403-405` は自動 RAM 化の必要量を「テーブル＋8 GiB」と説明していますが、この HEAD の実装は expert arena の全サイズも加えて「テーブル＋arena＋8 GiB」を判定します（`src/program/generate.cpp:4755-4761`; `include/strata/core/ple_residency.hpp:23-27`）。同資料の測定値は資料に記載された条件下の報告として扱い、この調査では再測定していません。

## 根拠

- 候補名と実読み取り: `docs/envvars/000_envvers.md:1276`; `src/program/generate.cpp:4751-4752`
- 値変換と既定値: `include/strata/core/ple_residency.hpp:30-35`; `include/strata/core/defaults_026.hpp:21-29`
- CLI の既定値・明示指定・検証: `src/program/generate.cpp:598-599,943-946,3060-3063,3790-3793`
- 適格性判定、open と fallback、ログ: `src/program/generate.cpp:4748-4783`; `include/strata/core/conversation_memory.hpp:82-85`
- lock の結果と警告: `src/kernels/ngram.cpp:409-463`
- serve 時の lock 返却と自動 cache: `src/program/generate.cpp:10404-10427`
