# `STRATA_PREFILL_MMQ`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prompt の expert 計算で、通常の MMQ（CUDA/HIP 系）または Strata の fused int8 / FP16 expert 経路（SYCL 系）を選ぶ実行時スイッチ。モデルの prompt expert の重み形式・層構成・利用可能な kernel によっては、この値が有効でも対象経路が使われず、別経路へ進む。CUDA/HIP と SYCL では値の解釈が異なるため、同じ文字列を全 backend 共通の boolean として扱えない。主な実装は `engine/src/prefill/prefill.cpp` の `mmq_plan()` と `engine/sycl/src/prefill/prefill.cpp` の `i8_mode()` / `mmq_plan()`。`STRATA_PREFILL_MMQ` という build macro は実行時環境変数とは別で、MMQ kernel の有無を示す条件コンパイルに使われる（`engine/src/prefill/prefill.cpp:1923-1925,2026-2037`、`engine/sycl/src/prefill/prefill.cpp:97-102`）。

## 値と判定

| 実行経路 | 未設定 | 設定値の判定と例 |
|---|---|---|
| CUDA/HIP 系、MMQ build | 通常は `mmq::built()` が真なら MMQ plan を作る。例外は下記の P100 既定。 | `std::atoi` の結果が 0 なら MMQ plan を無効化し、非 0 なら有効。空文字、`0`、`00`、`0anything`、`true`、空白だけは 0。`1`、`2`、`-1`、`1suffix`、先頭空白の後の `1` は非 0。全体の数値妥当性や大文字小文字は検査しない。符号・空白は `atoi` の規則に従う。 |
| CUDA/HIP 系、MMQ なし build（`STRATA_PF_OWN_ONLY`） | `fused::built()` が真なら Strata 所有の fused plan を許可する。 | 同じく `atoi(e) != 0` が条件。`0` と `atoi` が 0 になる文字列は plan を無効化し、それ以外は fused plan を許可する。MMQ 自体を有効化する値ではない（`engine/src/prefill/prefill.cpp:2026-2037`）。 |
| SYCL | Battlemage かつその queue で kernel が利用可能なら `auto`（値 2）、それ以外は FP16（値 0）。 | `STRATA_PREFILL_MMQ` が未設定または空なら `STRATA_PF_I8` を参照し、それも未設定または空なら上記既定。非空値の先頭が `a` / `A` なら `auto`（後続文字は検査しない）。それ以外は先頭から続く十進数字を読み、0 は FP16、非 0 は int8。したがって `0`, `00`, `0junk`, `off`, `-1`, 空白始まりは 0、`1`, `2`, `1junk` は int8、`auto`, `Auto`, `anything` は auto。大文字小文字は `auto` の先頭文字だけ区別せず、残りは見ない（`engine/sycl/src/prefill/prefill.cpp:333-345`、`engine/sycl/include/strata/prefill/esimd_moe.hpp:39-50`）。 |

CUDA/HIP 系では未設定と空文字を区別する。未設定だけが P100 の特例既定を許し、空文字は `atoi("") == 0` のため明示的な無効値として扱われる。SYCL の primary 名は未設定・空文字のどちらも alias `STRATA_PF_I8` にフォールバックする（同上）。

## 有効になる条件

- CUDA/HIP 系の MMQ 経路には MMQ kernel が build 済みであることが必要。`mmq_plan()` は値が非 0 でも `mmq::built()` が偽なら MMQ plan を作らない。対象 layer の gate/up と down の形式が `mmq::fits()` を満たさない場合、その layer は MMQ ではなく、条件が合えば fused 経路、そうでなければ FP16 経路になる（`engine/src/prefill/prefill.cpp:2026-2042,2048-2074`）。
- MMQ なし build では、非 0 は `fused::built()` の有無を越えて kernel を作る設定ではない。ビルド済みの Strata fused 経路の plan を許可する条件であり、pack / layer / chunk ごとの対応条件は別に適用される（`engine/src/prefill/prefill.cpp:2031-2042,2063-2067`）。
- CUDA の `STRATA_EXPERIMENTAL_SM60` build で全可視 GPU が compute capability 6.0 の場合、未設定なら P100 の prompt expert 既定は FP16。`STRATA_MMQ_WS`、`STRATA_EXPERT_NIBBLE`、`--peer-device` のいずれかが有効ならこの既定は適用されず、明示的にこの環境変数を設定した場合も P100 既定を上書きする。HIP と `STRATA_EXPERIMENTAL_SM60` なしの build ではこの特例は false（`engine/src/prefill/prefill.cpp:1988-2024`、`engine/include/strata/prefill/gp100_prompt_default.hpp:15-27`）。
- P100 特例が選んだ FP16 経路では、`STRATA_PF_FEWROWS` が未設定または空の場合に few-row 経路の既定も変わる。明示値は先頭文字が `0` なら off、それ以外なら on（`engine/src/prefill/prefill.cpp:7182-7187`、`engine/include/strata/prefill/fewrows.hpp:24-28`）。
- SYCL の int8 経路は `i8::available(queue)`、native pack、Hadamard fold が gate/up と down にないこと、対象形式（gate/up type 21 / 18 / 22、down type 20 / 42）、形状 `n_ff=640`, `n_embd=2560` を満たす場合に限られる。MMQ がその layer を使う場合、または XMX2 専用経路が選ばれる場合はこの int8 経路を使わない（`engine/sycl/src/prefill/prefill.cpp:4772-4780`）。`=1` はこれらの条件を外さない。明示 `auto` も測定した crossover による group ごとの選択で、利用可能形式・shape 条件を外さない（同ファイル `4862-4872`）。
- SYCL で primary 名が unset / empty のときだけ `STRATA_PF_I8` が値の供給元になる。primary に非空値があれば alias は参照されない（同ファイル `333-336`）。
- `STRATA_EXPERT_NIBBLE` が有効な CUDA 起動では、`STRATA_PREFILL_MMQ` が設定され `atoi` が 0 になると nibble の競合理由になる。nibble はその起動で無効化され、GGUF block の slot を維持する警告が出る（`engine/include/strata/core/expert_nibble.hpp:277-287`、`engine/src/program/generate.cpp:5468-5489`）。
- SYCL 用 `engine/sycl/serve/strata-sycl.sh` は空でない `STRATA_*` 値をコンテナに渡すため、`STRATA_PREFILL_MMQ=0` も渡される。空値は wrapper が渡さない（`engine/sycl/serve/strata-sycl.sh:33-43`）。

