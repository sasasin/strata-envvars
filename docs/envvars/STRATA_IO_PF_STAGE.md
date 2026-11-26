# `STRATA_IO_PF_STAGE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux のファイル層 I/O prefetch が有効なとき、`experts.bin` の先読み先をページキャッシュにするか、expert blob 用 staging buffer にするかを切り替える。既定では I/O worker が未キャッシュ範囲を scratch buffer に `pread` してページキャッシュを埋め、計算側は mapped file を読む。値が非ゼロなら worker は blob を staging buffer に読み、要求側はその buffer を使う。これは I/O prefetch 自体を有効化する設定ではない。`FileExpertSource::set_io_prefetch` が切替を設定し、`io_worker`、`prefetch`、`io_blob` が経路を実行する（`engine/src/core/expert_source.cpp:1261-1289,1406-1433,1468-1479,2449-2467`）。

## 値と判定

有効化判定は `std::getenv` の null 判定後に `std::atoi(v) != 0` を使う。文字列全体の数値検証やエラー処理、clamp はない。`atoi` が変換した整数が非ゼロなら staging 側、ゼロなら既定の page-fill 側になる。例えば `1`、`2`、`-1`、`1x` は非ゼロ扱い、`0`、`0x`、空文字、数字で始まらない文字列はゼロ扱い。先頭空白と符号は `atoi` の変換規則に従う。大きすぎる値の変換結果はコードで安全に定義・検査されていない（`engine/src/core/expert_source.cpp:1285-1288`）。

| 条件 | unset | 設定時に staging になる値 | 設定時に staging にならない値 |
|---|---|---|---|
| Linux、mapped `experts.bin`、I/O prefetch 有効 | page-fill（`io_fill_ = true`） | `atoi` 結果が非ゼロ。例: `1`, `-1`, `1x` | `atoi` 結果がゼロ。例: `0`, `0x`, 空文字, `true` |
| Linux、GGUF shard をその場で読む経路 | `io_fill_ = false` | 値にかかわらず同じ経路 | 値にかかわらず同じ経路 |
| I/O prefetch が無効、または Linux 以外 | この変数による切替なし | この変数による切替なし | この変数による切替なし |

GGUF 直読みでは `role_ptr_` が空でないため、代入式の左辺 `role_ptr_.empty()` が false となり、値が非ゼロでも `io_fill_` は false のまま。これは staging 経路を選ぶ状態ではあるが、`STRATA_IO_PF_STAGE` の値による差は生じない（`engine/src/core/expert_source.cpp:1285-1288,1812-1813,1875-1880`）。

## 有効になる条件

- `strata generate` の `--mmap-experts` ファイル層を使う必要がある。通常の expert arena 経路では `FileExpertSource` のこの設定を通らない（`engine/src/program/generate.cpp:8621-8628,8745-8748`）。
- Linux で `set_io_prefetch(true, ...)` が実際に有効になる必要がある。`STRATA_IO_PREFETCH` が非空かつ `atoi` 非ゼロなら明示的に要求し、未設定または空なら `src.linux_io_defaults()` が既定を決める。既定が有効でも全 expert が GPU cache にあると Linux 既定の I/O prefetch が停止される場合があり、明示的な `STRATA_IO_PREFETCH=1` はその停止を防ぐ（`engine/src/program/generate.cpp:8693-8704,10251-10258,10275-10285`）。
- `set_io_prefetch` は Linux でのみ worker を起動する。`on` が false、mapping がない、path がない、または unbuffered reader の場合は有効にならない。必要なファイル descriptor を開けない場合も途中で戻り、prefetch は開始されない（`engine/src/core/expert_source.cpp:1261-1277,1310-1312`）。この場合、値自体をエラーとして扱う処理はない。
- `experts.bin` で page-fill 方式と staging 方式を切り替えるのは `role_ptr_` が空のときだけ。GGUF shard 直読みでは `role_ptr_` が設定されているため、この変数による違いはない（`engine/src/core/expert_source.cpp:1285-1288,1812-1813,1875-1880`）。
- `STRATA_IO_PF_STAGE` は prefetch の可否、I/O thread 数、decode gate を上書きしない。これらは別途 `STRATA_IO_PREFETCH`、`STRATA_IO_PF_THREADS`、`STRATA_IO_PF_GATE` などで決まる（`engine/src/program/generate.cpp:8693-8718`; `engine/src/core/expert_source.cpp:1283-1303`）。

## 実行時の詳細

初回のファイル層設定で `set_io_prefetch` が呼ばれ、`STRATA_IO_PF_STAGE` がその時点で読み取られて `io_fill_` に反映される。GPU cache の全 expert 保持を理由に Linux 既定の prefetch が停止されたあと、cache resize や eviction で再有効化される経路でも `set_io_prefetch` が再度呼ばれるため、その都度この値を読み直す。変数は expert ごと・request ごとには読まれず、active 中の環境値変更だけでは `io_fill_` は更新されない（`engine/src/program/generate.cpp:8701-8704,10275-10285,10341-10369`; `engine/src/core/expert_source.cpp:1261-1289`）。

page-fill 方式では worker が各 span の未 resident 範囲を thread-local scratch buffer へ `pread` し、そのページを cache に置く。`prefetch` は worker に仕事を渡して戻り、kernel 側は mapping を読む。非ゼロ設定の staging 方式では、worker が mapped blob の未 cache データを stage buffer へコピーし、要求側は stage buffer を利用する。`io_blob` は stage 済みでない場合、cache 上の blob は mapping から返す（`engine/src/core/expert_source.cpp:1406-1433,1440-1464,1468-1495,2451-2467`）。

## ログと測定値

prefetch が有効で、`STRATA_IO_PF_STAGE` の `atoi` 結果が非ゼロなら、stderr に次の注意行が出る。これは切替の成功確認ログではなく、測定についての案内であり、無効値や unset では出ない（`engine/src/program/generate.cpp:8725-8729`）。

```text
strata generate: note: STRATA_IO_PF_STAGE=1 (staging) measured faster only on a 32 GB-class box (+25% on an RTX 3060, 32 GB); it was slower at 16 GB and on an iGPU (docs/DETAILS.md, file tier I/O)
```

`docs/DETAILS.md` の測定表は、0.1.40.2、RTX 3060 と Radeon 780M、interleaved A/B 10 pairs、200-token greedy、page cache dropped と記し、`experts.bin` で staging と fill を比較した値として RTX 3060 / IQ3_XXS の 32 GB 時 +25.7%、16 GB 時 -32.6%、Radeon 780M / Q2_0 の 16 GB 時 -19% を載せている。これは Strata 資料に記録された結果であり、ここで再測定したものではない（`docs/DETAILS.md:1667`）。

## 根拠

- `engine/src/core/expert_source.cpp:1261-1289` — Linux 条件、descriptor 確保、`atoi` による値判定と `io_fill_` 設定。
- `engine/src/core/expert_source.cpp:1406-1433,1468-1495,2451-2467` — page-fill と staging の worker / 読み出し動作。
- `engine/src/program/generate.cpp:8693-8729,10275-10285,10341-10369` — prefetch 起動・停止・再開条件と注意ログ。
- `engine/src/core/expert_source.cpp:1570-1580,1812-1880` — `experts.bin` と GGUF 直読みの source 構成。
- `docs/DETAILS.md:1667` — 資料に記録された staging 対 fill の測定条件と値。
