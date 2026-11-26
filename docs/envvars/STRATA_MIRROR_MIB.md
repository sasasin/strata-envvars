# `STRATA_MIRROR_MIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の `--stream-experts` 経路で、VRAM の expert cache に入らない expert を pinned host memory にミラーする量の上限を MiB で指定する。値は `generate.cpp` のミラー準備時に byte の cap に変換され、GGUF expert source の `mirror` に渡る。ミラーできた expert は device 側のアドレス表に登録される。これはミラー対象の上限であり、expert cache の容量 (`--expert-cache`) や PCIe 経由で GPU が処理する miss の割合 (`--pcie-frac`) は別設定である（`engine/sycl/src/program/generate.cpp:5426-5429,5475-5505`）。

## 値と判定

実行時に `std::getenv` で読み、`std::atoll` の結果を使う。文字列全体の数値妥当性、末尾文字、範囲は検証されない。`atoll` が 0 を返す文字列（未設定時以外の空文字、非数値文字列、先頭が `0` の文字列など）は cap 0 になる。したがって `0`, `0anything`, `true`, `false`, 空文字はいずれも 0 として扱われ、ミラーを開始しない。`12`, `12MiB`, ` 12` は先頭の数値部分が 12 となり 12 MiB の上限になる。符号は受け付けられ、負値を拒否する検査はない。通常の範囲内の整数について、上限値自体はミラー対象が尽きるか cap に達するまで使われる（`engine/sycl/src/program/generate.cpp:5475-5488`; `engine/sycl/src/core/gguf_expert_source.cpp:123-135`）。

| 条件 | 未設定 | 有効になる値（例） | ミラーしない値（例） |
|---|---|---|---|
| ミラー上限の計算 | Linux の `/proc/meminfo` から得た `MemAvailable` が 4 GiB を超えればその差、そうでなければ 0。UMA では後述の既定値に置き換わる | `1`, `12`, `12MiB`（数値接頭部を MiB として使う） | `0`, `0anything`, `true`, `false`, 空文字（`atoll` が 0） |
| UMA (`device_unified_memory()`) 上での既定値 | `--expert-cache auto` なら 0。明示 cache なら `uma_free_bytes(0)` から `--vram-reserve-mib` 分を引いた量（下限 0） | 明示した非ゼロ値はその値を cap とする | 明示した 0 相当値は cap 0 |

負値は入力検証されず、`atoll` 結果を unsigned に変換してから 20 bit 左シフトするため、負の数を「0」や負の cap と解釈する保証はない。`atoll` の範囲外入力も Strata 側で検査されない。これらの値は指定しないこと（`engine/sycl/src/program/generate.cpp:5475-5485`）。

## 有効になる条件

- SYCL の `strata generate` 実行で `--stream-experts` が有効、expert source が GGUF (`srcp == &gguf_src`)、かつ `--expert-cache` の解決後の値が正であること。`--stream-experts` はネイティブ (IQ) pack と `--native SHARD1` も要求する（`engine/sycl/src/program/generate.cpp:2002-2005,4711-4725,5431-5432`）。
- その cache に入らなかった expert があること。multi-GPU layer split ではミラー候補は最初の GPU が担当する layer までに限られる（`engine/sycl/src/program/generate.cpp:5435-5446`）。
- cap が正であること。cap 0 なら `mirror` は呼ばれず、正でも上限に入らない候補はミラーされない（`engine/sycl/src/program/generate.cpp:5486-5488`; `engine/sycl/src/core/gguf_expert_source.cpp:128-136`）。
- UMA の `--expert-cache auto` では、変数が未設定の場合の既定 cap は 0。明示した `--expert-cache` なら、未設定時の cap は UMA pool の残りから `--vram-reserve-mib` を引いた値になる。環境変数が設定されていれば、どちらも `atoll` 由来の明示 cap が使われる（`engine/sycl/src/program/generate.cpp:5477-5485`）。
- UMA、auto cache、単一 GPU、`--stream-experts`、GGUF、`STRATA_VERIFY_NO_HOST` が非空かつ `0` 以外、cache が全 expert を保持しない条件では、非ゼロの変数値が起動前の拒否判定を通す条件の一つになる。ここで 0 相当値は「明示的なミラーあり」とは数えられない（`engine/sycl/src/program/generate.cpp:5210-5226`）。
- `STRATA_VERIFY_NO_HOST` が非空かつ `0` 以外で、ミラー後も miss が残ると終了コード 2 で拒否する。UMA の場合は RAM と headroom の数値を含む `REFUSED` を出し、他の場合は「neither in VRAM nor mirrored」とする `REFUSED` を出す（`engine/sycl/src/program/generate.cpp:5508-5532`）。
- prefill borrow が許可され `--prefill-chunk > 0`、単一 GPU の場合、`STRATA_LEND_MIRROR` に従って cache tail の expert も miss の後ろにミラー候補として追加される。追加候補は通常の未 cache expert より cap を先に消費しないよう後ろに置かれる。UMA ではこの変数が未設定なら default 0、非 UMA では cache slot の 10%（最大 1200）が既定である。`STRATA_MIRROR_MIB` はこれらを含む全候補の cap となる（`engine/sycl/src/program/generate.cpp:5447-5467`）。

