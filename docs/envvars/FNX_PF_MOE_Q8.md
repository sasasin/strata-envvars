# `FNX_PF_MOE_Q8`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

split engine の prompt（prefill）経路で、MoE の routed expert 計算に使う入力・中間値の一部を Q8_1 に量子化し、decode 用の `*_big` expert kernel へ渡すかを選ぶ。無効時は同じ routed expert 計算を F16 入力と MMA kernel で行う。router の選択計算と shared expert の経路はこの切替の対象ではない（`engine/src/split/src/prefill.cu:1737-1759`）。

この読み取りは `Engine::prefill_alloc()` にある。split engine の構築時に prompt 用バッファを用意し、その間に値を読み取る（`engine/src/split/src/engine.cu:318`、`engine/src/split/src/prefill.cu:854-865,950-955`）。

## 値と判定

`env_flag()` は `env_int(name, 0) != 0` を返す。未設定は整数 `0` となり無効。設定時は符号付き base-10 整数を文字列全体から読み、0 以外なら有効にする。値を `1` に限定せず、範囲 clamp もしない（`engine/src/split/src/env.hpp:15-21,33-40,51-52`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| split engine の prompt buffer 構築 | `0`（無効） | `1`、`2`、`-1` など、long long の範囲内で 0 以外の整数 | `0`、`+0` |

空文字、`true` / `false`、`0anything`、先頭・末尾空白を含む文字列は整数全体として不正で、`env_int()` が `FNX_PF_MOE_Q8: '<値>' is not a whole number` の `std::runtime_error` を投げる。`+` / `-` だけ、long long の範囲外も不正。小数・大文字小文字の解釈はなく、10 進数字と任意の先頭符号だけを受け付ける（`engine/src/split/src/env.hpp:15-21,33-39`）。

## 有効になる条件

- `engine/src/split/src/prefill.cu` の split prompt 実装が使われ、その `Engine` が構築されること。読み取り箇所は同ファイルだけで、CUDA/HIP の split 実装を通らない実行経路にこの設定が適用される根拠は見つからない（`engine/src/split/src/prefill.cu:10-24,854-865,950`）。
- 値が 0 以外であれば Q8_1 用バッファを割り当てる。割り当てられなければ、実行時に F16 経路へ自動 fallback する分岐はない（`engine/src/split/src/prefill.cu:950-955`）。
- CLI 引数、サーバーモード、別環境変数によるこの値の上書き・優先順位は、対象変数の参照全体と読み取り helper の呼び出し先には見つからない。prompt の行数などの実行条件は chunk サイズ `C` に反映されるが、このフラグの値判定は変えない（`engine/src/split/src/prefill.cu:1730-1739`）。

## 実行時の詳細

`Engine` 構築中に `prefill_alloc()` が呼ばれ、各 GPU card の `Pf` を作るループ内で `env_flag()` を読み取る。関数内 static cache ではなく、リクエストごとの読み取りでもない。値は各 card の `Pf::moe_q8` に保存され、その engine の prompt 計算で使われる。エンジン構築後にプロセス環境を変更しても、すでに保存された値や確保済みバッファには反映されない（`engine/src/split/src/engine.cu:318`、`engine/src/split/src/prefill.cu:854-865,950-955`）。

有効時は各 FFN half で `p.mixed` を Q8_1 に量子化し、routed experts に `moe_gate_up_big()` と `moe_down_big()` を使う。無効時は `p.xh` の F16 入力で `moe_gate_up_mma()`、gate/up 後の値を `swiglu_h16()` で F16 化し、`moe_down_mma()` を使う。どちらでも router logits と top-10 expert 選択は同じコードを通る。shared expert は両分岐の後に別途 `p.xh` を使う F16 経路で計算される（`engine/src/split/src/prefill.cu:1737-1759`）。

有効時には各 card で `p.xq` と split twin 用領域を追加確保する。環境値が不正ならこの初期化中に例外が送出される。GPU 割り当てや kernel 起動の失敗経路は既存の `palloc` / kernel wrapper に従うが、この環境変数専用の fallback・警告・ログはない（`engine/src/split/src/prefill.cu:950-955,1738,1746-1753`）。

## ログと測定値

この変数の読み取りや有効化を知らせる専用の stdout / stderr ログは確認できない。無効値では F16 側を選び、エラー値では `env_int()` の例外メッセージが構成されるが、この箇所にログ出力はない（`engine/src/split/src/env.hpp:33-39`）。この調査で Strata 資料にある条件付き測定値は確認できなかった。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40,51-52` — 整数の構文・範囲、未設定既定値、不正値の例外、非ゼロ判定。
- `engine/src/split/src/engine.cu:318` — engine 構築中の prefill buffer 初期化。
- `engine/src/split/src/prefill.cu:323-332,854-865,950-955` — `Pf` のフラグと Q8_1 バッファの割り当て。
- `engine/src/split/src/prefill.cu:1726-1759` — prompt FFN の量子化、routed expert の Q8_1/F16 分岐、router と shared expert の共通経路。
