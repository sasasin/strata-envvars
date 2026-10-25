# `STRATA_ARENA_MMAP`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・driver の環境変数としての意味は対象外。

## 役割

`ArenaExpertSource` の expert arena を、RAM 上の pinned（登録済み）コピーとして読み込む代わりに、pack の `experts.bin` を read-only の mmap として使う。GPU の VRAM で大部分の expert を保持し、RAM が足りない PC 向けの opt-in 機能。

読み取り箇所は次の 3 系統で、いずれも Strata 自身のソースにある。

- arena のバックエンド選択: `src/core/expert_source.cpp:4451-4483`（SYCL 版は `sycl/src/core/expert_source.cpp:3356-3388`）
- 適応 swap のコピー元 page lock: `src/program/generate.cpp:163-172` の `pin_blobs_on()`（SYCL 版 `sycl/src/program/generate.cpp:185-192`）
- 起動時に別の環境変数への設定: `src/program/generate.cpp:1742-1750`（SYCL 版 `sycl/src/program/generate.cpp:1632-1640`）

`serve/`、`setup.py`、`tools/` にはこの名前の読み取りがない。CLI オプションでの等価設定もない（`--mmap-experts` は別クラス `FileExpertSource` の機能で、この変数とは別）。

## 値と判定

3 箇所すべて、文字列全体を parse せず、`getenv()` の結果の**先頭文字だけ**を `'1'` と比較する。

| 状態 | 判定 |
|---|---|
| unset | 無効 |
| 空文字 | 無効（先頭文字は `\0`） |
| 先頭文字が `1` | 有効。例: `1`、`10`、`1anything` |
| それ以外（`0`、`true`、`on` など） | 無効 |

`atoi`/`strtol` ではなく `e[0] == '1'` の比較なので、`1` 以外の数字、負値、大文字小文字、空白は検査されない。同じ名前の `getenv` は各箇所で二回呼ばれる（null チェックと先頭文字比較）。

## 既定値と優先順位

- 既定は無効。`docs/DETAILS.md:199-204` の "Without the variable nothing changes." は、この parse 結果と一致する（未設定・空文字・`1` 以外の値はすべて無効）。
- 有効でも、arena が mmap にならない経路がある。ファイルが存在しない、またはサイズが `want + blob`（arena layout の pad 分）でない場合は、そのまま通常の pinned arena の読み込み経路に落ちる（`src/core/expert_source.cpp:4457-4482`）。サイズチェックは `4430-4442` で、`want` と `want + blob` の両方を受け入れるが、mmap は `have == file_bytes`（pad 込み）のときだけ行う。
- 優先順位として、mmap 分岐は RAM 量チェック（`#633` の cgroup/available 判定、`4485-4514`）と共有 arena（`--shared-expert-arena`）の処理より**前**にある。mmap が成功すると `open()` は `return true` で抜けるため、`ram_warning_` は出ず、共有 arena の pack hash 検査も通らない。
- 起動時の `GPU_PINNED_MIN_XFER_SIZE` 設定は `setenv(..., "1000000", 0)` で、flag 0 により**既に設定されている値は上さない**（`src/program/generate.cpp:1749`）。Strata が行うのはこの設定だけであり、値の解釈は ROCclr 側にある。

## 有効になる条件

- **OS**: Linux（POSIX `mmap`/`madvise`）。Windows は `src/core/expert_source.cpp:4451-4452` で `arena_mmap = false` に固定（SYCL 版も `3356-3357` で同じ）。
- **backend/build macro**: 上記の mmap 選択自体は backend macro で分岐していない（CUDA/HIP/SYCL の Linux ビルドで効く）。一方 `pin_blobs_on()` と `GPU_PINNED_MIN_XFER_SIZE` の設定は `(defined(STRATA_USE_HIP) || defined(STRATA_HIP_GFX906)) && !defined(_WIN32)` のときだけ。したがって Linux の CUDA ビルドでは、mmap は有効になるが page lock 系統と driver 変数設定は動かない。
- **pack 状態**: native pack で `experts.bin` が存在し、arena layout の pad 込みサイズであること。`native_experts.txt` から GGUF を読む pack（`from_gguf`）では、最初の起動は mmap できず、pinned arena として読み込んだ後に `experts.bin` を書く（`4604-4627`）。書く条件は、そのドライブの空きが `want + blob + 2 GiB` 以上（`4609`）。足りなければ "NOT writing ... this start keeps the arena in RAM" として RAM 側で動く。
- **`--pcie-frac 0` が要られる**: mapped mode では `pinned_bytes_ = 0`、`dev_slice_.clear()`（`4470-4472`）なので `device_alias()` は常に `nullptr`、`pcie_layer()` は false（`4707-4720`、`include/strata/core/expert_source.hpp:198`）。prefill 側は `pcie_ok = d.pcie_num > 0 && d.src->pcie_layer(...)` が false になり、その layer の PCIe share のコピー数は 0 になる（`src/core/expert_source.cpp:3714-3715`）。`docs/DETAILS.md:203` の "Run it with `--pcie-frac 0`" はこのコード状態と一致する。
- **相互作用**: `STRATA_ARENA_RELEASE=0` は VRAM が保持している expert の page を返さない設定で、`release()` は `map_ != nullptr`（mapped mode）のときだけ意味を持つ（`6127`、`src/core/expert_source.cpp:4692-4705`）。`STRATA_HIP_ADAPT_KERNEL_COPY=1` は「source が mapped であること」を前提にする（`src/program/generate.cpp:176-177`）。`STRATA_ADAPT_OVERLAP` は `pin_blobs_on()` が true のとき "not with page-locked swap sources" として off になる（`8283`）。