## 実行時の詳細

CUDA/HIP の `mmq_plan()` は最初の呼び出しで `static const MmqPlan` を生成する。そこで読んだ値と model の expert layout から layer ごとの MMQ / fused 対象、fallback、scratch の大きさを決め、後続の prefill chunk で再利用する。したがってこの plan の初回生成後に環境を変更しても plan は再計算されない（`engine/src/prefill/prefill.cpp:2026-2042`）。`layers_all_fused_only()` と `plain_pack_all_fused()` にも直接の `getenv` 判定があり、呼び出しのたびに値を読む（同ファイル `392-405,516-524`）。

CUDA/HIP の通常経路では `atoi(e)==0` により plan の `on` が false になり、MMQ plan は fallback として扱われる。対象 layer の expert 計算は既存の FP16 経路などに進む。MMQ build がない場合には `on` は fused kernel の有無で決まり、同じ 0 判定が Strata fused plan を止める（`engine/src/prefill/prefill.cpp:2031-2042,2050-2074`）。この変数は prompt の expert 計算経路を切り替える。数値出力への影響や生成 token が同一になるかは、調査したソースだけから一般化できない。

SYCL では `i8_env()` / `i8_mode()` が呼ばれるたびに環境を参照し、`mmq_plan()` は CUDA/HIP と同様に static plan を一度作る（`engine/sycl/src/prefill/prefill.cpp:333-350,1255-1281`）。`auto` は queue と expert 形式ごとの crossover を初回に測定または cache file から読み、group の平均 rows/expert が crossover 未満なら int8、そうでなければ FP16 chain を選ぶ（同ファイル `949-979,4862-4872`）。int8 kernel が false を返す場合や例外を投げる場合は FP16 chain に戻る。例外時は `g_i8_failed` が立ち、そのプロセスの以後の int8 選択を止める（同ファイル `338-344,4910-4921`）。

## ログと測定値

CUDA/HIP の `STRATA_PREFILL_MMQ` 単独について、常時表示される有効・無効ログは確認できない。manifest が有効なら `mmq_plan()` が prompt experts の path と理由を manifest に記録し、無効理由は build に MMQ がない場合、P100 既定、または `STRATA_PREFILL_MMQ=0` として区別される（`engine/src/prefill/prefill.cpp:2043-2047,2082-2088`）。

SYCL では int8 が有効なとき stderr に `strata: int8 prompt experts are on (%s); STRATA_PREFILL_MMQ=0 turns them off`、実際に fused int8 DPAS products を使う最初の group で `strata: prompt experts on the fused int8 DPAS products (STRATA_PREFILL_MMQ=%s)` を出す（`engine/sycl/src/prefill/prefill.cpp:1416-1419,4880-4886`）。形式ごとの適用可否ログ、workspace / format fallback、kernel launch 失敗時の文言も同ファイル `4782-4787,4910-4921` にある。対象変数について条件を一般化できる benchmark 値は記載しない。

## 根拠

- `engine/src/prefill/prefill.cpp:392-405,516-524,1988-2037,2048-2088,7182-7187`
- `engine/include/strata/prefill/gp100_prompt_default.hpp:15-27`
- `engine/include/strata/prefill/fewrows.hpp:24-36`
- `engine/include/strata/core/expert_nibble.hpp:277-287`
- `engine/src/program/generate.cpp:3408-3441,5468-5489`
- `engine/sycl/src/prefill/prefill.cpp:97-102,333-350,949-979,1255-1281,1416-1419,4772-4787,4862-4921`
- `engine/sycl/include/strata/prefill/esimd_moe.hpp:39-50`
- `engine/sycl/serve/strata-sycl.sh:33-43`
