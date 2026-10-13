# `STRATA_PREFILL_RING`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

プロンプト処理（prefill）で、VRAM に常駐していない expert の重みを読み込む device staging ring の slot 数を指定します。1 slot は expert blob 1 個分です。大きい ring は先読みコピーを進められますが、その分の device memory を使います。`Prefill::init` が確保する ring と、自動 chunk / cache-loan のサイズ計算が使う ring 数の両方に反映されます。

CUDA/HIP 実装と SYCL 実装の双方に同名の読み取りがあります。設定値は関数呼び出しごとに `getenv` で取得され、環境変数の有無や数値を static cache していません。

## 値と判定

値全体の検証はせず、C の `std::atoi` で先頭の整数部分を読みます。空文字、数字で始まらない文字列は 0 として扱われ、数字の後ろは無視されます。空白や符号などの扱いも `atoi` に従います。

| 設定 | `atoi` の結果 | 結果（stream-all が使える場合） |
|---|---:|---|
| unset | — | 下記の優先順位で自動決定 |
| 空文字、数字で始まらない文字列、`0`、負数など | 0 以下 | 最小 16 slot に丸める |
| `8` または `8abc` など、結果が `STAGE` (= 8) | 8 | routed-only staging の 8 slot |
| 1〜15（8 を除く） | 1〜15 | 16 slot に丸める |
| 16〜上限 | 16〜上限 | 指定数を使用 |
| 上限超過 | 上限超過 | backend / kernel 条件ごとの上限に丸める |

数値変換が 8 になる設定値は、明示的な routed-only staging として特別扱いされます。例えば `8trailing` も 8 slot の staging です。`0` は ring を無効にせず、16 slot になります。大文字小文字の比較はありません。

未設定時の基本優先順位は次の通りです（上位が優先）。

1. HIP で `STRATA_HIP_WMMA` の先頭文字が `1`、かつ `STRATA_PREFILL_RING` が unset、かつ split override がない場合は、chunk が `STRATA_PREFILL_STREAM_MIN`（既定 1024）以上なら 96 slot、それ未満なら 8 slot。
2. `STRATA_SPLIT_RING` から設定された layer-split override。
3. `--prefill auto` の byte-budget 計算で設定された ring budget（budget が有効で、chunk が `small_max` を超える場合）。
4. 通常既定値: streamed expert の pinned-RAM share が 90% 以上なら、fused 条件を満たす Q2_0 pack は 1024、それ以外は 384。share が 90% 未満なら 96。

HIP の WMMA 判定は最初の判定時に static cache されます。ほかの設定値や通常既定値は、ring 数を計算するたびに評価されます。明示値がある場合は、HIP の WMMA 特例より先に通常の値処理へ進み、split override / byte-budget よりも優先します。

## 有効になる条件

- chunk が `STRATA_PREFILL_STREAM_MIN` 以上である必要があります。未満では ring 数の計算結果は通常 8 slot になり、expert 全体を先読みする stream-all ring は使いません。`STRATA_PREFILL_RING=8` はこの条件を越える chunk でも 8 slot staging を明示します。
- SYCL では、別変数 `STRATA_PREFILL_STREAM_ALL` が `1` でない限り、VRAM に常駐しない (layer, expert) pair の割合が 10% 以上なら ring 数は 8 に戻ります。`STRATA_PREFILL_STREAM_ALL=1` ならこの割合による抑制を越えて stream-all を許可します。したがって、SYCL で `STRATA_PREFILL_RING` を大きくしても stream-all 条件が不成立なら大きな ring にはなりません。stream-all 環境値は先頭文字が `1` かで判定されます。
- CUDA/HIP 側には、この SYCL の nonresident-share / `STRATA_PREFILL_STREAM_ALL` 抑制分岐はありません。
- ring 上限は `ring_cap()` によります。Q2_0 の fused path では 1024、その他は通常 512 です。native pack では全 layer の format が fused 対応するかなどで fused-ring 条件が決まります。明示値もこの上限を越えません。
- `STRATA_SPLIT_RING` の値は layer-split 起動時に `Prefill::set_ring_override()` を通じて反映されますが、`STRATA_PREFILL_RING` が設定されていれば本変数の値が優先されます。API のコメントと `ring_slots()` の分岐がこの優先を定めます。
- `--prefill auto` の chunk / lend 計算では、`STRATA_RING_BYTES` が有効な場合に ring byte budget が考慮されます。ただし明示された `STRATA_PREFILL_RING` は、auto scan が計算した ring より優先し、その ring 分のバッファが収まる chunk に制限します。

