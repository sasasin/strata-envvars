# `STRATA_INK_NO_CAND`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

## 役割

Inkling2 のサーバーループが backend の candidate rows を使うかを制御する診断・A/B 用スイッチです。値が `'1'` で始まると candidate rows を無効にし、従来の全 logits 行を backend から受け取って host 側で sampling します。候補経路が使われる場合も、全行経路の場合も、生成 token は同じ seed なら同じになると sampler のコメントに記されています。直接の制御箇所は `ink2::run_serve_loop` です。`ink_main.cpp` では `mode_serve` の場合に同関数へ進み、直接 CLI 生成モードは別経路です（`engine/src/inkling2/ink_serve.h:89-92, 494-505, 1166-1169`; `engine/src/inkling2/ink_main.cpp:1093-1100`）。

## 値と判定

`std::getenv` の戻り値が非 null で、先頭文字が `'1'` のときだけ `cand_ok` が false になります。文字列全体の比較や数値変換はしません。

| 条件 | unset | 設定時に candidate rows を無効にする値 | candidate rows を無効にしない値 |
|---|---|---|---|
| Inkling2 serving loop | `cand_ok` は true | `1`, `10`, `1anything` など、先頭が ASCII `'1'` | 空文字、`0`, `true`, `false`, ` 1`, `x1` など、先頭が `'1'` でない文字列 |

大文字小文字・空白・後続文字の妥当性検査はありません。空文字は設定済みですが無効化条件には一致しません。したがって未設定と同じく candidate rows を許可します（`engine/src/inkling2/ink_serve.h:504-505`）。

## 有効になる条件

- `ink_main.cpp` の `mode_serve` 経路で `run_serve_loop` が呼び出される必要があります。直接 CLI 生成はこの変数を読むループを通りません（`engine/src/inkling2/ink_main.cpp:1093-1100`）。
- 値が未設定または先頭が `'1'` 以外でも、candidate rows は `n_want > 0` かつ `backend.supports_candidates()` の場合に限り候補になります（`engine/src/inkling2/ink_serve.h:1063-1067`）。
- いずれかの対象 slot に sampling penalty があると、その step 全体で candidate rows を使いません。penalty は任意の logit を変え得るため、全行が必要です（`engine/src/inkling2/ink_serve.h:1066-1068`; `engine/src/inkling2/ink_serve.h:127-132`）。
- 共通 backend の既定実装は candidate rows 非対応です。対象 commit で `supports_candidates()` を true に override する実装は CUDA backend のみ確認でき、HIP / SYCL / Metal の backend には override がありません。そのため、それらはこの変数が未設定でも全行経路です。`docs/SETTINGS.md:400` は NVIDIA と AMD を対象として列挙していますが、この checkout の backend 実装で candidate rows 対応を確認できるのは CUDA backend だけです（`engine/src/inkling2/ink_backend.h:126-136`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:681-695`）。
- CUDA backend が初期化済みで candidate scratch の確保に失敗し、候補行がまだ生成されていない場合は、現在の step を全行経路で処理し、以降の step も `cand_ok = false` として全行経路に切り替わります（`engine/src/inkling2/cuda/ink_cuda_backend.cu:683-695`; `engine/src/inkling2/ink_serve.h:1071-1081`）。

## 実行時の詳細

値は `run_serve_loop` に入ったときに一度 `cand_ok` へ読み込まれます。ループ中に環境変数を再読込する箇所はなく、同ループ実行中の環境変更は反映されません。設定値は CLI 引数や別の環境変数で上書きされません（`engine/src/inkling2/ink_serve.h:494-506`）。

各 step で logits を要求する行数を数え、candidate rows が許可され、backend が対応し、penalty が不要なら `forward_batch_cand` を呼びます。それ以外は全 logits 行のバッファを確保して `forward_batch` を呼びます。候補経路は各行の上位最大 128 件と finite flag を backend から受け取り、host 側で `sample_candidates` を使います。全行経路は `sample_logits` を使います（`engine/src/inkling2/ink_serve.h:1063-1081, 1143-1169`; `engine/src/inkling2/ink_backend.h:118-136`）。

候補 scratch 不足での切り替え自体に専用ログはありません。forward が失敗し、KV growth failure として処理できない場合は serving protocol に `ERR fatal GPU error: ...` を出して return 1 します。KV growth failure で該当 slot を終了できる場合は stderr に `[ink-serve] slot ... ended at ... tokens: ...` を出し、要求を `length` 理由で終了します（`engine/src/inkling2/ink_serve.h:1083-1100`）。

## 根拠

- 候補名の直接参照と値判定: `engine/src/inkling2/ink_serve.h:504-505`。
- serving と CLI の経路分岐: `engine/src/inkling2/ink_main.cpp:1093-1100`。
- 候補経路の条件、penalty による抑止、scratch 不足時の全行 fallback: `engine/src/inkling2/ink_serve.h:1063-1081`。
- backend API の既定非対応と CUDA backend の対応: `engine/src/inkling2/ink_backend.h:118-136`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:681-695`。
- 候補／全行からの sampling と fatal error / KV growth の観測経路: `engine/src/inkling2/ink_serve.h:1143-1169, 1083-1100`。
