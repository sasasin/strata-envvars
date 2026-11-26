# `STRATA_ARENA_MMAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

非 Windows の `ArenaExpertSource` で、native pack の expert arena を通常の pinned RAM コピーではなく、pack の `experts.bin` から read-only mmap する経路を選ぶ。すでに arena 形式で末尾に最大 blob 分の padding を持つ `experts.bin` がある場合はそれを直接 map する。ファイルが無く GGUF shard から読み込む場合は、まず通常の arena に読み込み、空き容量が条件を満たせば `experts.bin` を生成して次回起動から map する。Windows では arena mmap 判定が常に false で、この変数による map・生成は行わない。`--mmap-experts` の file-tier 経路ではなく、`ArenaExpertSource` の選択経路で作用する（`engine/src/core/expert_source.cpp:6445-6460,6484-6523,6865-6887`; SYCL 複製実装 `engine/sycl/src/core/expert_source.cpp:3311-3326,3350-3388,3513-3536`）。

## 値と判定

判定は文字列全体の parse ではなく、値が存在し、先頭 byte が文字 `'1'` かどうかだけを見る。空文字は無効。`"1"`、`"10"`、`"1anything"` は有効で、`"0"`、`"true"`、`" 1"`、未設定は無効。大文字小文字、数値としての妥当性、末尾文字は検査しない。Windows の arena 判定は値にかかわらず無効。

| ビルド / 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 非 Windows `ArenaExpertSource`（CUDA / SYCL 共通実装） | 無効 | 先頭が `1`（例: `1`, `10`, `1xyz`） | 先頭が `1` 以外（例: 空文字、`0`, `true`, ` 1`） |
| Windows `ArenaExpertSource` | 無効 | なし | すべて |
| HIP / HIP GFX906 の非 Windows 補助処理 | 無効 | 先頭が `1` | 空文字、先頭が `1` 以外 |

arena 判定は `ArenaExpertSource::open` 内の関数ローカル `static const bool` に保存され、最初の `open` 時に一度評価する。HIP の `pin_blobs_on()` も独自の関数ローカル static を初回呼び出し時に保存する（`engine/src/core/expert_source.cpp:6490-6494`; `engine/sycl/src/core/expert_source.cpp:3356-3360`; `engine/src/program/generate.cpp:595-601`; `engine/sycl/src/program/generate.cpp:217-224`）。

## 有効になる条件

- `ArenaExpertSource` を使う実行経路であること。通常の CUDA 側では `arena_src.open(...)` が呼ばれる分岐で作用する。SYCL 側では `--stream-experts` が有効かつ `--mmap-experts` が無効だと `GgufExpertSource` を選ぶため、その経路では arena mmap 判定に入らない（`engine/src/program/generate.cpp:8745-8748,8871-8872`; `engine/sycl/src/program/generate.cpp:4711-4720,4759-4778`）。
- Windows では無効。非 Windows 実装だけが `getenv` を評価して POSIX `open` / `mmap` を呼ぶ（`engine/src/core/expert_source.cpp:6490-6505`; `engine/sycl/src/core/expert_source.cpp:3356-3371`）。
- 既存 `experts.bin` を mmap するには、そのサイズが `want + blob`（arena 全体と最大 blob 1 個分の padding）に一致する必要がある。通常サイズ `want` の既存ファイルは mmap 条件を満たさず、通常の RAM arena 読み込みに進む。サイズがどちらとも一致しない場合は arena 読み込み前のサイズ検査で拒否される（`engine/src/core/expert_source.cpp:6456-6481,6495-6521`; SYCL: `engine/sycl/src/core/expert_source.cpp:3322-3347,3361-3387`）。
- `experts.bin` が無いときに GGUF から読み込んで生成するには `lay.native`、native GGUF shard 情報があり、GGUF 検査を通ることが必要。生成には pack directory に `want + blob + 2 GiB` 以上の空きが必要。空きが足りない、または空き容量検査が失敗した場合は現在の起動では RAM arena を使い続け、ファイルを生成しない（`engine/src/core/expert_source.cpp:6459-6467,6865-6875`; SYCL: `engine/sycl/src/core/expert_source.cpp:3325-3333,3513-3523`）。
- map 成功時は device alias を空にして `pinned_bytes_` を 0 にする。実装コメントはこの mapped arena では `--pcie-frac 0` で実行するよう案内しているが、ここで CLI 値を強制設定する処理はない（`engine/src/core/expert_source.cpp:6501-6519`; SYCL: `engine/sycl/src/core/expert_source.cpp:3367-3385`）。
- HIP または `STRATA_HIP_GFX906` の非 Windows build では、同じ先頭文字判定が起動時に `GPU_PINNED_MIN_XFER_SIZE=1000000` を `setenv(..., 0)` で設定する。既存値を上書きしない。さらに適応的 swap の pin 処理は `pin_blobs_on()` が true の場合だけ span を収集して `pin_blobs` に渡す（`engine/src/program/generate.cpp:3741-3749,8917-8925`; SYCL: `engine/sycl/src/program/generate.cpp:1858-1866,217-224,8917-8925`）。この文書は Strata による環境値の読み取り・設定だけを記し、外部 runtime の挙動は扱わない。
- map 後の VRAM resident expert のページ解放を `STRATA_ARENA_RELEASE=0` で止められる。未設定または先頭が `0` 以外なら mapped source の resident experts を `release()` し、その後 nonresident experts に `prefetch()` hint を出す（`engine/src/program/generate.cpp:11022-11045`）。