## 実行時の詳細

`Prefill::init` は `ring_slots(T)` の結果を `m.ring` に取り、その個数分の `MAXBLOB()` byte device staging slot を確保します。所有バッファでは一つの連続 allocation にまとめ、借用領域では slot ごとに割り当てます。必要サイズ計算 `bytes_needed_impl` と `bytes_needed_no_ring` も同じ ring 数を含めるため、設定値はメモリ適合性と自動 chunk / cache loan の見積もりにも影響します。streamed expert の読み込み処理がこれらの slot を再利用します。

SYCL 実装では stream-all が有効かを `STRATA_PREFILL_STREAM_ALL` と nonresident share から追加判定し、通らなければ `STAGE` を返します。CUDA/HIP の WMMA 既定特例は `STRATA_HIP_WMMA` を先頭文字で判定し、同じく unset の `STRATA_PREFILL_RING` でのみ働きます。

serve の layer-split / resident-RAM 経路では、起動時に chunk と ring slot 数を `strata serve: lend sizing: ... (ring R slots at chunk C)` のログに出します。コード上、ring が貸出領域の計算・確保を超えると「do not fit」等の適合失敗につながり得ます。環境値そのものに対する専用の警告ログは確認できません。

## 文書との照合

`docs/AMD_HIP_PERFORMANCE.md` は、gfx1100 の測定構成で `STRATA_PREFILL_RING=96` を使った例を示しています。`docs/AMD_HIP.md` は gfx12 WMMA と組み合わせた 96 slot の構成と、9070 XT の特定条件で既定 384 slot より 96 slot が速かった測定を記載しています。これらは明記された GPU / model / chunk 条件での測定で、一般的な最適値を示すものではありません。

`docs/MULTI_GPU.md` は `STRATA_SPLIT_RING` による split ring override と、`STRATA_PREFILL_RING=384` を明示したときの lend sizing が変わらない例を記しています。ソースでは `STRATA_PREFILL_RING` が split override より優先されるため、この説明と整合します。

## 根拠

- `src/prefill/prefill.cpp:277-299`: 環境値の `atoi`、HIP WMMA 特例、override / budget / 既定値、最小値・上限、chunk 閾値。
- `sycl/src/prefill/prefill.cpp:195-227`: 同じ値決定と SYCL の stream-all / nonresident-share 条件。
- `src/prefill/prefill.cpp:211-250, 242-275`: split override、fused 判定、ring cap と pinned-share 由来の slot 数。
- `include/strata/prefill/prefill.hpp:79-90, 106-124`: API の条件、override / budget の意味、INFO 表示向け ring 解決 API。
- `src/prefill/prefill.cpp:1287-1303, 1836-1895`: 実 ring の設定・allocation、および必要 byte 数への算入。
- `src/program/generate.cpp:6386-6455`: `--prefill auto` の byte-budget と明示 ring を含む chunk / loan 計算。
- `src/program/generate.cpp:6702-6717, 7241-7254`: split override の設定順と serve の lend sizing ログ。
- `sycl/src/program/generate.cpp:5945`: SYCL の nonresident share 設定元。
- `docs/AMD_HIP_PERFORMANCE.md:13-34`, `docs/AMD_HIP.md:337-349`, `docs/MULTI_GPU.md:158-174`: 測定例および split との説明。
