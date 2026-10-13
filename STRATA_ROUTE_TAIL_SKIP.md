# `STRATA_ROUTE_TAIL_SKIP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

serve の verify window で、GPU キャッシュにない expert が、その window の全 token で router 上位10件の指定 rank 以降にだけ現れる場合、その expert をコピーも計算もしないようにします。該当する expert の出力行はゼロにされ、router weight の再正規化は行いません。そのため出力は変わり得ます。通常の single-GPU および layer-split 経路では、GPU に送る miss と CPU で計算する miss の両方を減らします。

## 値と判定

環境値は `src/core/expert_source.cpp` の `std::atoi` で整数に変換します。文字列全体の検証ではなく、`atoi` が読める先頭の整数部分を使います。したがって、先頭空白や符号を許し、数字の後ろの文字は無視します（例: `"  +7x"` は 7）。空文字、数字で始まらない文字列、変換後の 0、負数、10以上は無効値として 0 になります。1〜9 が有効な rank です。

| 環境値 | 変換後の rank | 結果 |
|---|---:|---|
| 未設定 | 0（ただし serve 起動時に既定値を設定する場合あり） | 無効 |
| `0`、空文字、`false`、整数に変換できない文字列 | 0 | 無効 |
| `1`〜`9` | 1〜9 | その rank 以降の miss を条件付きで skip |
| `10`以上、負数 | 0 | 無効 |

`atoi` は小数や末尾文字を厳密に検査しません。たとえば `7.5` は 7 として扱われます。値を読む結果はプロセス内の atomic に一度キャッシュされ、以後の環境変更では再評価されません。serve 起動処理は、既定値を適用する場合に `set_tail_skip_rank(7)` でそのキャッシュ値を上書きします。

## 有効になる条件

未設定時の自動既定値は 7 です。ただし serve 起動時に次をすべて満たす場合に限ります。

- 全 expert が VRAM に resident ではない。
- キャッシュ済み expert の割合がしきい値未満。
- `--batch` / parallel slots を使っていない。
- peer GPU tier を使っていない。
- CUDA build、または HIP build の gfx1200 / gfx1201（RDNA4）。

自動既定値を決めるキャッシュ割合のしきい値は CUDA で 90%、HIP の単一 GPU で 90%、HIP の layer split で 60% です。これは `STRATA_TAIL_SKIP_MAX_CACHED` が未設定または空文字の場合の既定値です。値がある場合は `std::atof(value) / 100.0` を使い、割合の判定は「キャッシュ済み数 >= しきい値 × 全数」です。明示的に `STRATA_ROUTE_TAIL_SKIP` を設定すると、このしきい値は自動既定値を抑制する判定にだけ使われ、明示値を無効化しません。

rank が正でも、実際の skip には `expert_pool_dispatch_multi()` の GPU plan 経路（`d.plan != nullptr` かつ window の entry 数が plan 容量内）が必要です。そこで `d.peer == nullptr` かつ helper GPU 数が 0 の場合にだけ適用し、resident expert は skip しません。SYCL 側の `expert_pool_dispatch_multi()` にはこの rank 判定がなく、`STRATA_ROUTE_TAIL_SKIP` の読み取りもありません。

コード上、明示値は自動既定値のアーキテクチャ・batch 条件を通らず `tail_skip_rank()` に渡ります。よって CUDA/HIP の対象 plan 経路では、未設定時の既定適用条件と明示値の適用条件を区別してください。たとえば batch は既定値の適用を止めますが、明示 rank が正なら起動時の ON ログは出せるうえ、dispatch 側にも batch の拒否判定がありません。`docs/DETAILS.md` は batch 時には適用しないと説明しており、この点は説明とコードの条件に差があります。

## 実行時の詳細

`expert_pool_dispatch_multi()` は verify window 内の各 routed expert をまとめ、expert ごとに window 中の最小 rank（0 始まり）を求めます。最小 rank が設定値以上、かつ当該 expert が GPU cache にない場合に、その expert の全 token 分の entry を `kind = -2` にします。これらは miss 数から差し引かれるため、PCIe staging 対象にも CPU prefetch / 計算対象にもなりません。後段で該当行を `memset(..., 0, ...)` して `tail_skipped` を加算します。条件は「全 token で rank が設定値以上」です。どれか1 token でもそれより上位に現れれば、その expert は通常処理されます。

起動時、正の rank で全 expert が resident でなければ `strata serve: STRATA_ROUTE_TAIL_SKIP=%d is ON...` を stderr に出します。未設定でキャッシュ割合がしきい値以上なら `... is off by default ...` の案内を出します。serve の集計ログでは `strata serve: route tail skip: %lld missed experts skipped (%lld entries) since the start` と累計を表示します。

## 文書・測定との照合

`docs/DETAILS.md` は CUDA での既定 rank 7、HIP gfx1200/gfx1201 での同じ既定値、rank 1〜9、rank 0 による無効化を説明しています。資料にある性能・品質の数字は同文書記載の環境と測定に限られます。たとえば RTX 3060 12 GB / IQ3_XXS と RTX A4000 16 GB / Q2_0 の5回 interleaved run では、既定値対 `=0` の全3 workload中央値がそれぞれ 1.156倍、1.129倍でした。同資料は回答が 0.1.41 と少し異なることも記載しています。これはコードから独立に再測定した値ではありません。

## 根拠

- `src/core/expert_source.cpp:3607-3622` — 環境変数の読み取り、`atoi`、1〜9への範囲制限、キャッシュと setter。
- `src/program/generate.cpp:1607-1617,8279-8315` — CUDA/HIP の既定条件、キャッシュ割合のしきい値、起動時の判定とログ。
- `src/core/expert_source.cpp:3664-3713,3720-3729,3825-3828,3853-3869` — plan 経路、rank 条件、miss の除外、ゼロ行と累計。
- `src/program/generate.cpp:12431-12433` — serve の累計ログ。
- `sycl/src/core/expert_source.cpp:2547-2615` — SYCL 側の実装に rank 判定がないこと。
- `docs/DETAILS.md:1609-1629,1631-1664` — 仕様説明、適用条件、測定結果。
