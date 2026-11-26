# `FNX_PFX_GDN_TC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA split engine の prompt 中の GDN scan で、Strata の tensor-core chunk scan を使うかを上書きする。`1` などの非ゼロ値は使用を要求し、`0` は無効化する。設定しない場合はモデルの routed-expert 形式に応じた既定値を使う。これは prompt 経路の選択であり、decode GDN の scan 選択にはこの読み取りは使われない（`engine/src/split/src/kernels.cu:2001-2017`, `engine/src/split/src/engine.cu:65-66`）。

機能本体は `FNX_KPART == 4 && !FNX_HIP && FNX_ARCH >= 80` のときだけコンパイルされる。それ以外のビルドには環境変数の読み取り箇所がなく、この設定による変更はない（`engine/src/split/src/gdn_tc_prompt.cuh:11-20,720-761`）。

## 値と判定

`gdn_prompt_impl` 内の関数ローカル `static const int` 初期化で一度だけ `fnx::env_int("FNX_PFX_GDN_TC", -1)` を呼ぶ。helper は `getenv` で未設定を判定し、設定値全体を符号付き base-10 整数として読み取る。空文字、空白、数字以外の末尾、`long long` 範囲外は整数として受理せず、`FNX_PFX_GDN_TC: '<値>' is not a whole number` の例外になる。`+` / `-` 符号は受理する。読み取った値は `int` に cast される（`engine/src/split/src/env.hpp:15-21,33-40`, `engine/src/split/src/kernels.cu:2008-2011`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 対応ビルドで、cast 後の値が `>= 0` | `-1` を使いモデル既定に委ねる | `1`, `2` は ON、`0` は OFF | `-2` はモデル既定に委ねる。空文字・`true`・`0x` は parse 例外 |
| CUDA/HIP 以外、HIP、または `FNX_ARCH < 80` | 読み取りコード自体がコンパイルされない | 該当なし | 設定値はこの機能に作用しない |

意図された上書き値は `0` と `1`。読み取れる整数に `0/1` の限定検査や clamp はなく、正の整数はすべて ON、負の整数は既定値に戻る。`long long` から `int` への範囲外 cast の結果は実装依存なので、`INT_MIN..INT_MAX` 外の値の意味は保証されない（`engine/src/split/src/env.hpp:15-21,33-40`, `engine/src/split/src/kernels.cu:2010-2011`）。

## 有効になる条件

- ビルドが CUDA split engine であり、`FNX_KPART == 4` かつ `FNX_ARCH >= 80` である必要がある。HIP とそれ以外の build architecture ではこの tensor-core scan はコンパイルされない（`engine/src/split/src/gdn_tc_prompt.cuh:11-20`）。
- 未設定または負値なら、`Engine` 構築時に設定するモデル既定を使う。`m_.g.iq_experts()` が真（routed experts を持つ IQ / Strata 2-bit 型）なら OFF、偽なら ON（`engine/src/split/src/engine.cu:65-66`; 判定内容は `engine/src/split/src/gguf.hpp:69,98`, 初期化は `engine/src/split/src/gguf.cpp:143`）。
- ON でも実行デバイスが compute capability major 8 未満、必要な opt-in shared memory が不足、`nk` / `nv` が正でない、scan scratch が利用できない、または scan の launch 後に CUDA error がある場合、`gdn_tc_run` は `false` を返す。呼び出し側は通常の chunk scan `k_gdn_ch_prep` / `k_gdn_ch_rec` に進む（`engine/src/split/src/gdn_tc_prompt.cuh:720-759`, `engine/src/split/src/kernels.cu:2011-2017,2049-2050`）。
- この環境変数を読むのは `gdn_prompt_impl` の prompt GDN 経路だけ。CLI 引数や別環境変数による優先上書きは、この選択箇所にはない（`engine/src/split/src/kernels.cu:2001-2017`）。

## 実行時の詳細

環境変数は `gdn_prompt_impl` が初めて呼ばれたときに static 初期化され、そのプロセス内では以後の呼び出しに同じ値を使う。実行中に環境を書き換えても再評価しない。例外なく値が読めた後は、非負ならその値のゼロ判定を使い、負なら atomic に保持されたモデル既定を参照する（`engine/src/split/src/kernels.cu:1916-1917,2008-2012`）。

scan を選び `gdn_tc_run` が成功すると tensor-core scan が `S` と `y32` を処理し、`k_gdn_pf_norm_own` を起動して prompt GDN を終える。scan を選ばない場合、または実行可能条件を満たさず `false` が返る場合は `k_gdn_ch_prep` と `k_gdn_ch_rec` による chunk scan に進み、その後 `k_gdn_pf_norm_own` を実行する。ここでの fallback は同じ prompt GDN 処理の別実装を使う分岐である（`engine/src/split/src/kernels.cu:2011-2017,2049-2069`）。

値の parse に失敗すると `std::runtime_error` が伝播し、`fnx_run` の最上位 handler は stderr に `fnx_run: <例外内容>` を出して終了コード 1 を返す（`engine/src/split/src/env.hpp:33-39`, `engine/src/split/tools/fnx_run.cpp:1370-1372`）。

## ログと測定値

この変数専用の有効・無効ログや fallback 理由ログは確認できない。parse 例外は上記のとおり `fnx_run: ...` として stderr に出る。Strata の `docs/DETAILS.md` に本変数固有の測定値は見つからなかった。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40` — 整数の全体 parse、既定値、無効値時の例外。
- `engine/src/split/src/engine.cu:65-66`, `engine/src/split/src/gguf.hpp:69,98`, `engine/src/split/src/gguf.cpp:143` — モデル形式による既定値。
- `engine/src/split/src/kernels.cu:1916-1917,2001-2017,2049-2069` — cache、値判定、scan と fallback の呼び分け。
- `engine/src/split/src/gdn_tc_prompt.cuh:11-20,720-761` — CUDA / architecture 条件、デバイス条件と scan の失敗時の戻り値。
- `engine/src/split/tools/fnx_run.cpp:1370-1372` — 例外時の stderr と終了コード。
