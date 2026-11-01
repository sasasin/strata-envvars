# `DS4_DBG_H`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal backend の DSV4.1 layer 処理で、残差状態 `h` の値を stderr に診断出力する開発・調査用フックです。計算結果や制御分岐を変える設定ではありません。`DS4_DBG_ALL` が有効なら対象 layer を拡張します（`src/dsv41/ds4_model.cu:9986-10005`）。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む任意の設定値 | 有効。値の文字列や数値は parse しない |

共通 helper `ds4_dbg(name)` は Metal build では `std::getenv(name) != nullptr` を返します。したがって `DS4_DBG_H=0` や空文字も「設定あり」です。helper は static cache を持たず、この分岐が評価されるたびに環境を読みます（`src/dsv41/ds4_launch.h:30-36`）。この名前を読むコードは `src/dsv41/ds4_model.cu:9986` の一箇所です。

## 有効になる条件

- `STRATA_METAL` でコンパイルされた DSV4.1 engine が layer 処理を実行する必要があります。CUDA/HIP 側では `ds4_dbg()` は常に `false` を返すため、この環境変数による出力はありません（`src/dsv41/ds4_launch.h:30-36`）。
- `DS4_DBG_H` が設定され、group member `mi` が `0` であることが必要です。
- 標準では layer index `l.il` が `0` または `1` のときだけ出力します。`l.il >= 2` も出すには `DS4_DBG_ALL` を設定します。こちらも設定値の内容ではなく、設定の有無を判定します（`src/dsv41/ds4_model.cu:9986`）。
- CLI 引数や別設定値による優先順位・上書きはこの実装にはありません。DSV4.1 の layer 処理が呼ばれない実行では、この診断も行われません。

## 実行時の詳細

`run_dev()` が各 layer を処理するとき `layer()` を呼び、その layer の本計算に入る前に診断分岐を評価します（`src/dsv41/ds4_model.cu:9928-9929,9961-9969,9985-9987`）。対象になると `T * H * D` 個の float 用 vector を作り、Metal のキューを同期・flush してから `d.h` の host view を取得し、取得できた場合に値をコピーします。続いて NaN 数、非ゼロ数、最大絶対値を集計し、次の形式で stderr に一行出力します（`src/dsv41/ds4_model.cu:9987-10005`; flush の実装は `metal/src/engine/ds4_finish.cpp:2728-2736`）。

```text
DBG h: il=... dev=... h=... p0=... T=... p0tok=... zeros=... ninf=... max=... first=... ... nan_range=.....
```

`ninf` 欄には実装上 NaN と判定した要素数が出ます（カウンタ `nf`）。`host_view(d.h)` が null の場合、vector はゼロ初期化状態のまま集計・出力されます。診断ブロックには明示的なエラー返却や終了処理はありません。このチェックは通常の layer 呼び出しごとに行われ、環境値をプロセス内で変更した場合も次の評価で再参照されます。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — Metal では環境変数の有無を返し、非 Metal では compile-time false とする helper。
- `src/dsv41/ds4_model.cu:9928-9929,9961-9969,9985-10005` — layer 呼び出し、適用条件、`h` の取得・集計・stderr 出力。
- `metal/src/engine/ds4_finish.cpp:2728-2736` — 診断前に呼ぶ Metal flush の Strata 実装。
