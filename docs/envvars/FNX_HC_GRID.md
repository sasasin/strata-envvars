# `FNX_HC_GRID`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

HIP 版の任意エンジン `strata-split` が hyper-connection read (`hc_read`) に使う CUDA/HIP grid の block 数を指定します。既定では各カードの multiprocessor 数（SM 数）と上限 80 の小さい方を使います。変数に正数を指定すると SM 数基準の値を置き換え、最大 80 blocks にします。Strata の通常エンジンにはこの設定経路はありません。

## 値と判定

| 環境値 | 結果 |
|---|---|
| 未設定 | `env_int` の既定値 0。SM 数と 80 の小さい方を使用 |
| 整数 0 または負数 | override しない。SM 数と 80 の小さい方を使用 |
| 正の整数 `n` | grid を `min(n, 80)` にする。実 SM 数を超える指定も clamp されずに採用される（ただし 80 が上限） |
| 空文字、整数でない文字列、`long long` の範囲外 | `env_int` が例外を送出し、engine の初期化に失敗 |

値は `parse_whole` により、符号は任意、10 進数字のみの整数として文字列全体を変換します。先頭・末尾の空白、数字の後ろの文字、小数表記は受け付けません。`+2` や `002` は整数として有効です。`std::strtoll` の `ERANGE` も不正値扱いになります。`H_BLOCKS` は `H_NS * H_RG` で、この実装では 80 です。`hc_prepare` の `cap` は engine から既定の 0 で呼ばれるため、正数指定時の上限は `H_BLOCKS` です。

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` で構成され、Linux HIP build として `FNX_HIP=1` を定義した `strata-split-N` を実行すること。CMake は split engine を既定で build せず、CUDA build では `FNX_HIP` 分岐が無効です。
- engine が各カードの `hc_prepare` を実行すること。読み取りは `hc_prepare` の `#if FNX_HIP` 内に限られます。

値の override 自体に CLI 引数や他の環境変数との優先順位はありません。GPU の SM 数を使う既定値を、正数の環境値が置き換えます。

## 実行時の詳細

`Engine` の構築時にカードごとの scratch buffer を作成し、`hc_prepare` を呼びます。同関数はまずデバイスの SM 数を取得し、環境値を読み、カードごとの `hc_grid_` に決定した grid を保存します。この関数で読み取った値を static cache には保存せず、カードごとの `hc_prepare` 呼び出しで評価します。設定値をプロセス稼働中に変更する運用はコード上保証されません。

`hc_read` は保存された grid を取得し、その block 数で各 token 行数に対応する kernel を launch します。決定値が 80 未満なら stderr に `fnx: card ...: <grid> SMs: the hc read runs its 80 blocks of work on <grid>` 形式の行が出ます。このログは `hc_prepare` の戻り値を SM 数と実行 block 数の両方に表示します。決定値が 80 の場合、この条件による行は出ません。

不正値は `env_int` が `FNX_HC_GRID: '<値>' is not a whole number` の例外を送出します。これは `Engine` 構築中に発生し、`sfnx.cpp` の初期化失敗処理が stdout に `ERR ...`、stderr に `sfnx: failed: ...` を出して終了コード 1 で終了します。GPU 属性取得や grid barrier counter の初期化にも失敗経路がありますが、それらは `FNX_HC_GRID` の値判定とは別です。

## 根拠

- 候補一覧の掲載: `docs/envvars/000_envvers.md:541`。
- 任意 split engine と build 条件: `CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:20-27,97-106`。
- 整数全体の parse、未設定時の fallback、不正値例外: `src/split/src/env.hpp:15-21,33-40`。
- 読み取りの HIP 条件、SM 数基準値、正数 override と 80 上限、grid の保存: `src/split/src/kernels.cu:1170-1193`; `H_BLOCKS=80` の定義: `src/split/src/hc.cuh:18-24`。
- engine 構築からの呼び出しと grid 値のログ: `src/split/src/engine.cu:139-142`。
- kernel launch が保存済み grid を使う箇所: `src/split/src/kernels.cu:1205-1229`。
- 初期化例外の表示と終了: `src/split/tools/sfnx.cpp:1051-1062,1027-1035`。
