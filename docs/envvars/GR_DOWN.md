# `GR_DOWN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`GR_DOWN` は Metal の開発・診断用実行ファイル `gr_parity` において、hyper-connection down kernel の variant 名を選ぶ。通常の Metal engine が使う環境設定ではなく、`engine/metal/tests/gr_parity.cpp` から `getenv` で読まれるテスト専用の selector である。同ファイル冒頭は `gr_parity` を parity 検証または per-kernel benchmark と説明している（`engine/metal/tests/gr_parity.cpp:1-5,73-90`）。

選ばれた値は `gr_down_`、`gr_down_bf16f_`、`gr_down_q8_`、`gr_down_q8f_` のいずれかの後ろに付加され、down kernel の pipeline 名と dispatch の threadgroup サイズ・grid サイズに使われる。通常の engine の `window.cpp` は `8_8` の固定名を組み立てており、この変数を読まない（`engine/metal/src/engine/window.cpp:1104-1105,2661`）。

## 値と判定

環境値を文字列として取得し、未設定なら `"8_8"` にする。続いて `std::sscanf(grd.c_str(), "%d_%d", &grd_sg, &grd_ks)` で整数を読み込む。変換結果のチェックはなく、初期値は両方 8 である。したがって空文字や先頭整数を読めない文字列では初期値が残る。片方だけ変換できれば、もう片方は 8 のままになる。`%d` のため符号付き整数と先行空白を受け付け、末尾の未読文字列も検査されない（`engine/metal/tests/gr_parity.cpp:73-77`）。

| 条件 | unset | 有効になる例 | 無効・注意が必要な例 |
|---|---|---|---|
| `gr_parity` の down variant 名 | `8_8` | `8_8`, `8_4`, `4_4`, `4_2`, `16_16`, `16_8` は登録済みの variant 名になる | `4_8`, `0_0`, `8_x` は登録名と一致しない。空文字、`abc` など整数変換が始まらない値は既定の `8_8` が残る。`8_8junk` は `8_8` として読み取られる |

登録済みの6組は `engine/metal/kernels/gr.metal:282-286` にあります。これは parser が値域を検証するという意味ではありません。整数として読み取れても登録名と一致しない場合は pipeline の作成に失敗します（`engine/metal/tests/gr_parity.cpp:75-90`; `engine/metal/src/mtl_rt.mm:229-255`）。

## 有効になる条件

- `GR_DOWN` を読むのは `gr_parity` だけであり、通常の Strata engine の生成・推論には適用されない（`engine/metal/tests/gr_parity.cpp:29-38,73-90`; `engine/metal/src/engine/window.cpp:1104-1105,2661`）。
- テスト実行ファイルが Metal 対応環境で起動され、`gr.metal` の compile と指定名の pipeline 作成まで進む必要がある（`engine/metal/tests/gr_parity.cpp:37-39,85-90`）。
- `GR_Q8` が設定されていれば down prefix は Q8_0 用になり、未設定なら BF16 用になる。`GR_INJ_F32` の設定有無で inject 用形式の prefix も変わる。いずれも設定有無だけを見ており、空文字でも設定済み扱いとなる。これらの変数は `GR_DOWN` の判定値を上書きせず、別の kernel 名 prefix を選ぶ（`engine/metal/tests/gr_parity.cpp:41-44,88-90`）。各 prefix には `gr.metal:282-286` の同じ6 variant が登録されている。
- `--bench` と `--ntok N` はテストの benchmark/parity モードと token 数を選ぶ引数で、`GR_DOWN` の値判定を変えない（`engine/metal/tests/gr_parity.cpp:29-36,87-90`）。

## 実行時の詳細

`main()` が開始した後、buffer の割り当て前に一度値を読み、`grd_sg` と `grd_ks` を計算する。static cache はないが、この実行では値を再取得しない。実行中に環境を変更するコードもなく、通常の engine や子プロセスへの転送もない（`engine/metal/tests/gr_parity.cpp:29-37,73-90`）。

down pipeline 名に読み取った二つの整数をつなげ、dispatch では `grd_rs = grd_sg / grd_ks` を `grid[0]` の行数計算に、`32 * grd_sg` を `tg[0]` に使う。したがって選択 variant は down kernel とその dispatch geometry を変える。parity 計算や up kernel の選択そのものを `GR_DOWN` が変更するコードはない（`engine/metal/tests/gr_parity.cpp:75-77,88-90,106-114`）。

整数変換に失敗した値は初期値を残して既定 variant を使う。一方、変換結果から作った名前が登録済みでなければ `Context::pipeline` が `mtl: no function <名前> <詳細>` を stderr に出し、exit status 3 で終了する。登録済み関数の pipeline 作成自体が失敗した場合も `mtl: pipeline <名前>: <詳細>` を出して status 3 で終了する（`engine/metal/src/mtl_rt.mm:229-265`）。成功時は parity 実行で PASS/FAIL 行と最後の `ALL PASS` / `SOME FAILED` を出し、失敗件数に応じて status 0 / 1 を返す。benchmark モードでは per-kernel の時間行を出す（`engine/metal/tests/gr_parity.cpp:187-212`）。

## ログと測定値

`GR_DOWN` 自体を表示するログはありません。variant 名の pipeline が見つからない、または pipeline 作成に失敗した場合の stderr と終了 status は上記の通りです（`engine/metal/src/mtl_rt.mm:252-265`）。この変数の値ごとの性能測定値は、対象ソース・資料から確認できません。

## 根拠

- `engine/metal/tests/gr_parity.cpp:1-5,29-44,73-90,106-114,187-212` — test-only の位置付け、読み取り・parse、pipeline 名と dispatch、結果出力。
- `engine/metal/kernels/gr.metal:282-286` — 登録済みの variant 名。
- `engine/metal/src/mtl_rt.mm:229-265` — pipeline lookup / 作成の失敗ログと終了 status。
- `engine/metal/src/engine/window.cpp:1104-1105,2661` — 通常 engine 側が固定名を使用。
