# `FNX_RING_GRID`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

HIP 版 split engine のリング集約 kernel に使う CUDA/HIP grid の block 数を調整します。通常の `ring_sum` は 256 threads/block で、行数とモデル幅から計算した値を最大 40（`T > MAXT` では 240）に制限します。HIP 版では、`T <= MAXT` のとき環境変数の正の値でこの grid を上書きし、処理要素数に必要な block 数を上限にします。`MAXT` は 16 行です。

ソースコメントは one-hop window sum の調整と説明していますが、実装上の上書きは one-hop kernel を選ぶ条件より前に行われます。そのため `T <= 16` なら one-hop の有無にかかわらず grid に反映され、後段で選ばれる peer push、one-hop、または通常 ring kernel のいずれにも適用されます。

## 値と判定

この変数は `fnx::env_int("FNX_RING_GRID", 0)` で読み取られます。helper は未設定なら既定値を返し、設定時は符号付き base-10 整数として文字列全体を検証します。先頭の `+` / `-` は受け付けますが、空文字、空白、数字以外の末尾、`long long` の範囲外は無効です。

| 値 | 動作 |
|---|---|
| 未設定 | 既定値 0。grid 上書きなし |
| `0` または負数 | `g > 0` の条件を満たさず、grid 上書きなし |
| `int` 変換後の `g` が正 | `min(g, ceil(T * NP / 256))` を grid に設定（通常の `T > 0`、`NP = N / 2`）。要求値が通常の上限 40 より大きければ、要素数に必要な block 数まで増やせる |
| 空文字・整数でない文字列・`long long` 範囲外 | `std::runtime_error`。エラーは `FNX_RING_GRID: '<値>' is not a whole number` の形式 |

値は `long long` から `int` に変換されます。コードに `int` 範囲の個別検証はありません。したがって `long long` として有効でも `int` で表せない値について、実装は変換後の結果を別途検証しません。正値に対する明示的な上限は grid 設定時の要素数上限です。

## 有効になる条件

- `src/split/CMakeLists.txt` の HIP 用 target では `FNX_HIP=1` が定義され、この分岐がコンパイルされます。CUDA 用 target ではこの分岐はありません。
- `ring_sum` が呼ばれ、`T <= MAXT`（最大 16 行）の経路に入る必要があります。`T > MAXT` では変数を読みません（`r.flags` が立っている場合は専用 chunk ring 経路に入ります）。
- `g > 0` の場合だけ grid を変更します。`FNX_ONEHOP` が 0、または `FNX_RING_F32` により one-hop が選ばれない場合も、grid の上書き自体は先に適用されます。これらの変数は kernel 選択や ring 表現に関わりますが、`FNX_RING_GRID` の値判定を置き換えません。
- CLI 引数や設定ファイルによる優先順位・上書きは実装にありません。

## 実行時の詳細

環境値の読み取りは `ring_sum` 内の関数ローカル `static const int` です。HIP ビルドで初めて `T <= MAXT` の処理に到達したときに一度だけ評価され、同一プロセス内では結果が cache されます。初回評価後に環境を変更しても反映されません。`T > MAXT` の呼び出ししかなければ初期化されません。

正の値が適用された grid で `k_ring_a2a_push`（peer push 条件）、`k_ring_a2a`（one-hop 条件）、または `k_ring`（通常 ring）が起動されます。これらは各行・各要素の分担に gridDim を使います。変数値そのものを出力するログは見当たりません。

無効な設定値は helper が例外を投げます。`fnx_run` は stderr に `fnx_run: <例外>` を出して終了コード 1 を返します。`sfnx` の実行中の失敗経路では `ERR <例外>` を通知し stderr に `sfnx: failed: <例外>` を出して終了コード 1 で終了します。

## 根拠

- `src/split/src/kernels.cu:1566-1598` — `ring_sum` の既定 grid、HIP 限定の読み取りと上書き、kernel 選択・起動。
- `src/split/src/env.hpp:15-21,33-40` — 整数全体の parse、未設定時の既定値、無効値の例外。
- `src/split/src/model.hpp:43` — `MAXT = 16`。
- `src/split/CMakeLists.txt:92-106,111-118` — split engine の HIP target に `FNX_HIP=1` を定義する箇所と CUDA target 側。
- `src/split/src/engine.cu:266-273,935-936,987-988,1073,1158,1263,1327` — one-hop 条件と `ring_sum` の engine 呼び出し箇所。
- `src/split/tools/fnx_run.cpp:1365-1373` — `fnx_run` の例外表示と終了コード。
- `src/split/tools/sfnx.cpp:1027-1035` — `sfnx` の実行時エラー通知、stderr、終了コード。
