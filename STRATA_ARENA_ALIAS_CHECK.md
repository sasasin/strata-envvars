# `STRATA_ARENA_ALIAS_CHECK`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

SYCL エンジンで 32 MiB 以上のデバイス割り当てに対して行う、割り当て範囲のページ alias 検査と再配置を有効・無効にする。検査は 64 KiB ごとに異なるタグを書いて読み戻し、書いた位置と別の位置が同じページに対応していないかを調べる。alias があれば割り当てを解放し、拡大する spacer の後ろで取り直す。

対象は `strata::malloc_device_guarded` を通る SYCL 側の割り当てだけである。CUDA/HIP の実装にはこの環境変数の読み取りがない。

## 値と判定

| 環境変数の状態 | 判定 |
| --- | --- |
| 未設定 | 有効 |
| 空文字 | 有効 |
| 値の先頭文字が `0` | 無効（例: `0`, `0abc`） |
| それ以外 | 有効（例: `1`, `false`, `abc`, 空文字） |

整数や真偽値への変換、文字列全体の比較は行わず、`v[0] != '0'` だけで判定するため、大文字小文字は関係しない。値を読む関数内の `static const bool` に初回評価結果をキャッシュする。したがってプロセス起動後に値を変更しても、そのプロセス内の判定は更新されない。

## 有効になる条件

- `malloc_device_guarded` に渡すサイズが **32 MiB 以上**であること。32 MiB 未満、または環境変数の値が `0` で始まる場合は通常の `sycl::malloc_device` の割り当てをそのまま返し、alias 検査を行わない。
- `sycl::malloc_device` が null を返した場合も検査・再試行をせず、その null を返す。
- 実際に検査されるのはこの guarded allocator を使う SYCL 実行経路である。例として DeviceArena、expert cache arena、native dense/head、verify、MTP、generation、prefill の割り当てがこの関数を呼ぶ。expert cache は segmented/VMM 経路を選んだ場合にはこの allocator を通らない。

## 実行時の詳細

`arena_alias_guard_enabled()` が値を一度読み、`malloc_device_guarded()` は最初に `sycl::malloc_device` を呼ぶ。対象サイズで検査が有効なら、割り当て範囲の各 64 KiB ブロック先頭にブロック番号由来のタグを書き、別のカーネルで読み戻す。カーネル起動は一度に最大 `1 << 20` ブロックずつに分けられ、各チャンク後に queue を待つ。検査関数は alias のあるブロック数と最初の異常オフセットを返す。検査中に割り当て範囲へタグを書き込むため、元の内容は保持されない。この関数を呼ぶ時点でバッファ内容は初期化前である必要がある。

異常があれば stderr に `strata: WARNING: ... do not keep their own bytes ... allocating it again behind a ... MiB spacer` を出し、割り当てを解放してから `2, 4, 6, ... 16 MiB` の spacer を確保し、その後ろで同サイズを再確保して検査する。最大8回検査する。再試行後に通れば、移動回数が1回以上の場合に stderr へ `strata: ... is clean after ... move(s)` を出す。8回検査しても clean にならず最後の割り当てが null でなければ、`strata: WARNING: the ... still has aliased pages after 8 tries (STRATA_ARENA_ALIAS_CHECK=0 skips the check)` を出す。最後の再確保自体が失敗して null の場合は、この警告条件を満たさない。最終的な割り当て（null を含む）は device allocation map に登録され、呼び出し元へ返される。検査失敗だけを理由に割り当てを失敗扱いにしたり、例外終了したりする処理はこの関数にはない。

`docs/INTEL.md` は Arc Pro B70 の大きな expert-cache arena で見つかったページ alias の事例、32 MiB 以上の割り当てに対するこの検査、警告と再配置、および環境変数によるスキップを記述している。現行コードで確認できる制御内容は一致する。文書中の「起動時 under 0.5 s」はその資料に記載された測定であり、ここで再測定した値ではない。

## 根拠

- `sycl/include/strata/sycl_queue.hpp:163-203` — 64 KiB ごとのタグ書き込み・読み戻し、異常数と先頭オフセットの返却、対象範囲の内容が破壊されること。
- `sycl/include/strata/sycl_queue.hpp:207-211` — 変数の唯一のコード読み取り箇所、未設定を有効とする既定値、先頭文字 `0` のみ無効とする判定、および static cache。
- `sycl/include/strata/sycl_queue.hpp:256-288` — 32 MiB の閾値、通常割り当てへの迂回、8回の検査、2 MiB 刻みで増える spacer、stderr ログ、map 登録。
- `sycl/src/core/device.dp.cpp:405-417` — DeviceArena が guarded allocator で一括領域を確保する例。
- `sycl/src/core/expert_cache.cpp:635-652` — expert cache が segmented/VMM 経路でない場合に guarded allocator を使う箇所。
- `sycl/src/core/native_dense.cpp:249-360`, `sycl/src/core/native_head.cpp:54-216`, `sycl/src/core/verify.cpp:614`, `sycl/src/core/mtp.cpp:225-468`, `sycl/src/program/generate.cpp:2780-3239`, `sycl/src/prefill/prefill.cpp:327-1738` — その他の呼び出し箇所。
- `docs/INTEL.md:747-756` — B70 での alias 事例と資料上の説明・測定。