## 実行時の詳細

- **読み取り時期**: `pin_blobs_on()` と `arena_mmap` は関数内 `static const bool` に一度だけ格納され、以後の環境変更は反映されない。`main()` の分岐は GPU を触る前、プロセス起動時に一度読む。
- **mmap 成功時**: `open()` はファイル読込・load loop・PinnedArena 確保をすべて飛ばして `return true` する。`note_` は `mapped read-only from <path> (STRATA_ARENA_MMAP: not locked, not pinned)` となり、起動ログは `strata generate: expert arena: <note>` として出される（`src/program/generate.cpp:4723`）。この経路では `gib_per_s_`・load 時間が 0 に設定されるので、直後の `loaded %.2f GiB at %.2f GiB/s` 行は 0 を表示する（`4724-4726`）。
- **expert 読み**: `blob()` は `base_ + blob_offset()` を返すだけ（`4722-4731`）。page fault による読みは OS の page cache が担い、dropped page はファイルから再読される。
- **page の返却と先読み**: `prefetch()` は blob の page 範囲を `MADV_WILLNEED`、`release()` は blob に**完全に含まれる** page だけを `MADV_DONTNEED`（隣と共有する page は残す）。呼び出しは startup の residency release（`src/program/generate.cpp:6122-6137`）と、decode/serve の swap 後（`8448`、`12946`）。`MADV_DONTNEED` はこのプロセスから外すだけで、clean page として cache に残るという説明が `4686-4691` にある。
- **page lock**: `pin_blobs_on()` が true のとき、swap 元 span を 4 KB に揃え、重複/隣接 span を merge し、`cudaHostRegister(ReadOnly | Portable)` を span ごとに一度行う。登録に失敗した span は pageable のまま（コピーは driver の staging 経由で成功する）で、`failed` 数を返す（`src/program/generate.cpp:197-222`）。コピーが到着した後 `unpin_blobs()` で解除する（`8326`、`11348`、`12856`）。呼び出側は `blob_stable()` の pointer を使う（`8384-8391`、`12914-12921`）。
- **close**: `munmap(map_, map_bytes_)`（`4658-4661`）。

## 資料にある測定

- `docs/DETAILS.md:199-204`: 2x 16 GB GPU + 32 GB RAM で、serve 中に利用可能 RAM が約 1 GB から 25 GB。PR #640、0.1.39、Linux、opt-in。
- `docs/AMD_HIP.md:508-516`: 2x Instinct MI50 16 GB（85 W）、PCIe 3.0 x16、Xeon E5-2666 v3、32 GB DDR4、SATA SSD、Coder IQ1_M（`--native`）、131,072-token context、`--pcie-frac 0`、`STRATA_ARENA_MMAP=1` の構成。
- `docs/AMD_HIP.md:248-250`: RX 6800 gfx1030、ROCm 7.2.4、31 GiB RAM、IQ3_XXS で `--mmap-experts` の各 run が stall し、`GPU_PINNED_MIN_XFER_SIZE=1048576` を加えてから stall しなくなったという報告。エンジンはこの値を 1000000 として設定する（単位は MiB とコメントされている）。
- `bench/results/2026-10-03-community-2x-mi50/README.md:52-53`: 起動時に 23.4 GiB が OS へ返されたというコミュニティ計測（`--pcie-frac 0` を "required with STRATA_ARENA_MMAP=1" としている）。これは記録であり、コードから独立に確認した事実ではない。

## 根拠

- `src/core/expert_source.cpp:4430-4443`（サイズ判定）、`4451-4483`（Linux 限定の parse と mmap）、`4604-4627`（初回起動のファイル書き出しとメッセージ）、`4658-4705`（munmap、prefetch、release）、`4707-4731`（pinned/device_alias/blob）
- `src/program/generate.cpp:163-172`（`pin_blobs_on` の HIP/Linux 条件）、`197-227`（register/unregister）、`1742-1750`（`GPU_PINNED_MIN_XFER_SIZE` 設定）、`6122-6137`（startup の release と `STRATA_ARENA_RELEASE`）、`8283`（`STRATA_ADAPT_OVERLAP` との相互作用）、`8384-8391`・`12914-12921`（swap span の lock）、`4700-4726`（arena 経路の選択とログ）
- SYCL 版の対応箇所: `sycl/src/core/expert_source.cpp:3338`、`3356-3388`、`3516-3535`、`3572-3636`、`sycl/src/program/generate.cpp:185-192`、`1632-1640`
- `docs/DETAILS.md:199-204`、`docs/AMD_HIP.md:248-250`、`508-516`

確認できていない点: mmap 分岐は backend macro で守られていないため、Linux の CUDA ビルドでも arena の mmap は選択される。この場合 driver 変数設定と page lock は動かない（上記の条件分岐）。この組合せの性能・安定性はソースから判断できない。テストコード・ベンチ記録は候補値の根拠にはしていない。
