# `FNX_HC_GRID`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP 版 split engine のハイパーコネクション read kernel で、同時に起動する grid block 数を指定する内部調整値です。通常は `hc_prepare` が GPU の SM 数を基準に grid を決めますが、この値が正数なら `H_BLOCKS` 以下の指定値で置き換えます。`hc_read` は保存された grid を使って kernel を起動し、grid が `H_BLOCKS` より小さい場合は各 block が複数の仕事を順に処理する `WALK` 版を選びます（`engine/src/split/src/kernels.cu:1173-1190,1205-1227`; `engine/src/split/src/hc.cuh:113-115,130-134,382-392`）。

この読み取りを含む `hc_prepare` は `FNX_KPART == 3` の kernel 分割にコンパイルされ、その中の環境読み取りはさらに `FNX_HIP` 条件内です。split の CMake は kernel を 0..8 の部分に分け、HIP target に `FNX_HIP=1` を定義するため、HIP split engine では有効ですが、非 HIP build では環境値を読みません（`engine/src/split/src/kernels.cu:1139-1140,1173-1185`; `engine/src/split/CMakeLists.txt:93-102,120-127`）。通常の CLI 引数や別の環境変数による `FNX_HC_GRID` の上書きは、この実装にはありません。

## 値と判定

`fnx::env_int("FNX_HC_GRID", 0)` が `std::getenv` で値を取り、符号付き base-10 の `long long` として文字列全体を解析します。未設定なら既定値 `0`、設定済みの空文字は数値として不正です。先頭には `+` または `-` を付けられますが、先頭・末尾の空白や数字以外の後続文字は受け付けません。`long long` の範囲外も不正です（`engine/src/split/src/env.hpp:15-21,33-40`）。

| 条件 | unset | 有効になる値（例） | grid 変更なし / 無効になる値（例） |
| --- | --- | --- | --- |
| HIP split engine の `hc_prepare` | `0` と同じ。通常の `min(SM 数, H_BLOCKS)` を使う | 正数。`H_BLOCKS` を超える値は `H_BLOCKS` に制限 | `0`、負数（例 `-1`）は通常 grid のまま。空文字、`true`、`1x`、空白付き数値、整数範囲外は parse error |
| 非 HIP build | このコード箇所で環境値を読まない | なし | 値にかかわらずこの設定の効果なし |

正数 `g` は `min(g, cap ? cap : H_BLOCKS)` で grid に設定されます。Engine の呼び出しは `hc_prepare(b->hcs)` と cap を省略し、既定 cap `0` を使うため、ここでは `min(g, H_BLOCKS)` です。上限は SM 数ではないので、`g` が SM 数より大きくても `H_BLOCKS` 以下ならその値がそのまま使われます（`engine/src/split/src/kernels.hpp:64-67`; `engine/src/split/src/engine.cu:174-184`; `engine/src/split/src/kernels.cu:1173-1185`）。

不正な設定値は fallback せず、`std::runtime_error`（`FNX_HC_GRID: '<値>' is not a whole number`）になります。空文字もこの経路です（`engine/src/split/src/env.hpp:15-21,33-40`）。

## 有効になる条件

- split の kernel 分割 `FNX_KPART == 3` に `hc_prepare` がコンパイルされていること。CMake は `kernels.cu` を 0..8 の部分に分けます（`engine/src/split/src/kernels.cu:1139-1140`; `engine/src/split/CMakeLists.txt:93-102`）。
- HIP 版の split engine であること。HIP build は `FNX_HIP=1` を定義し、環境変数の読み取り箇所自体も `#if FNX_HIP` 内にあります。非 HIP build では読み取りません（`engine/src/split/src/kernels.cu:1181-1185`; `engine/src/split/CMakeLists.txt:120-127`）。
- split Engine が GPU card ごとの buffer 初期化まで進み、`hc_prepare` が呼ばれること。ここで scratch を確保した後、各 card の device を選んで grid を準備します（`engine/src/split/src/engine.cu:156-183`）。
- 値が正数であること。未設定、0、負数では環境変数による上書きが起きず、GPU の SM 数を基準にした既定 grid になります（`engine/src/split/src/kernels.cu:1173-1185`）。

## 実行時の詳細

Engine の初期化時に各 card で `hc_prepare` が呼ばれ、環境値はその都度読み取られます。読み取った結果は `hc_grid_[dev]` に card ごとに格納され、以後の `hc_read` はその grid を使います。環境変数自体を static cache する処理はありませんが、既に初期化した Engine の grid は実行中の環境変更では更新されません。Engine を新たに初期化すれば、その初期化時点の環境値で再設定されます（`engine/src/split/src/engine.cu:156-183`; `engine/src/split/src/kernels.cu:1155-1170,1173-1190,1205-1208`）。

既定値では grid は `min(SM 数, H_BLOCKS)` です。正数指定時は `min(指定値, H_BLOCKS)` となり、`grid < H_BLOCKS` なら `hc_launch` が `WALK=true` の kernel を起動します。その kernel は `blockIdx.x + k * gridDim.x` の順に担当 block を進め、grid block 数が `H_BLOCKS` に足りない場合も全仕事を処理する構造です（`engine/src/split/src/kernels.cu:1173-1185`; `engine/src/split/src/hc.cuh:113-115,130-134,379-392`）。

## ログと測定値

`hc_prepare` の返した grid が `H_BLOCKS` 未満なら、Engine は stderr に `fnx: card %d: %d SMs: the hc read runs its %d blocks of work on %d\n` を出します。表示上の `%d SMs` に渡される値は実際には有効 grid 数です。このログは `H_BLOCKS` と等しい場合には出ません。未設定でも SM 数が `H_BLOCKS` 未満なら同じログ条件になります（`engine/src/split/src/engine.cu:181-184`; `engine/src/split/src/kernels.cu:1173-1190`）。

不正値では `env_int` が例外を投げるため、grid 設定や上記ログに進みません。この箇所自身は例外を別のログへ変換したり、終了コードを設定したりしません（`engine/src/split/src/env.hpp:33-40`; `engine/src/split/src/engine.cu:181-184`）。ソースコメントには R9700 で 32 block を使った「screen」の記述がありますが、条件を備えた測定結果ではないため性能値としては扱いません（`engine/src/split/src/kernels.cu:1182-1184`）。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40` — 整数全体の parse、未設定時の既定、無効値の例外。
- `engine/src/split/src/kernels.cu:1155-1190,1193-1228` — card ごとの grid 保存、HIP 条件下の読み取り、上限と read kernel への適用。
- `engine/src/split/src/engine.cu:156-184,931-936` — card 初期化時の準備、stderr ログ、実行時の hyper-connection read。
- `engine/src/split/src/hc.cuh:11-14,113-135,379-392` — grid 不足時の複数仕事の処理と kernel variant の選択。
- `engine/src/split/CMakeLists.txt:93-102,120-127` — kernel 分割と HIP split target の `FNX_HIP=1` 定義。
