# `FNX_RING_GRID`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP 版 split engine の `ring_sum` が、行数 `T <= MAXT` の ring 計算で GPU に起動する thread block 数を上書きする。既定の grid 上限 40 block より大きい値を指定できる一方、実データを処理するのに必要な block 数を上限に clamp する。値によって ring の加算方式や入力値は切り替わらず、変更するのは grid 数である（`engine/src/split/src/kernels.cu:1582-1614`）。

この読み取りは `#if FNX_HIP` 内にあり、split の HIP target は `FNX_HIP=1` でコンパイルされる。CUDA target にはこの定義がないため、この変数を読む分岐は HIP build に限られる（`engine/src/split/src/kernels.cu:1593-1601`、`engine/src/split/CMakeLists.txt:121-143`）。

## 値と判定

`fnx::env_int` は環境変数が未設定なら呼び出し側の既定値を返し、設定済みなら `parse_whole` で文字列全体を符号付き base-10 整数として読み取る。先頭の `+` / `-` と数字列のみを許し、値は `long long` の範囲内でなければならない。空文字、前後の空白、数字以外の末尾、範囲外は整数として不正となる。部分文字列だけを読むことはない（`engine/src/split/src/env.hpp:15-21,33-40`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP split、`ring_sum` 内の宣言に到達 | `0`。grid の上書きなし | 正の整数。`g = (int) env_int(...)` の後、`g > 0` の場合に `min(g, ceil(T * NP / 256))` を grid に設定 | `0` と負数は parse されるが上書きしない。空文字、`true`、`1x`、空白付きの数値などは整数 parse エラー |
| CUDA build、または `T > MAXT` | この変数は読まれない | 該当なし | 該当なし |

有効例は `1`、`+8`、`0008`。`0`、`-1` は parse 成功後に override 条件を満たさず、既定 grid のままとなる。`1x`、空文字、` 8`、`8 ` はエラーになる。`long long` から `int` への cast が行われる前に `int` の範囲へ clamp する処理はない（`engine/src/split/src/kernels.cu:1597-1600`）。

既定 grid は整数演算の `(T * NP / NCARD + 255) / 256` を使い、`max(4, min(T > MAXT ? 240 : 40, ...))` で決める。したがって override はこの値を正の `g` で置き換え、データ全体を処理する block 数 `(T * NP + 255) / 256` を上限にする。コード上、override 側には既定値の `min 4` に相当する下限 clamp はない（`engine/src/split/src/kernels.cu:1593-1600`）。

## 有効になる条件

- HIP build の split engine で `ring_sum` が呼ばれること。`FNX_HIP=1` は HIP target に定義され、通常の CUDA target ではこの環境変数を参照するコードがコンパイルされない（`engine/src/split/CMakeLists.txt:121-143`）。
- `T <= MAXT` であること。`MAXT` は 16。`T > MAXT` かつ `r.flags` がある場合は chunk ring を起動して先に return し、その他の `T > MAXT` も環境変数を読む `if (T <= MAXT)` を通らない（`engine/src/split/src/model.hpp:43`、`engine/src/split/src/kernels.cu:1582-1601`）。
- 値が正の整数であること。未設定・0・負数なら既定 grid を使う。正の値でも、データ全体に必要な block 数を超える部分は切り詰められる（`engine/src/split/src/kernels.cu:1597-1600`）。
- `r.peer` / `r.onehop` の状態は、grid を使う ring kernel の選択には関わるが、環境変数を読む条件には含まれない。環境変数の判定後に peer push、一 hop、通常 ring のいずれかを選び、それぞれ同じ計算で決まった grid 数を使う（`engine/src/split/src/kernels.cu:1602-1614`）。`FNX_ONEHOP` や `FNX_RING_F32` が ring の方式を変えても、それ自体は `FNX_RING_GRID` の判定を無効化しない（`engine/src/split/src/engine.cu:308-316`、`engine/src/split/src/engine_common.cu:1035-1041`）。

## 実行時の詳細

`ring_sum` は入力が ring buffer の保持行数を超えれば `ring_sum: more rows than the ring's buffers hold` を例外にする。その後、`r.flags && T > MAXT` の chunk path を先に処理する。通常 path では grid を計算し、HIP build かつ `T <= MAXT` の場合だけ `static const int g` を初期化して環境変数を読む（`engine/src/split/src/kernels.cu:1582-1600`）。

この `static` は最初に該当分岐へ到達したとき一度だけ評価され、成功すればそのプロセス内で値を保持する。それ以降にプロセスの環境を変更しても再読込されない。分岐へ到達しない実行では読み取りも起きない。`ring_sum` は split engine の window 処理などから呼ばれる（例: `engine/src/split/src/engine.cu:980,1032,1119,1204,1339,1403`）。

正の `g` は、通常 grid の代わりに `min(g, ceil(T * NP / 256))` を使う。`k_ring_a2a` などの kernel は block/thread index を用いて要素 `e` を grid stride で分担するため、この値は block あたりの担当量と並列分配を変える。環境変数を使った追加の加算・丸め規則の分岐はない（`engine/src/split/src/kernels.cu:949-970,977-1001,1597-1614`）。

## ログと測定値

有効値に対する専用ログはない。設定値が `long long` として不正なら `env_int` が `std::runtime_error` を投げ、そのメッセージは `FNX_RING_GRID: '<値>' is not a whole number`。この関数内には stderr 出力や終了処理はなく、例外の捕捉後にどう表示・終了するかは呼び出し側に依存する（`engine/src/split/src/env.hpp:33-40`）。ソースコメントには screen 用の試行意図が記されているが、条件付きの測定値は示されていない（`engine/src/split/src/kernels.cu:1595-1596`）。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40` — 整数文字列の判定、未設定時の既定値、不正値の例外。
- `engine/src/split/src/kernels.cu:1582-1614` — `ring_sum` の早期 return、既定 grid、環境変数による上書きと後続 kernel 起動。
- `engine/src/split/src/kernels.cu:949-970,977-1001` — one-hop kernel の grid stride 分配。
- `engine/src/split/src/model.hpp:43` — `MAXT` の値。
- `engine/src/split/CMakeLists.txt:121-143` — HIP target での `FNX_HIP=1` と CUDA target の別 build 定義。
- `engine/src/split/src/engine.cu:308-316`、`engine/src/split/src/engine_common.cu:1035-1041` — ring mode に関わる `FNX_ONEHOP` / `FNX_RING_F32` の設定。