## 実行時の詳細

`ArenaExpertSource::open` は既存 `experts.bin` の有無と arena geometry を先に検査する。mmap が有効で、既存ファイルのサイズが `want + blob` なら read-only / shared mapping を行い、`base_` を map に向け、pinned/device alias を無効にして成功する。mmap が失敗した場合は `ArenaExpertSource: mmap of <path> failed` をエラーとして返し、通常 RAM への fallback はしない。ファイルが無い場合は GGUF から通常の arena に読み込み、十分なディスク空きがあれば `.tmp` に arena bytes とゼロ padding を書き、rename で `experts.bin` にする。書き込み失敗は一時ファイルを削除してログに出し、現在の起動は RAM arena のまま継続する。次回の `open` が正確な padded size のファイルを見つければ mmap する（`engine/src/core/expert_source.cpp:6468-6481,6494-6521,6837-6858,6865-6887`; SYCL: `engine/sycl/src/core/expert_source.cpp:3334-3347,3360-3387,3489-3506,3513-3536`）。

この変数の `arena_mmap` は初回 `open` 時の値をプロセス内で cache するため、その後の環境変更は反映されない。mapped source では `blob()` が map 内の expert pointer を返し、resident page の `release()` はページ境界に揃えた範囲へ `madvise(MADV_DONTNEED)`、`prefetch()` は `madvise(MADV_WILLNEED)` を呼ぶ（`engine/src/core/expert_source.cpp:6962-6971,6980-6992,7036-7044`; SYCL: `engine/sycl/src/core/expert_source.cpp:3588-3598,3600-3618,3636-3645`）。HIP 補助の環境読み取りも static cache であり、起動時の `GPU_PINNED_MIN_XFER_SIZE` 設定は明示的な既存値を保持する。

## ログと測定値

- mmap が成功すると source note は `mapped read-only from <path> (STRATA_ARENA_MMAP: not locked, not pinned)` となり、呼び出し側が `strata generate: expert arena: <note>` と stderr に出す（`engine/src/core/expert_source.cpp:6516`; `engine/src/program/generate.cpp:8871-8883`; SYCL: `engine/sycl/src/core/expert_source.cpp:3381`; `engine/sycl/src/program/generate.cpp:4775-4785`）。
- mmap 呼び出しの失敗は `ArenaExpertSource::open` が false を返し、呼び出し側が `strata generate: <error>` を stderr に出して終了コード 1 で終了する（`engine/src/core/expert_source.cpp:6502-6505`; `engine/src/program/generate.cpp:8871-8883`; SYCL: `engine/sycl/src/core/expert_source.cpp:3368-3371`; `engine/sycl/src/program/generate.cpp:4775-4779`）。
- 初回生成に必要な空き容量が無ければ `strata generate: STRATA_ARENA_MMAP: NOT writing ...`、書き込み試行後は `strata generate: STRATA_ARENA_MMAP: wrote ...` または `could NOT write ...` を stderr に出す（`engine/src/core/expert_source.cpp:6871-6887`; SYCL: `engine/sycl/src/core/expert_source.cpp:3519-3535`）。
- Strata の資料には性能値の記載があるが、この文書ではコード上の動作説明に必要でないため転記しない。

## 根拠

- CUDA 実装の arena判定、read-only mmap、補助処理とログ: `engine/src/core/expert_source.cpp:6445-6523,6865-6887`。
- CUDA 側の起動時設定・pin 条件・mapped page の release / prefetch: `engine/src/program/generate.cpp:595-601,3741-3749,8871-8883,11022-11045`。
- SYCL 複製実装の arena 判定、read-only mmap、生成ログ: `engine/sycl/src/core/expert_source.cpp:3311-3388,3513-3536`。
- SYCL 起動時設定・pin 条件・arena 呼び出し: `engine/sycl/src/program/generate.cpp:217-224,1858-1866,4711-4779,8917-8925`。
