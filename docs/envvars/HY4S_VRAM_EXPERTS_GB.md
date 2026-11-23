# `HY4S_VRAM_EXPERTS_GB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL の HY4-Flash 実行経路で、GPU 0 の Section 4 expert VRAM cache に渡す予算を GiB 単位で指定する。`setup_experts_unified` がこの値をバイトへ変換して `SyVramExpertCache::init` に渡し、キャッシュ可能な expert 数を制限する。実際に確保できる slot 数は expert body の最大サイズ、作業領域、デバイス確保の成否にも制約されるため、指定値がそのまま確保量になるわけではない（`engine/src/hy4flash/sycl/sy_graph.h:123-142`、`engine/src/hy4flash/sycl/sy_vram_cache.h:691-750`）。

## 値と判定

読み取り箇所は `setup_experts_unified` の 1 箇所。CLI の `vram_experts_gb_arg` が 0 以上なら環境変数を読まず CLI 値を使う。CLI 値が負の場合に限り `std::getenv` で設定有無を判定し、設定されていれば `atof` の結果が正のときだけ GiB 値をバイトに変換する。正の値は `1073741824.0` 倍後に `size_t` へキャストされるため、小数部のバイトは切り捨てられる（`engine/src/hy4flash/sycl/sy_graph.h:127-139`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `--vram-experts-gb` が未指定または負 | 空き状況から自動計算。safe cap は総 VRAM の 94% で、割当済み bytes と呼び出し側の reserve を差し引き、256 MiB を超える余裕がなければ予算 0 | `atof` の結果が正の数。例: `1`、`1.5`、`1.5GiB`（数値部分の prefix を `atof` が読む） | 空文字、`0`、`0anything`、`true`、`false`、非数値、負数は `atof` 結果が正でないため予算 0 |
| `--vram-experts-gb` が 0 以上 | 該当なし。環境変数は参照されない | 該当なし。CLI の値を使う | 該当なし。CLI の値を使う |

文字列全体の妥当性検査や単位 suffix の検証はない。`atof` による数値 prefix の変換なので、たとえば `2GiB` は `2` として扱われ、空文字や数値で始まらない文字列は 0 になる。大文字小文字での比較は行わない。CLI 側も `atof` で変換し、初期値は `-1.0` なので、たとえば `--vram-experts-gb 0` は環境変数を上書きして GPU 0 の予算を 0 にする一方、負の CLI 値は環境変数への fallback を残す（`engine/src/hy4flash/sycl/sy_main.cpp:103-104,140-141`、`engine/src/hy4flash/sycl/sy_graph.h:129-139`）。

## 有効になる条件

- SYCL 版 HY4-Flash の `sy_main.cpp` / `sy_serve.h` が `setup_experts_unified` を呼ぶ経路で有効。SYCL は独立 backend として扱われ、通常の CUDA/HIP 経路にこの読み取り箇所はない（`engine/CMakeLists.txt:23-32`、`engine/src/hy4flash/sycl/sy_main.cpp:304`、`engine/src/hy4flash/sycl/sy_serve.h:283`）。
- `--vram-experts-gb` が 0 以上なら CLI が優先する。通常実行ではパーサーの初期値 `-1.0` が渡され、serve 実行でも同じオプション値が `ServeOpts` にコピーされる（`engine/src/hy4flash/sycl/sy_main.cpp:103-104,140-141,226-248`）。
- モデルの expert directory を `SyVramExpertCache::init` が読み取れることが必要。directory が空、または expert 数が 512 の倍数でなければ初期化に失敗する（`engine/src/hy4flash/sycl/sy_vram_cache.h:691-705`）。
- 値が正でも予算が cache の最小条件を満たさない場合、キャッシュはエラーなく無効になる。最大 expert body から丸めた `slot_bytes` の 41 倍未満、または作業領域 `ws_bytes` と 1 slot の合計以下なら初期化は成功扱いで早期 return する（`engine/src/hy4flash/sycl/sy_vram_cache.h:723-735`）。
- `HY4S_VRAM_STATIC` はこの予算を変えず、キャッシュが初期化された後の adaptive 動作だけを変える。値の先頭が `'1'` の場合 `adaptive_` は false になる（`engine/src/hy4flash/sycl/sy_vram_cache.h:795-797`）。
- peer GPU の予算は `HY4S_VRAM_EXPERTS_GB` ではなく CLI 引数からだけ計算される。CLI 引数が正ならその値を peer ごとの budget とし、それ以外は 0 を渡して peer 側の自動計算に任せる（`engine/src/hy4flash/sycl/sy_graph.h:144-152`、`engine/src/hy4flash/sycl/sy_peer.h:231-255`）。

