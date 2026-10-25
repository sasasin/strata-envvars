# `--vram-segment-mib`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--vram-segment-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数。parser は `atoll` で変換する |

## 役割

`--vram-elastic` が使う expert cache の VRAM セグメントサイズを MiB で指定します。これ単独では elastic cache を有効にしません。elastic モードでは cache を複数の物理セグメントとして確保し、`--serve` 中の `VRAM <reserve_mib>` コマンド（server の `POST /v1/vram`）による縮小・再拡張に使います（`src/program/generate.cpp:907-909`, `src/program/generate.cpp:6282-6298`, `include/strata/core/expert_cache.hpp:117-124`）。

## 使い方

```sh
strata --serve --vram-elastic --vram-segment-mib 512 ...
```

`...` はモデル等、このエンジン実行に必要な引数を表します。例の `512` はソース上の既定値です（`src/program/generate.cpp:613-616`）。

## 値と既定値

- 省略時は `512` MiB です（`src/program/generate.cpp:616`）。
- オプションに値が続かない場合、parser は `--vram-segment-mib needs a value` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2416-2420`）。
- parser は値を `std::atoll` で読み、厳密な整数形式・全桁消費・上限を検証しません。したがって、無効文字列を含む値を安全な入力として扱わないでください。複数回指定した場合は、parser のループで後の値が代入されます（`src/program/generate.cpp:2604-2605`）。
- `--vram-elastic` が有効な条件で値が `64` MiB 未満なら、起動をエラー終了させるのではなく elastic 機能を無効化し、stderr に `strata generate: --vram-elastic is off: --vram-segment-mib is below 64` と出します（`src/program/generate.cpp:6284-6295`）。
- このオプションだけを指定し `--vram-elastic` を付けない場合、値は保存されますが `set_segment_bytes` に渡されず、通常の cache 割当には作用しません（`src/program/generate.cpp:2604-2605`, `src/program/generate.cpp:6284-6298`）。

## 実行時の動作

elastic 条件を満たすと、値を MiB からバイトへ変換して expert cache に設定します（`src/program/generate.cpp:6297`）。`ExpertCache` は要求サイズを CUDA driver の割当粒度に切り上げて実際の segment size とし、expert cache の仮想アドレス範囲を予約して初期セグメントを map します（`src/core/expert_cache.cpp:297-321`, `src/core/expert_cache.cpp:323-345`）。したがって、実際の粒度は指定値と完全一致するとは限りません。

segment は `VRAM` コマンドを受けたときに必要な単位で解放・再 map されます。縮小時は末尾の segment を解放し、再拡張時は先頭側から map します。segment の丸めにより、要求された空き VRAM と実際の解放量は一致しないことがあります（`src/core/expert_cache.hpp:137-146`, `src/core/expert_cache.cpp:384-445`, `src/program/generate.cpp:11197-11204`, `src/program/generate.cpp:11221-11245`）。このサイズ指定自体が自動的に VRAM を返すわけではありません。

## 適用条件と副作用

- `--vram-elastic` が必要です。elastic は `--serve`、単一 GPU、helper cache なしの場合に限り有効です。layer split、別 GPU の helper cache、または 64 MiB 未満では起動時に機能を無効化して理由を stderr に出します（`src/program/generate.cpp:6282-6295`）。
- HIP build では NVIDIA 専用として機能を無効化します（`src/program/generate.cpp:6290-6295`）。CUDA driver/GPU が仮想メモリ管理を提供しない場合、cache の segmented allocation は `ExpertCache: --vram-elastic needs the driver's virtual memory management, which this GPU or driver does not offer` で失敗します（`src/core/expert_cache.cpp:303-311`）。
- elastic 時は expert cache の確保・解放単位と、VRAM 再拡張時の段階を変えます。縮小で cache から外れた expert は CPU miss として処理され、他のモデル重みや KV 等すべての VRAM が返却されるわけではありません（`src/program/generate.cpp:11197-11204`, `include/strata/core/expert_cache.hpp:117-123`）。
- 正の大きな値に対する MiB からバイトへのシフトや driver の上限について、CLI parser 側に明示的な範囲検証はありません。上限値はソースから確認できないため、ここでは保証しません（`src/program/generate.cpp:2605`, `src/program/generate.cpp:6297`）。

## 出力とエラー

値が 64 MiB 未満のときの警告付き無効化は上記の通りです。CUDA VMM 非対応や segmented cache の確保失敗は、初期化先でエラー文字列となります。初期 segment を map できない場合は `ExpertCache: cudaMalloc failed: segment ... of the segmented cache could not be allocated` を返します（`src/core/expert_cache.cpp:333-342`）。cache 確保が最終的に失敗すると `strata generate: <エラー>` を stderr に出して終了コード `1` で終了します（`src/program/generate.cpp:6362-6390`）。これらは `--vram-segment-mib` 固有の parser 拒否ではありません。

未知の引数は `unknown argument: ...` を stderr に出し、usage を表示して終了コード `2` になります（`src/program/generate.cpp:2786-2793`）。

## 根拠

- 索引上の位置と scope: `docs/cli/README.md:1128-1136`, `docs/cli/README.md:1307-1310`。`strata-engine` のルート引数 parser は `src/program/generate.cpp` と説明されています。
- 既定値・help の説明: `src/program/generate.cpp:613-616`, `src/program/generate.cpp:907-909`。
- parser と不足値の処理: `src/program/generate.cpp:2416-2420`, `src/program/generate.cpp:2604-2605`。
- elastic の条件、値の設定と警告: `src/program/generate.cpp:6282-6298`。
- segmented cache の CUDA VMM 要件と実割当: `src/core/expert_cache.cpp:297-345`, `src/program/generate.cpp:6362-6390`。
- resize が扱うセグメントと cache の制約: `include/strata/core/expert_cache.hpp:117-146`, `src/core/expert_cache.cpp:384-445`, `src/program/generate.cpp:11197-11245`。

調査範囲は上記 commit の checkout にある parser、cache 実装、索引です。実バイナリの `--help`、Release artifact、各 GPU/driver での実行結果は確認していません。
