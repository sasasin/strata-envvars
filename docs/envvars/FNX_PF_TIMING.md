# `FNX_PF_TIMING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`strata-split-N` の sFNX prompt path について、確保した prompt 用バッファ量、RAM 上の expert を stage する設定、各 prefill pass の所要時間を stderr に出す診断スイッチである。計算経路や値の選択を変える分岐はなく、ログ出力だけを制御する。実装は `Engine::prefill_alloc`、`Engine::prefill_stages`、`Engine::prefill` にある（`engine/src/split/src/prefill.cu:854-855,1144-1147,1247-1259,1831-1842`）。

このコードは opt-in の strata-split エンジンに属する。split は既定で無効で、ビルド時に `STRATA_BUILD_SPLIT=ON` を指定して作る Linux CUDA/HIP 向けの実行ファイルである（`engine/src/split/CMakeLists.txt:1-7,120-152`）。通常の Strata エンジンの環境変数ではない。

## 値と判定

3 箇所とも `fnx::env_flag` を使う。これは `getenv` で値を取得し、`env_int(name, 0) != 0` と判定する。設定なしは 0（無効）。値は 10 進の符号付き整数として全体を `strtoll` で読み、末尾まで消費でき、`long long` の範囲内である必要がある（`engine/src/split/src/env.hpp:15-22,33-40,51-52`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| split エンジン内の 3 読み取り箇所 | 無効 | `1`, `-1`, `+2`（整数として非ゼロ） | `0`, `00`（整数としてゼロ） |

空文字、`true` / `false`、`0anything`、前後の空白、整数でない文字列、`long long` 範囲外は整数全体の parse に失敗し、`std::runtime_error`（`FNX_PF_TIMING: '<値>' is not a whole number`）になる。小数や数値の後ろに文字を付けた値も受理されない。値に範囲制限はなく、範囲内の負数も非ゼロなら有効（`engine/src/split/src/env.hpp:15-22,33-40,51-52`）。

## 有効になる条件

- split エンジンを含むビルドが必要。既定では `STRATA_BUILD_SPLIT` が OFF であり、split バイナリがない通常ビルドではこの読み取り箇所は実行されない（`engine/src/split/CMakeLists.txt:1-7`）。
- prompt 用メモリのログは `Engine::prefill_alloc` が各カードのバッファ割当てを終えたときに評価される。stage ログは `Engine` の構築中に `prefill_stages` が呼ばれたときだけ評価される。arena 有無にかかわらずこの呼び出しがある（`engine/src/split/src/engine.cu:317-318,359-392`）。
- pass 時間ログは `Engine::prefill` が処理を完了してログ位置まで到達した場合に出る。prefill を行わない実行や、途中で例外・失敗となった実行にはこの行は出ない（`engine/src/split/src/prefill.cu:1300-1303,1785-1803,1831-1842`）。
- CLI 引数、モデル状態、別の環境変数による `FNX_PF_TIMING` の上書き・優先順位はない。ここで参照する設定はプロセスの環境値のみ。

## 実行時の詳細

`Engine::prefill_alloc` はカードごとに `env_flag("FNX_PF_TIMING")` を呼び、true のとき `stderr` に `prefill buffers on card %d: %zu MiB (%zu MiB free before)` を出す。サイズと空き量は `pf_card_bytes` と割当て直前に得た `free0` の MiB 表示である。`Engine::prefill_stages` もカードごとに値を読み、true のとき `prefill on card %d: passes of %d chunks, stages of %zu MiB` を出す（`engine/src/split/src/prefill.cu:854-864,1144-1147,1247-1259`）。

`Engine::prefill` の pass 完了箇所では `static const bool timing` として初回到達時に一度評価し、以後の pass ではその値を使う。true なら開始位置、chunk 数、row 数、全体時間、embed + upload 時間、enqueue 時間、draft layer 時間を ms で出す。staging が有効な pass では各カードの expert コピー量と in-place read 量も同じ行に加える（`engine/src/split/src/prefill.cu:1300-1308,1831-1842`）。

前二者は呼び出しごと（各カードの初期化時）に `getenv` し、後者は関数内 static に初回値を保持する。環境変数をプロセス実行中に変更した場合、すでに通過した初期化ログは再評価されず、pass ログは初回 pass の評価後に変更しても切り替わらない。CLI の prefill 選択フラグ `FNX_PREFILL` は別の判定であり、この変数の値を変更しない（`engine/src/split/src/env.hpp:33-40,51-52`; `engine/src/split/tools/fnx_run.cpp:987-992,1003-1009`）。

有効値なら処理結果にログが追加される。無効な文字列や空文字は helper の例外となり、Engine 構築中なら初期化が失敗する。pass ログ評価時に例外となる場合も prefill の呼出し元へ伝播する。これらの読み取り箇所自体に `FNX_PF_TIMING` 専用の catch、警告文、fallback はない（`engine/src/split/src/env.hpp:33-40`; `engine/src/split/src/engine.cu:317-318,359-392`; `engine/src/split/src/prefill.cu:1146-1147,1257-1259,1831-1842`）。

## ログと測定値

上記 3 種のログはすべて `stderr` への `fprintf` である。計測時間は `std::chrono::steady_clock` の pass 内計時点間の差で、ミリ秒を小数 1 桁で表示する。Strata の資料にこの変数を使った比較測定値は確認できなかったため、速度向上などの数値は記載しない（`engine/src/split/src/prefill.cu:1831-1842`）。

## 根拠

- `engine/src/split/src/env.hpp:15-22,33-40,51-52` — 整数全体の parse、未設定時の既定値、非ゼロ判定。
- `engine/src/split/src/prefill.cu:854-864,1144-1147` — prompt buffer 割当て後の読み取りとログ。
- `engine/src/split/src/prefill.cu:1247-1259` — stage 割当て後の読み取りとログ。
- `engine/src/split/src/prefill.cu:1300-1308,1785-1803,1831-1842` — prefill の pass 成功経路、static cache、時間ログ。
- `engine/src/split/src/engine.cu:317-318,359-392` — Engine 構築時の呼び出し。
- `engine/src/split/CMakeLists.txt:1-7,120-152` — split の build 条件と独立実行ファイル。