## 実行時の詳細

通常実行では引数を解析してモデルと runner を初期化した後、`setup_experts_unified` を 1 回呼ぶ。serve 経路も `hy4s_serve_main` 内で trunk/KV/DFly2 初期化後、server 起動前に同じ helper を 1 回呼ぶ。したがって環境値は expert 配置の初期化時に読み取られ、既存のキャッシュのままプロセス環境だけを変更しても再評価されない（`engine/src/hy4flash/sycl/sy_main.cpp:103-104,255-307`、`engine/src/hy4flash/sycl/sy_serve.h:258-287`）。

環境変数が未設定で CLI も負なら、`dev_caps().global_mem` の 94% を safe cap とし、`dev_bytes_allocated() + reserve_vram_bytes` を差し引いて自動 budget を決める。閾値を満たさなければ budget は 0 のままになる（`engine/src/hy4flash/sycl/sy_graph.h:127-139`）。設定値または CLI 値から得た budget は、最大 body サイズから算出した slot 単位で切り詰められ、初期化時に Section 3 rank 順の experts が GPU 0 の cache slot に読み込まれる。残りは RAM または cold SSD 用 mask へ回される（`engine/src/hy4flash/sycl/sy_vram_cache.h:710-750`、`engine/src/hy4flash/sycl/sy_graph.h:173-200`）。

この helper の呼び出し側は通常実行では失敗時に stderr へ `experts: %s` を出して終了コード 1、serve では `ERR experts: %s` を protocol 出力して終了コード 1 を返す。予算不足だけなら `init` は成功し、エラー終了ではなく GPU 0 VRAM slot 0 として unified pool のログに現れる（`engine/src/hy4flash/sycl/sy_main.cpp:304-307`、`engine/src/hy4flash/sycl/sy_serve.h:283-286`、`engine/src/hy4flash/sycl/sy_graph.h:229-235`）。

## ログと測定値

slot を確保して初期化が最後まで進むと stderr に `[vram-cache] %zu slots across %zu slabs (<= %zu MiB/slab) = %.2f GiB (%.1f experts/layer, %.1f s, adaptive=%d, sg16+dedup+preq8)` を出す。予算が小さく早期 return した場合、この `[vram-cache]` 行は出ない。後続の unified pool 行 `[experts] unified pool (%s, %d thr, act=%s): %d GPU0 VRAM (%.2f GiB), ...` は、確保数 0 の場合も出る（`engine/src/hy4flash/sycl/sy_vram_cache.h:723-735,794-798`、`engine/src/hy4flash/sycl/sy_graph.h:229-235`）。

ファイルを開けない場合の `vram cache: cannot open ...`、短い read の `vram cache: short read` などは `err` に設定され、上記の通常実行または serve のエラー経路で表示される（`engine/src/hy4flash/sycl/sy_vram_cache.h:769-782`、`engine/src/hy4flash/sycl/sy_main.cpp:304-307`、`engine/src/hy4flash/sycl/sy_serve.h:283-286`）。この調査では build や実測はしていない。

## 根拠

- 環境変数と自動予算の分岐: `engine/src/hy4flash/sycl/sy_graph.h:127-142`
- CLI の既定値・変換・serve への受け渡し: `engine/src/hy4flash/sycl/sy_main.cpp:103-104,140-141,226-248`
- 通常実行での初期化順と失敗出力: `engine/src/hy4flash/sycl/sy_main.cpp:255-307`
- serve の helper 呼び出しと失敗出力: `engine/src/hy4flash/sycl/sy_serve.h:258-287`
- VRAM cache の最小予算、slot 確保、読み込み、ログ: `engine/src/hy4flash/sycl/sy_vram_cache.h:691-798`
- 残余 experts の RAM/cold SSD 分割と unified pool ログ: `engine/src/hy4flash/sycl/sy_graph.h:155-235`
- peer 予算の分岐と自動予算: `engine/src/hy4flash/sycl/sy_graph.h:144-152`、`engine/src/hy4flash/sycl/sy_peer.h:231-255`
