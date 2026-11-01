# `STRATA_GDN_FUSE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP gfx12 の prompt GDN で、畳み込み（conv）と chunked recurrence をまとめて実行する経路を許可します。この変数だけでは経路を有効にせず、別変数 `STRATA_GDN_CHUNKED` が設定され、その `atoi()` 結果が 0 以外であることが必要です。`STRATA_GDN_FUSE` が未設定なら融合は許可され、設定されていて `atoi()` 結果が 0 なら融合を止めます。

## 値と判定

実装は `std::getenv()` の値を `std::atoi()` に渡し、結果が 0 かどうかで判定します。文字列全体の妥当性検査はありません。

| `STRATA_GDN_FUSE` | 判定 | 結果（`STRATA_GDN_CHUNKED` が有効な場合） |
|---|---|---|
| 未設定 | `nullptr` | 融合を許可 |
| 空文字 | `atoi("") == 0` | 融合を止める |
| `0`、`false`、数値で始まらない文字列 | `atoi()` が 0 | 融合を止める |
| `1`、`-1`、`2`、`1tail` など、先頭部分が 0 以外の整数 | `atoi()` が 0 以外 | 融合を許可 |

`atoi()` は先頭の空白と符号を許容し、数値部分の後ろにある文字は判定に使いません（例: `1tail` は許可、`0tail` は停止）。`true` のような非数値文字列は真として扱われません。オーバーフロー値の扱いは実装で別途定義・検査されていません。

## 有効になる条件

- HIP ビルドであること。呼び出し側は `STRATA_USE_HIP` の場合だけ融合関数を呼び、関数の実装も `__HIPCC__` 以外では常に `false` を返します。
- `STRATA_GDN_CHUNKED` が設定され、`atoi()` の結果が 0 以外であること。未設定、空文字、`0`、`false` などの場合は `STRATA_GDN_FUSE` の値にかかわらず融合しません。
- 現在の GPU が gfx12 WMMA 対応であること。
- prompt の token 数 `T` が 64 以上であること。gfx12 の下限 `kGdnW12MinT` は `kGdnWmmaMin` と同じ 64 です。
- recurrence 出力の stride が有効であること。`ld16 <= 0` は標準 stride に置き換えられ、最終的に 8 の倍数でなければ融合を見送ります。

条件を満たさないと融合関数は `false` を返し、呼び出し元は通常の `gdn_conv()` と `gdn_recurrence()` を呼びます。モデル内に GDN 層があり、prompt 処理の該当経路が実行されることも必要です。`STRATA_GDN_FUSE` による CLI 引数の上書きは実装されていません。

## 実行時の詳細

環境変数の判定は `gdn_fused_impl()` の最初の呼び出しで行われ、`static const bool` に保存されます。同じプロセスで後から環境値を変更しても再評価されません。ここでは `STRATA_GDN_CHUNKED` と `STRATA_GDN_FUSE` を同時に読みます。

融合が選ばれると、conv と recurrence の間に通常の FP32 `h` バッファを使わず、conv 出力を再利用される `hbuf` に FP16 で保持し、gfx12 の prep/scan を実行します。kernel launch 後の `check("gdn_conv_recurrence_fused")` は CUDA/HIP の直近エラーを確認し、エラー時には stderr に `prefill gdn_conv_recurrence_fused: <error string>` を出してプロセスを終了コード 1 で終了します。

融合を止めた場合や GPU・長さ・stride の条件が合わない場合、専用の警告やログは出さず、呼び出し側が conv と recurrence の通常経路へ進みます。

## 根拠

- `src/prefill/kernels.cu:2160-2168` — HIP gfx12 融合実装と `STRATA_GDN_CHUNKED` / `STRATA_GDN_FUSE` の読み取り・`atoi()` 判定、長さの下限。
- `src/prefill/kernels.cu:2169-2181` — stride の補正・境界検査、現在の GPU の取得、gfx12 判定。
- `src/prefill/kernels.cu:2183-2197` — 融合 kernel の起動とエラーチェック。
- `src/prefill/kernels.cu:102-105,3090-3099` — GPU エラー時の stderr / 終了動作と、HIP 以外で `false` を返す実装。
- `src/prefill/prefill.cpp:3816-3831,6948-6958` — HIP での呼び出し、`false` の場合の通常 conv / recurrence への fallback。
- `include/strata/prefill/kernels.hpp:78-83` — 公開関数の適用範囲についての宣言コメント。
