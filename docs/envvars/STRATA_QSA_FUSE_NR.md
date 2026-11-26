# `STRATA_QSA_FUSE_NR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA/HIP の QSA prompt 処理で、K・query・indexer query の RMS norm と rotary embedding（RoPE）をそれぞれ一つの `rms_rope_rows` kernel に融合するかを選ぶ。既定は融合 ON。OFF にすると K と indexer query は `rms_rows` の後に `rope`、query はさらに先行する `split_q` を含む別々の kernel に戻る。融合 kernel のコメントは置き換える処理と同じ算術・結果ビットを意図すると説明しているが、この文書では実行測定や全モデルでの同一性を独自に確認していない（`engine/src/prefill/prefill.cpp:1017-1018,5242-5247,5309-5321`; `engine/src/prefill/kernels.cu:2531-2539`).

この分岐は QSA の K 投影後、Q 投影後、および indexer Q 投影後に適用される。QSA を含まない層や、この prompt 経路を実行しない処理では、この設定による分岐は起きない（`engine/src/prefill/prefill.cpp:5222-5247,5309-5321,9346-9367,9414-9426`）。

## 値と判定

`qsa_fuse_nr()` は初回呼び出し時に `std::getenv` で値を読み、値が未設定でない場合に先頭文字 `e[0]` が `'0'` かどうかだけを判定する。文字列全体の parse、数値変換、空白除去、大文字小文字変換はしない（`engine/src/prefill/prefill.cpp:1026-1028`）。

| 条件 | 判定 | 例 |
|---|---|---|
| 未設定 | ON | unset |
| 空文字 | ON（値は設定済みだが `e[0]` は終端文字 `\0`） | `STRATA_QSA_FUSE_NR=''` |
| 先頭文字が `0` | OFF | `0`, `00`, `0anything`, `0 ` |
| 先頭文字が `0` 以外 | ON | `1`, `true`, `false`, `True`, ` 0`, ` 1`, `anything` |

したがって `false` や先頭空白付きの `0` も OFF にはならない。OFF を指定する条件は値の先頭が文字 `0` であることだけ。別の環境変数や CLI 引数による優先・上書きはこの判定にはない（同 `qsa_fuse_nr()` 定義）。

## 有効になる条件

- 読み取り箇所は CUDA/HIP 共有 GPU engine の `engine/src/prefill/prefill.cpp`。CMake では `STRATA_ENABLE_CUDA OR STRATA_ENABLE_HIP` の場合にこの GPU engine が定義され、その prefill library に `prefill.cpp` と `kernels.cu` が含まれる（`engine/cmake/strata_gpu_engine.cmake:6-8,482-488`）。
- 実行中の層が QSA であること。コードは QSA 層の K/Q/indexer-Q 投影の後でこの設定を参照する（`engine/src/prefill/prefill.cpp:5222-5247,5309-5321,9346-9367,9414-9426`）。モデルに QSA 層がなければ参照されない。
- 同じ関数は通常の chunked prompt 処理と `run_impl` 側の QSA prompt 処理の双方で使われる。どちらも同じ設定判定で融合または分割経路を選ぶ（`engine/src/prefill/prefill.cpp:5242-5247,5309-5321,9363-9367,9414-9426`）。
- Metal 実装はこの環境変数を読まない。Metal 側の `rms_rope_rows` stub は呼ばれた場合 `missing("strata::prefill::rms_rope_rows")` に渡す（`engine/metal/src/engine/stubs_0291.cpp:21-25`）。
- ソース上、この設定のための OS、GPU 世代、モデル状態、CLI オプションによる追加条件や fallback は確認できない。QSA prompt 経路へ到達しない場合は単に判定箇所を通らない。

## 実行時の詳細

`qsa_fuse_nr()` 内の関数ローカル `static const bool` が最初の呼び出しで初期化されるため、プロセス環境の変更はその初回評価後に反映されない。起動時に無条件で読むのではなく、最初に該当する QSA prompt 前処理が呼ばれた時点で読み取る。キャッシュ値はその後の同プロセス内の各 QSA 層・各呼び出しに使われる（`engine/src/prefill/prefill.cpp:1026-1028,5242-5247,5309-5321`）。

融合 ON では K の行（2 heads、dim 256）、Q の行（query と gate を含む投影出力から query 部分を直接読み、24 heads、dim 256）、indexer Q の行（4 heads、dim 128）ごとに `rms_rope_rows` を呼ぶ。query は融合時に `split_q` を別途呼ばず、関数の入力 stride で query 部分を読む。OFF では K/indexer Q は norm と RoPE の二段、Q は `split_q`・norm・RoPE の三段になる（`engine/src/prefill/prefill.cpp:5242-5247,5309-5321`; kernel の stride／行処理は `engine/src/prefill/kernels.cu:2538-2545,2549-2580`）。後続の K/V append や query の利用は両方の分岐の後に続く（`engine/src/prefill/prefill.cpp:5248-5308,5316-5325`）。

融合 kernel の API は `T <= 0` なら何もせず戻り、`dim` が 64..256 の範囲外なら stderr に `prefill rms_rope_rows: dim %lld is outside 64..256` を出して `exit(1)` する。RoPE scaling が無効なら `prefill rope: invalid rope scaling: %s` を出して `exit(1)` する。通常の QSA 呼び出しで渡す dim は 256 または 128（query の head size は `kHeadDim`）である（`engine/src/prefill/kernels.cu:3555-3566`; 呼び出し側 `engine/src/prefill/prefill.cpp:5243,5310,5318`）。kernel launch 後は `check("rms_rope_rows")` を呼ぶ（`engine/src/prefill/kernels.cu:3567-3578`）。

## ログと測定値

QSA prompt 処理の最初の該当箇所で、一度だけ stderr に次の形式を出す。第一の `on/off` がこの変数による norm + RoPE の判定で、第二の値は別設定による attention gate の状態である。

```text
strata prefill: QSA layers: norm + rope in one pass on, attention gate in the attention epilogue off
```

`on` / `off` の部分は実行時状態で置換される。ログは環境変数自体を独立に検査するものではなく、初回実行時にキャッシュ済みの `qsa_fuse_nr()` の結果を表示する（`engine/src/prefill/prefill.cpp:5545-5551`）。Strata の `docs/DETAILS.md` と `docs/QSAROWS.md` にこの設定の測定値は見つからず、ソースコメントにも条件付きの数値測定値はない。設定一覧には NVIDIA/AMD 向け「on / off」として掲載されている（`docs/SETTINGS.md:456`）。

## 根拠

- 値の読み取りと cache: `engine/src/prefill/prefill.cpp:1026-1028`
- 融合と分割の実行経路: `engine/src/prefill/prefill.cpp:5242-5247,5309-5321,9363-9367,9414-9426`
- 融合 kernel の動作・制限・失敗経路: `engine/src/prefill/kernels.cu:2531-2580,3555-3578`
- CUDA/HIP build 範囲: `engine/cmake/strata_gpu_engine.cmake:6-8,482-488`
- Metal stub: `engine/metal/src/engine/stubs_0291.cpp:1-4,21-25`
- 設定一覧: `docs/SETTINGS.md:456`
