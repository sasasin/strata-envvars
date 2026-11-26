# `STRATA_KV_PREFETCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prefill 中、システム RAM にある次の QSA 層の K/V prefix を、現在層の計算と重ねて GPU の staging pool に転送する opt-in です。通常は対象層に到達してから同じ転送を始めます。有効時も既存の staging pool を再利用し、追加の K/V pool は作りません。生成処理や KV の格納内容を変更する設定ではなく、転送を始める時期と stream/event の使い方を変えます。`engine/src/prefill/prefill.cpp:4597-4620,5248-5261`、`engine/sycl/src/prefill/prefill.cpp:3031-3075,3578-3592`

## 値と判定

CUDA/HIP 系の prefill と SYCL prefill は、初回の `Prefill::run_impl` で `std::getenv` し、値が存在すれば `std::atoi(value) != 0` を有効とします。未設定は false、空文字や数値に変換できない文字列は `atoi` が 0 を返すため false です。数値の後ろは検査しないので `1anything` は true、`0anything` は false。先頭空白や符号は `atoi` の変換規則に従い、変換結果が非 0 なら負数も true です。`true` / `false` という単語の特別扱い、大文字小文字の検証、範囲検証、clamp はありません。`engine/src/prefill/prefill.cpp:4260-4264`、`engine/sycl/src/prefill/prefill.cpp:2709-2713`

| 読み取り箇所 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA/HIP・SYCL の `run_impl` | OFF | `1`, `-1`, `1abc` | 空文字, `0`, `0abc`, `abc` |
| Linux HIP の load 時先行確保 | 確保しない | `1`, `-1`, `1abc` | 空文字, `0`, `0abc`, `abc` |

CLI や設定ファイルによる上書きはありません。`--kv-resident` 等は K/V がストリーミング状態になるかを決めますが、prefetch flag の値自体は変えません。`engine/src/program/generate.cpp:3906-3908,5028-5032`

## 有効になる条件

- `STRATA_KV_PREFETCH` が上記の規則で有効であること。主処理の判定値は関数内 `static const bool` に保存され、プロセス内で最初に実行された `run_impl` の値を以後の prefill でも使います。実行中に環境を変更しても反映されません。`engine/src/prefill/prefill.cpp:4260-4264`、`engine/sycl/src/prefill/prefill.cpp:2709-2713`
- QSA 層の K/V が streaming (`kv_mode == 1`) であること。通常は `--kv-resident N` で VRAM resident window を全 context より小さくします。CUDA 系では実装上の最小 window も適用されます。`--kv-resident` を省略しても、SYCL の単一 GPU 経路では context が VRAM に収まらない場合に自動 streaming を選ぶ分岐があります。full-resident の場合、prefetch stream は用意されても対象 prefix がなく、転送は起きません。`engine/src/core/layer.cpp:738-755,807-824`、`engine/sycl/src/program/generate.cpp:4234-4277`
- 現在の prompt chunk の開始位置 `p0` が 0 より大きく、担当範囲 `LB..LE` の先に `kv_mode == 1` の QSA 層があること。関数は次の streamed QSA 層を最大一つ先行させ、単一 staging pool の先行転送が消費されるまで次を発行しません。したがって prompt の最初の prefix (`p0 == 0`) は先行コピーしません。`engine/src/prefill/prefill.cpp:4594-4624`、`engine/sycl/src/prefill/prefill.cpp:3027-3038,3084-3085`
- ソースで確認できる主な実装は CUDA/HIP 系の `engine/src/prefill/prefill.cpp` と SYCL の `engine/sycl/src/prefill/prefill.cpp` です。Metal 固有の prefill 実装でこの変数を読む箇所は見つかりませんでした。Linux HIP ではさらに、`load_moves().first_prompt_buffers && T > 0` の場合に load 時点で stream/event を先行確保します。これは失敗しても無視され、request 側で必要なリソースを再試行します。`engine/src/prefill/prefill.cpp:2633-2650`

## 実行時の詳細

