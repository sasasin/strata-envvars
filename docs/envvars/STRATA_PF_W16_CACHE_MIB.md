# `STRATA_PF_W16_CACHE_MIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA の `strata::prefill::Gemm::native()` が量子化重みを FP16 に dequantize した結果を GPU メモリに保持し、同じ重みへの後続 GEMM で dequantize を省くための MiB 予算を指定する。キャッシュキーは重みポインター、型、行数、列数で、ヒット時は保持した FP16 重みで GEMM を行う。通常の非キャッシュ経路と同じ FP16 重みと積を使う設計だが、ここでは数値同一性を独立に検証していない。実装は `engine/src/prefill/gemm.cu` と `engine/include/strata/prefill/gemm.hpp` にある。`STRATA_PF_W16_CACHE_MIB` が設定されても、HIP 経路ではこのキャッシュブロック自体がコンパイルされない（`engine/src/prefill/gemm.cu:1587-1595,1644-1645`）。

## 値と判定

`std::getenv` で値の有無を調べる。値が大文字小文字を含め完全一致で `auto` なら自動予算を使い、それ以外の設定値は `std::atoll` で整数変換し、MiB（`1<<20` bytes）へ掛ける。したがって文字列全体の数値検証はなく、先頭の空白と符号を含む整数接頭部を変換し、後続文字は無視する。空文字や数字で始まらない文字列は 0 相当となる。正の予算だけがキャッシュを試すため、0・負数はキャッシュなし。`auto` 以外の文字列 `AUTO` は数値変換されて 0 相当となる。範囲外数値の扱いはコードで検証・制限していない（`engine/src/prefill/gemm.cu:1595-1615`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA、環境変数を明示 | `--batch >= 2` かつ Linux CUDA なら既定 16 GiB、空き 3 GiB を維持。それ以外は 0（OFF） | `1`, `2048`, `+2MiB`, `1foo`（それぞれ 1 MiB、2048 MiB、2 MiB、1 MiB の予算。数値接頭部の後ろは無視） | `0`, `-1`, 空文字, `false` |
| CUDA、明示値 `auto` | ― | `auto`（予算上限 16 GiB、空き 3 GiB を維持） | `AUTO`（0 相当） |
| HIP | ― | 該当なし | どの値もこのキャッシュ処理には使われない |

明示した値は unset 時の既定値より優先される。数値値では予算を指定しつつ空き 2 GiB を維持し、`auto` と unset 時の自動 ON では空き 3 GiB を維持する。MiB への換算値を GPU に割り当てられる総量へ clamp する処理はなく、実際に確保できるかは別途判定される（`engine/src/prefill/gemm.cu:1597-1615,1622-1627`）。

## 有効になる条件

- CUDA ビルドで `Gemm::native()` がキャッシュ判定ブロックまで到達すること。HIP では `#ifndef STRATA_USE_HIP` の範囲外となり、Metal ではこの CUDA `.cu` 実装を使わない（`engine/src/prefill/gemm.cu:1489-1491,1587-1595,1644-1645`）。
- `w16_budget_` が正であること。unset 時は `generate.cpp` が Linux CUDA ビルドで `o.batch >= 2` のときだけ自動既定を ON にする。`--batch` / `--slots` は同じ値を設定する CLI 引数（`engine/src/program/generate.cpp:4041-4042,9569-9574`）。明示値はこの既定を上書きする。
- `Gemm` に `side_scratch_` が設定されていないこと。`STRATA_DEQUANT_SIDE` は CUDA でプロセス内初回判定時に先頭文字が `1` なら有効となり、第2スクラッチが設定された場合、正の予算でもこのキャッシュ部分を通らず side-stream の dequant/GEMM 経路へ進む（`engine/src/prefill/gemm.cu:737-743,1617,1660-1678`; 設定箇所 `engine/src/prefill/prefill.cpp:2719-2723,2946-2948`）。
- 新規キャッシュ時に、その重みサイズ `N*K*2` が残予算内であり、`cudaMemGetInfo` が成功し、確保後にも設定された reserve より多くの VRAM が残って `cudaMalloc` が成功すること（`engine/src/prefill/gemm.cu:1618-1627`）。既存キーに一致すれば、追加確保なしで使う。
- キャッシュ節より前に `native()` の別経路が処理を完了しないこと。例として CUDA NVFP4 専用経路や、ビルド時 `STRATA_CUBLASLT_MXFP8` と形状・有効化条件を満たす MXFP8 経路は先に return し得る（`engine/src/prefill/gemm.cu:1539-1544,1545-1586`）。

## 実行時の詳細

設定値はプロセス全体で一度ではなく、各 `Gemm` インスタンスの `w16_budget_` が `-1` のまま初めてキャッシュ節に来た `native()` 呼び出しで読み取られ、そのインスタンスの budget/reserve に保存される。以後、同じインスタンスでの環境変更は読み直されない。別インスタンスは独立して初回判定する。unset の自動既定は `generate.cpp` から `Gemm` の静的 atomic へ設定される（`engine/include/strata/prefill/gemm.hpp:100-112`; `engine/src/prefill/gemm.cu:1595-1615`; `engine/src/program/generate.cpp:9569-9574`）。

新規項目は全行の FP16 dequantization を行って `w16_` に登録する。ヒットすると `f16()` でその重みを使い、通常の逐次 dequantize へ戻らずに `native()` を終了する。予算超過なら追加キャッシュをせず通常経路へ進む。空き VRAM 判定または `cudaMalloc` に失敗した場合も処理を失敗させず、stderr に一度だけ現在のキャッシュ量と reserve を出して以後の新規確保を止める。すでに確保した項目はインスタンス破棄時に `cudaFree` される（`engine/src/prefill/gemm.cu:1622-1643,746-748`）。通常の native prompt 投影から `Gemm::native()` が呼ばれる（`engine/src/prefill/prefill.cpp:3967-3972`）。

## ログと測定値

キャッシュ確保を試みた際に VRAM 判定または確保が失敗した場合、最初の一度だけ stderr に次の形式で出る（値は実行時に埋め込まれる）。予算が 0、side scratch により処理が迂回された場合、予算超過だけの場合にはこのログは出ない。

```text
strata prefill: FP16 weight cache %lld MiB (the card keeps %lld MiB free; STRATA_PF_W16_CACHE_MIB=0 turns it off)
```

Strata 資料 `docs/SETTINGS.md:441` はこの変数を `on / off`、`NVIDIA and AMD` と記載するが、現行ソースは MiB 数値と厳密な `auto` を受け付け、明示的な CUDA キャッシュ実装で、HIP には実装がない。この資料記述は現行実装と一致しない。速度・品質の測定値はここでは記載しない。

## 根拠

- `engine/src/prefill/gemm.cu:1489-1491,1587-1645` — native 経路、値の読み取り、予算・空き VRAM 判定、ログ、キャッシュヒット。
- `engine/include/strata/prefill/gemm.hpp:97-112` — キャッシュキーとインスタンス状態、自動既定。
- `engine/src/program/generate.cpp:4041-4042,9569-9574` — `--batch` / `--slots` と Linux CUDA の自動既定。
- `engine/src/prefill/prefill.cpp:2722-2723,2947-2948,3967-3972` — side scratch 設定および native 投影からの呼び出し。
- `docs/SETTINGS.md:441` — 記載内容との照合。