## 実行時の詳細

変数は起動時設定として `generate.cpp` 内で2回読み取られ、static cache には保存されない。1回目は UMA auto-cache の事前拒否判定向けで、`std::atoll(...) != 0` だけを確認する。2回目はミラー準備時に cap を計算する。後者では未設定時の cap を `/proc/meminfo` の `MemAvailable - 4 GiB`（最低 0）から始め、UMA かつ未設定なら pool の空き容量に応じた値に置き換える。明示値は MiB を byte に変換し、UMA でも同じ cap として扱う。CLI にこの cap を直接上書きする引数はなく、`--expert-cache` は候補となる cache miss を変える別の設定である（`engine/sycl/src/program/generate.cpp:5210-5214,5468-5485,2002-2005`）。

ミラー候補は profile 順に未 cache expert を集め、profile にない expert を追加する。layer split では最初の GPU の範囲のみを対象にする。`GgufExpertSource::mirror` は候補を順に追加し、各 blob の 256-byte 丸めサイズを cap 内に収め、次の blob が入らなくなった時点で打ち切る。確保・GGUF 読み取り失敗時にはエラー文字列を返し、呼び出し側は `mirroring the experts missing from VRAM: ... (they stay on the SSD)` を stderr に出して処理を続ける。成功時はミラー数・容量・所要時間を stderr に出して device 用アドレス表を作る（`engine/sycl/src/core/gguf_expert_source.cpp:123-135,153-205`; `engine/sycl/src/program/generate.cpp:5486-5505`）。

ミラーできなかった expert があり、`STRATA_VERIFY_NO_HOST` が有効なら拒否経路に入り、終了コード 2 となる。通常の host fallback を許す場合、ミラーされない expert はこの処理では SSD 上に残る（`engine/sycl/src/program/generate.cpp:5488-5492,5508-5532`）。この変数は CUDA/HIP 経路では読まれず、生成実行以外のサーバー要求ごとに再評価する処理もない（候補名の実装参照は `engine/sycl/src/program/generate.cpp:5211,5475` のみ）。

## ログと測定値

- ミラー確保または GGUF 読み取りの失敗: `strata generate: mirroring the experts missing from VRAM: <error> (they stay on the SSD)`（`engine/sycl/src/program/generate.cpp:5488-5492`）。
- 成功: `strata generate: <n> of <total> experts missing from VRAM (+ <n> in the prompt loan's slots) mirrored in pinned host memory (<GiB> GiB, <seconds> s); the GPU reads them over PCIe`（`engine/sycl/src/program/generate.cpp:5493-5497`）。
- `STRATA_VERIFY_NO_HOST` 有効時に未ミラー miss が残る場合は、該当する `REFUSED` を stderr に出して終了コード 2（`engine/sycl/src/program/generate.cpp:5511-5532`）。
- ソースにこの変数の性能測定値はない。設計資料の測定記録は本調査では挙動の根拠に用いていない。

## 根拠

- `engine/sycl/src/program/generate.cpp:5210-5226` — UMA auto-cache と `STRATA_VERIFY_NO_HOST` の事前拒否判定。
- `engine/sycl/src/program/generate.cpp:5431-5488` — SYCL stream 条件、miss 候補、既定値と cap の計算。
- `engine/sycl/src/program/generate.cpp:5488-5532` — mirror 呼び出し、ログ、未ミラー miss の拒否。
- `engine/sycl/src/core/gguf_expert_source.cpp:123-205` — cap による候補選択、pinned host allocation、ミラー記録。
