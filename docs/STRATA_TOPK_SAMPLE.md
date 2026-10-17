# `STRATA_TOPK_SAMPLE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の QSA prompt top-k 選択で使う one-read sampling kernel を選択します。この kernel は各 query の score を一度走査して候補を絞り、閾値と tie の処理を行って block 順の ID を出力します。候補数が上限を超える場合や候補に含まれる cell が不足する場合は、その query を wide kernel に fallback します。通常の wide kernel を選ぶ場合と同じ ID を出す設計と、fallback 条件は実装コメントおよび kernel の処理に記載されています。

## 値と判定

`topk_sample_on()` 内の関数ローカル `static const int env` が `std::getenv` と `std::atoi` で値を一度だけ読みます。設定されている場合、`atoi(v) != 0` なら強制 ON、0 なら強制 OFF です。文字列全体の検証はしません。したがって未設定と明示設定は異なり、空文字、数字で始まらない文字列、`0` や `0suffix` は OFF、`1`、負の非ゼロ数値、`1suffix` は ON になります。`atoi` が解釈する先頭の空白や符号も適用されます。

| 値 | `topk_sample_on()` の判定 |
|---|---|
| unset | 下記の GPU / `STRATA_SM75_PERF` 判定へ進む |
| `0` または `atoi` 結果が 0 | OFF（任意の CUDA GPU で wide kernel を使う） |
| `atoi` 結果が非 0 | ON（任意の CUDA GPU で sampling kernel を許可） |

設定値はプロセス内で最初に `topk_sample_on()` が呼ばれた時に固定され、後から環境を書き換えても再評価されません。unset 時の GPU 判定結果も device index ごとにキャッシュされます。

## 有効になる条件

環境変数で ON になっても、次の dispatch 条件を満たす prompt 呼び出しに限り sampling kernel が起動します。

- CUDA 実装である（sampling kernel と判定関数は `__HIPCC__` でない場合のみコンパイルされる）。
- 選択幅を実際の block 数で制限できる `counted` 経路である。CUDA では `active_blocks > 0`、`active_blocks <= max_blocks`、`STRATA_TOPK_CAPACITY_GUARD` が未設定であることに加え、通常は `topk_active_turing_device()` が true（device の compute capability が 7.5）である必要があります。`STRATA_TOPK_ACTIVE_ANY` の先頭文字が `1` なら任意の CUDA GPU で counted を許可します。
- `nq <= TS_MAXQ`（4096）かつ `reach > 28672`。ソースコメントでは約 115K cells 超としている。
- `qsa_block_topk` の外側の wide-kernel dispatch 条件（`reach > fit`、または `STRATA_TOPK_STREAM` が有効な counted band で `reach > 22528`）にも該当する。`STRATA_TOPK_STREAM` は未設定なら有効、設定時は先頭文字が `0` 以外なら有効です。

値を設定した場合、sampling 自体はどの CUDA GPU でも値の ON/OFF が優先します。ただし非 Turing GPU では通常 `counted` にならないため、sampling に到達するには `STRATA_TOPK_ACTIVE_ANY=1` も必要です。unset の場合は、その device の compute capability が 7.5 で、さらに `STRATA_SM75_PERF` の `atoi` 結果が非 0 のときだけ `topk_sample_on()` が既定 ON です。その他の GPU は既定 OFF です。`STRATA_SM75_PERF` 自体も初回参照時にキャッシュされます（emulated compute capability の扱いは `sm75_default` の共通 helper に従います）。

HIP の経路ではこの環境変数による sampling dispatch はありません。prompt の active block 数が不明な decode/captured graph 経路も `counted` 条件を満たさず、この kernel には入りません。

## 実行時の詳細

`qsa_block_topk` は、wide kernel を使う領域で条件を満たすと、まず `block_topk_sample_kernel` を起動し、続けて `block_topk_wide_kernel<true>` を起動します。sampling kernel は query ごとに `g_tk_fail` を設定します。`n_kv <= width` なら全 ID を出して成功扱いにし、sampled bound が作れない場合、候補数が `TS_CAP`（4096）を超えた場合、または候補 cell 数が `width` に足りない場合は失敗扱いにします。後続の wide kernel は失敗した query だけを処理します。

環境値が OFF の場合、または dispatch 条件を満たさない場合は `block_topk_wide_kernel<false>` が選択されます。この環境変数専用のログ出力はありません。kernel launch 後の CUDA エラーは `qsa_block_topk: %s` を stderr に出し、プロセスを終了します。

## 根拠

- `src/kernels/cuda/qsa_select.cu:2476-2492`: 値の `atoi` 判定、明示値の優先、device ごとの Turing 既定判定。
- `src/kernels/cuda/qsa_select.cu:2317-2391`: sampling kernel の早期成功、候補生成、fallback flag の設定。
- `src/kernels/cuda/qsa_select.cu:855-860`: `g_tk_fail` と failed query のみを処理する wide kernel。
- `src/kernels/cuda/qsa_select.cu:1946-1961,2561-2584`: Turing device 判定、wide dispatch、`counted` と `reach` の条件、sampling / fallback kernel の起動、launch error の扱い。
- `include/strata/core/sm75_series.hpp:24-43`: `STRATA_SM75_PERF` の parse/cache と `sm75_default` の compute capability 条件。
- `docs/DETAILS.md:2246-2257`: Turing kernel 群と `STRATA_TOPK_SAMPLE` の位置付け。資料は Turing kernel 群を RTX 2080 Ti / CMP 50HX で測定したと記すが、この環境変数に対応する個別の数値や条件は示していないため、ここでは性能値を記載しない。
