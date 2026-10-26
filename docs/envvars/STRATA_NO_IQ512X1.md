# `STRATA_NO_IQ512X1`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数の意味は対象外。

## 役割

CPU の native expert 経路で、IQ3_XXS / IQ3_S の gate/up 行を1 tokenだけ計算するときに使う、AVX-512 の gather を使った exact-row カーネルを無効にします。無効化後は `native_gu_rows()` の後続の multi-token / ggml-cpu 経路が選ばれます。この変数は native expert の CPU pool (`pool.cpp` が `native_gu_rows()` を呼ぶ経路) に作用します。

## 値と判定

値の内容ではなく、環境変数が設定されているかだけを調べます。`getenv(...) == nullptr` のときだけ、このスイッチ自体は有効化を妨げません。

| 状態 | `STRATA_NO_IQ512X1` の判定 |
|---|---|
| 未設定 | 無効化しない |
| `1`、`0`、`false`、その他の文字列 | 無効化する |
| 空文字（設定済み） | 無効化する |

数値変換、先頭文字比較、大文字小文字比較はありません。したがって名前に `NO_` が付いていますが、`STRATA_NO_IQ512X1=0` も設定すれば対象カーネルを止めます。判定結果は `native_gu_rows()` 内の `static const bool` に保存されるため、最初の呼び出し後にプロセス環境を変更しても反映されません。

## 有効になる条件

未設定であることは必要条件の一つにすぎず、次の条件がすべて必要です。

- 実行 CPU で `cpu_avx512_ok()` が真で、別変数 `STRATA_NO_IQ512` も未設定であること。`STRATA_NO_IQ512` が設定されていると、AVX-512 経路全体のフラグ `avx512` が偽になります。
- 別変数 `STRATA_IQ_GATHER` の設定から `iq512_gather_on()` が真になること。この設定は空でない値なら `atoi(value) != 0`、未設定または空文字なら `cpu_gather_fast()` の結果を使います。
- `nt == 1` かつ `nt < native_gu_mt_min(f.gu_type)` であること。`STRATA_IQ_MT_MIN` が1など、multi-token カーネルへ1 tokenを送る設定では、この exact-row 分岐には入りません。
- gate/up 型が `18` または `21`（ソースコメント上の IQ3_XXS / IQ3_S）で、`f.tail_off == 0` であること。
- `x512_one_ok()` が、その型についてこのビルドの ggml-cpu dot と Strata の AVX-512 exact-row の結果がビット単位で一致すると確認すること。

いずれかの条件を満たさない場合、この変数の有無による差はありません。なお `STRATA_NO_IQ512X1` は `avx512` フラグ自体を変更しないため、対応する複数 token の IQ AVX-512 カーネルには直接影響しません。

## 実行時の詳細

`native_gu_rows()` は、条件を満たす場合に gate と up の行を `iq512x_rows()` で処理して SwiGLU を計算し、その呼び出しから戻ります。無効化された場合や条件不成立の場合はこの早期 return を通らず、後続のカーネル選択へ進みます。通常は `nt >= mt_min` なら対応する IQ AVX-512 multi-token カーネルが選ばれ、それ以外や対応条件外では最終的に ggml-cpu の `vec_dot` を使うループへ進みます（trellis 型など別の専用分岐に該当する場合を除く）。

`x512_one_ok()` は型ごとに初回確認の結果を map に保存します。ggml-cpu の比較関数がない、対象型をサポートしない、または bitwise 結果が違う場合は `false` となり、差が見つかった場合は stderr に `strata: the 512-bit exact one-token rows of type %d differ from this ggml-cpu's dot: not used` を出します。このチェック自体は対象環境変数の値を読みません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:42-73` — 型ごとの bitwise 比較、結果のキャッシュ、差異時の stderr。
- `src/kernels/cpu/native_expert.cpp:296-303` — native gate/up 行関数、AVX-512 経路の CPU 条件と `STRATA_NO_IQ512`。
- `src/kernels/cpu/native_expert.cpp:336-353` — 対象型、`nt`・tail 条件、`STRATA_NO_IQ512X1` の設定有無判定と exact-row 実行。
- `src/kernels/cpu/native_expert.cpp:355-424` — 分岐後の multi-token / ggml-cpu fallback。
- `src/kernels/cpu/iq_avx512.cpp:38-45,601-605` — `STRATA_IQ_GATHER` 判定、および gather と対象型の実装条件。
- `src/kernels/cpu/pool.cpp:1200-1235` — native expert gate/up モードから `native_gu_rows()` を呼ぶ箇所。

`docs/DETAILS.md` を確認しましたが、この変数固有の値判定や適用条件の記載は見当たりません。性能値はこの文書では主張しません。
