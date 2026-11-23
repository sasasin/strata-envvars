# `STRATA_I8_SM70`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の自前 int8 expert カーネルで、compute capability 7.0（Volta）向けの tile 調整と、一部形式の codebook grid を global memory から読む経路を有効にするスイッチ。値を有効にしても int8 expert カーネル自体を選択する設定ではなく、通常の prompt expert 経路の選択は `STRATA_EXPERT_I8` と build・モデル・chunk 条件で別に決まる。`STRATA_I8_SM70=0` は Volta 用調整を止める（`engine/src/kernels/cuda/iq_kernels.cu:6860-6875`, `7009-7023`）。

## 値と判定

`i8_switch_parse` は文字列全体を parse せず、先頭 byte だけを見る。環境変数未設定または空文字は `-1`（未指定）、先頭 byte が `'0'` なら `0`（無効）、それ以外の非空文字列は `1`（有効）となる（`engine/include/strata/kernels/i8_expert_rule.hpp:29-32`）。

| 条件（build / backend） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA build | `-1`。Volta ルールを許可し、デバイス判定へ進む | `1`, `true`, `false`, `yes`, ` 0`, `-1`。空でない文字列で先頭が `0` 以外 | `0`, `0anything`。先頭が `0` の文字列 |
| HIP build | HIP 分岐が常に `{}` を返すため、変数は読まず Volta ルールは無効 | 該当なし | 設定値にかかわらず無効 |

したがって `true` / `false` の意味解釈、大文字小文字、数値妥当性、空白除去、数値境界チェックはない。空文字は未設定と同じ扱い。たとえば `0anything` は無効だが、先頭に空白のある ` 0` は有効（`engine/include/strata/kernels/i8_expert_rule.hpp:29-32`, `engine/src/kernels/cuda/iq_kernels.cu:6866-6875`）。

## 有効になる条件

- CUDA build であり、現在のデバイスが compute capability 7.0 と判定される必要がある。他世代では switch が許可状態でも `I8Volta::on` は false となり、この Volta 用処理は行われない。HIP build は常に無効（`engine/src/kernels/cuda/iq_kernels.cu:6866-6887`）。
- `native_expert_i8` が実際に呼ばれる必要がある。通常の prompt 経路では `STRATA_EXPERT_I8=0` なら停止し、`STRATA_EXPERT_I8=1` なら対応可能な場合に選択を要求する。未設定時の CUDA は一般に class default ではないが、MMQ 無し build ではその int8 経路が既定となる。いずれも fused / staged 経路、共有・peer 条件、対応レイアウト、平均 256 entries 以上などの prompt 側条件が優先する（`engine/include/strata/kernels/i8_expert_rule.hpp:34-58`, `engine/src/kernels/cuda/iq_kernels.cu:6908-6915`, `engine/src/prefill/prefill.cpp:6351-6389`）。
- Volta 上でも、`STRATA_I8_TM` が正数で指定されると Volta 固有の「2 blocks/SM に収める tile への縮小」と平均 entries に基づく tile 5 選択は行わない。ただし tile 5 自体は `vo.on` および対応形式等に依存し、最後に shared-memory 上限による縮小が適用される。`STRATA_I8_SM70=0` では `vo.on` が false となり、Volta 用縮小、tile 5 条件、global-grid 選択がすべて無効となる（`engine/src/kernels/cuda/iq_kernels.cu:7004-7025`）。
- global-grid 経路は `vo.on` だけで一律に有効になるのではなく、`i8_gg_type` が対象とする gate/up 形式にも限定される（`engine/src/kernels/cuda/iq_kernels.cu:7018-7022`）。

## 実行時の詳細

環境値は `i8_volta()` の function-local `static const int sw` 初期化時に一度読み、以後プロセス内で cache する。したがって初回呼び出し後の環境変更は反映されない。HIP build ではコンパイルされた分岐が即座に空の結果を返すため `getenv` しない（`engine/src/kernels/cuda/iq_kernels.cu:6866-6875`）。

有効な CUDA 経路では、現在 device の番号を取得し、0〜63 の範囲外または取得失敗なら無効状態を返す。device ごとの shared memory / block reservation と Volta 判定は `per[64]` / `done[64]` に一度 cache される。compute capability 7.0 かつ multiprocessor shared memory が正の場合にのみ `on=true` となる。reserved shared memory の属性取得失敗時は CUDA error を読み捨て、reservation を 0 とする（`engine/src/kernels/cuda/iq_kernels.cu:6871-6887`）。

`native_expert_i8` は `STRATA_I8_TM` の値から通常 tile を決めた後、Volta ルールが有効で tile が明示指定されていない場合、shared memory と block reservation に基づいて tile を下げ、対象形式・平均 160 entries 以上なら Volta tensor-core tile 5 を選ぶ。別途 shared-memory per-block 上限に収まらない tile は小さくされる。大きな grid 形式の一部は `gg` を通じて global-memory grid 経路を使う（`engine/include/strata/kernels/i8_expert_rule.hpp:96-119`, `engine/src/kernels/cuda/iq_kernels.cu:7004-7029`）。

## ログと測定値

この変数の値や無効化理由を直接出すログはない。int8 expert 経路が選ばれたとき、prompt 側が一度だけ `strata: prompt experts on our own int8 dot-product kernels (STRATA_EXPERT_I8=1)`、または build / GPU の既定で選ばれた場合は `strata: prompt experts on our own int8 kernels (the default of this build or graphics card; STRATA_EXPERT_I8=0 goes back to the old kernels)` を stderr に出す。後者は `STRATA_PF_OWN_ONLY` build では出さない。このログは int8 経路を示すもので、Volta switch が有効だったこと自体は示さない（`engine/src/prefill/prefill.cpp:6443-6452`）。

カーネル起動後の CUDA エラーは `check` が `what: error` を stderr に出して `exit(1)` する経路があるが、環境値に固有の失敗文言はない（`engine/src/kernels/cuda/iq_kernels.cu:47-49`, `7044-7052`）。`docs/DETAILS.md` にはこの変数や Volta int8 経路の測定記載を確認できなかったため、性能値は記載しない。なお設定一覧 `docs/SETTINGS.md:384` は対象を「NVIDIA and AMD」とするが、実装の HIP 分岐は Volta ルールを無効にする。

## 根拠

- `engine/include/strata/kernels/i8_expert_rule.hpp:29-32,96-119` — 値の parser、Volta tile ルール。
- `engine/src/kernels/cuda/iq_kernels.cu:6860-6887` — CUDA/HIP 分岐、環境読み取り時期、device 判定・cache。
- `engine/src/kernels/cuda/iq_kernels.cu:6908-6915,7004-7029` — int8 route query と tile / global-grid への適用。
- `engine/src/prefill/prefill.cpp:6351-6389,6443-6452` — 通常の prompt 側選択条件と観測可能なログ。
- `engine/src/kernels/cuda/iq_kernels.cu:47-49,7044-7052` — CUDA error 時の stderr / 終了経路。