有効時、CUDA 系は非同期 copy stream と release/ready event を作り、SYCL は専用 queue と event を用意します。次の streamed QSA 層の host prefix `[0, p0)` を既存 staging pool へ転送し、現在層の最後の reader が pool を解放した後にコピーを始めます。ready event を次層の compute stream / queue で待ってから、通常の層処理と同じ staging pool の内容を使います。`p0 <= 0`、先読み対象の streamed QSA 層なし、または prefetch が無効なら、層に到達した時点で従来の stream から `kv_stage_from_host` を呼びます。`engine/src/prefill/prefill.cpp:4597-4620,5248-5261`、`engine/sycl/src/prefill/prefill.cpp:3031-3075,3578-3592`

CUDA 系は prefill 完了時に prefetch stream を同期し、SYCL は queue を wait します。early return 時も RAII drain が同期します。正常完了時、両実装とも prefetch が有効なら `strata KV prefetch: %lld layer prefixes, single existing staging pool` を stderr に出します。実際に先行転送した prefix 数が 0 の場合も表示されます。`engine/src/prefill/prefill.cpp:4273-4277,7934-7940`、`engine/sycl/src/prefill/prefill.cpp:2735-2740,5707-5727`

## ログと測定値

stream/event の作成失敗、pool release、コピー enqueue、ready event wait、最終同期に失敗すると prefill は false を返し、それぞれ `prefill: KV prefetch stream/events`、`prefill: releasing KV staging pool`、`prefill: enqueueing KV prefetch`、`prefill: waiting for KV prefetch`、または `prefill: KV prefetch stream: ...` をエラー文字列に設定します。SYCL queue/event 作成時の例外は `exc.what()` とソース位置を stderr に出して `exit(1)` する経路もあります。`engine/src/prefill/prefill.cpp:4265-4271,4606-4616,5253-5258,7934-7938`、`engine/sycl/src/prefill/prefill.cpp:2714-2732,3031-3082,3583-3588,5707-5727`

Strata の RTX 4090 測定記録では、Engine 0.1.40、`--kv-resident` なしの条件で `STRATA_KV_PREFETCH=1` を付けた prompt throughput は 32,768 token で 3136.3→3001.8 tok/s (-4.3%)、131,072 token で 3118.5→3052.3 tok/s (-2.1%)（各 n=3）でした。記録自身が「KV が VRAM に収まり重ねる転送がない」条件の測定と説明しており、現行 HEAD の性能測定ではありません。現行コードをこの依頼では build・実行しておらず、現行 HEAD での速度差は確認していません。`docs/bench-results/2026-10-06-community-rtx4090-opt-ins/README.md:3-12,24-47`

## 根拠

- 候補名のソース全参照: `engine/src/prefill/prefill.cpp`（load 時先行確保と実行時読み取り）、`engine/sycl/src/prefill/prefill.cpp`（実行時読み取り）。他のソースでの実読込はありません。
- 実際の streaming mode 判定: `engine/src/core/layer.cpp:738-755,807-824`。
- CLI 値の parse と負値拒否: `engine/src/program/generate.cpp:3906-3908,5028-5032`。
- SYCL の自動 streaming 条件と RAM 不足時のログ: `engine/sycl/src/program/generate.cpp:4234-4277`。
- CUDA/HIP 系の flag 読み取り、先読み、ready wait、完了ログ: `engine/src/prefill/prefill.cpp:4260-4277,4594-4624,5248-5261,7934-7940`。
- Linux HIP load 時の best-effort 先行確保: `engine/src/prefill/prefill.cpp:2633-2650`。
- SYCL の flag 読み取り、先読み、ready wait、完了ログ: `engine/sycl/src/prefill/prefill.cpp:2709-2740,3027-3085,3578-3592,5707-5727`。
- 関連設計説明と測定条件: `docs/KV_PREFETCH.md:1-18`、`docs/bench-results/2026-10-06-community-rtx4090-opt-ins/README.md:3-47`。設計説明は歴史的 validation と区別し、現行の実行時挙動はコードを根拠にしました。
