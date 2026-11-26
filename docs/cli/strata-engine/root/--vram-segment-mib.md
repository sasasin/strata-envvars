# `--vram-segment-mib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root scope） |
| オプション | `--vram-segment-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数。`--vram-elastic` と併用する場合は 64 以上 |

## 役割

`--vram-elastic` が使う expert cache の物理 VRAM segment の要求サイズを MiB で指定する。segment 化した cache は server の request 間 VRAM resize で縮小・再拡張できる。これ単独では elastic cache を有効にしない。

## 使い方

```sh
strata --serve --vram-elastic --vram-segment-mib 256 <model.strata>
```

## 値と既定値

- 既定値は `512` MiB。
- parser は値を `std::atoll` で `int64_t` に変換する。専用の数値形式検査や上限検査は見当たらない。数値として読めない文字列は `atoll` の結果 0 となり、後述の elastic 下限条件に該当する。
- 値を複数回指定した場合は parser のループで後の値が同じフィールドを上書きする。
- `--vram-elastic` が有効な場合、64 MiB 未満（0、負値を含む）は受理されず、elastic が無効化される。64 MiB 以上についてソース上の上限は確認できない。
- segment の実サイズは CUDA driver の推奨割当粒度に切り上げられるため、要求値と実サイズは一致しない場合がある。

## 実行時の動作

root parser は値を `Options::vram_segment_mib` に格納する。expert cache の初期値は 512 MiB である。後段は `--vram-elastic` が指定された場合に限って、`--serve` であること、helper cache がないこと、値が 64 MiB 以上であることを確認する。条件を通ると `MiB << 20` で byte 数へ変換して ExpertCache に設定し、cache open 時に CUDA virtual memory management を使った segment 化 arena を構成する。segment 化は固定アドレス範囲を予約し、各 segment に物理割当を map する。通常の cache 割当（segment 要求値 0）は従来どおり単一 `cudaMalloc` である。

server は設定の `vram_elastic: true` で `--vram-elastic` を追加し、`vram_segment_mib` が正の整数で CLI 引数に未指定の場合に本オプションを engine 引数へ追加する。起動後の resize は `VRAM <reserve_mib>` / `POST /v1/vram` によって request 間に行われ、segment 境界に合わせて cache を縮小・再拡張する。segment 境界の解像度と、resize で解放・再取得できる単位にこの値が関係する。

## 適用条件と副作用

- 効果には `--vram-elastic` も必要。`--vram-segment-mib` だけを指定した場合、この値は cache の割当に使われない。
- elastic は `--serve` 用で、通常の非 serve 実行では有効化されず警告を出して無効化される。helper cache が他 GPU にある場合も同様。
- 現行 root parser は HIP build では elastic を NVIDIA 専用として無効化する。CUDA 側でも GPU/driver が virtual memory management を提供しない場合は ExpertCache の open が失敗する。
- cache の segment を縮小すると、解放範囲に入る resident expert は追い出され CPU miss になる。再拡張は空 slot から始まり、driver が追加 VRAM を確保できなければ grow が失敗する。アドレス範囲は保持される。
- SYCL 側にも同名 parser があるが、索引上の `strata-engine` root scope は `engine/src/program/generate.cpp`。SYCL parser の elastic 条件は layer split を無効化理由に含み、CUDA root と条件が異なる。SYCL 実行時の segment allocator 挙動はこの調査では確定していないため、CUDA root の説明をそのまま適用しないこと。

## 出力とエラー

- 値が不足すると `--vram-segment-mib needs a value` を stderr に出して exit code 2。
- `--vram-elastic` と併用して serve でない、helper cache がある、または値が 64 MiB 未満の場合、`strata generate: --vram-elastic is off: ...` を stderr に出し、elastic をオフにして続行する。
- CUDA driver の VMM 非対応、segment の予約・割当失敗などは cache open エラーになる。具体的な起動結果は GPU、driver、空き VRAM に依存する。

## 根拠

- `docs/cli/README.md:1036-1042,1229-1233` — `strata-engine` root scope と対象リンク。
- `engine/src/program/generate.cpp:964-968` — elastic の用途、segment 既定値。
- `engine/src/program/generate.cpp:4036-4038` — parser と整数変換。
- `engine/src/program/generate.cpp:3842-3847` — 値不足時の stderr と exit code。
- `engine/src/program/generate.cpp:9575-9591` — serve/helper-cache/下限/NVIDIA 条件、警告、MiB から bytes への変換。
- `engine/include/strata/core/expert_cache.hpp:119-148` — segmented arena、shrink/grow と slot の契約。
- `engine/src/core/expert_cache.cpp:415-464` — CUDA VMM 対応確認、粒度への切り上げ、segment の予約と map、割当失敗。
- `engine/src/core/expert_cache.cpp:503-575` — shrink/grow の失敗経路と live slot 更新。
- `terminal/serve/server.py:3751-3757` — server 設定から CLI 引数への追加条件。
- `terminal/serve/server.py:1284-1307,4991-5005` — VRAM resize の request 間動作と server 側の拒否条件。
- `engine/sycl/src/program/generate.cpp:2032-2034,5050-5067` — 同名 parser と SYCL 側の有効化条件。

調査制約: 安全に使える同一 revision の既存 engine binary を確認していないため `--help` は実行していない。性能や特定 GPU/driver での segment 粒度・resize 成功率は測定していない。
