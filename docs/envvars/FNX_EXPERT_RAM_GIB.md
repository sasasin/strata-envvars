# `FNX_EXPERT_RAM_GIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

all-cards split engine の Flash-Next モデルで、ルーティングされた experts のうち、使用頻度の低いものを VRAM の初期配置から外してホスト RAM に置く量を GiB で指定する。値を省略すると 3 GiB 分を対象にする。`off` は ExpertCache を使わず、全 expert を VRAM に置く指定である。ExpertCache を使う場合、RAM に置いた expert は mapped page-locked host memory に保持され、VRAM の slot にない expert は cache の slot に読み込まれる。`off` と `FNX_ARENA=0` の組み合わせでは cache と arena を使わず全 expert を VRAM に置く。`engine/src/split/src/model.cpp:1514-1565`、`engine/src/split/src/model.cpp:286-315, 341-379`。

この環境変数は all-cards split engine のモデル読み込み設定で、通常の layer-split engine の設定ではない。`FNX_27B=0` の split ターゲットが CUDA と HIP 向けに定義されている。Flash-Next の通常の `PLAIN` load は `!FNX_27B` のときだけ読み取り関数を呼ぶ。`engine/src/split/CMakeLists.txt:120-146`、`engine/src/split/src/model.cpp:1485-1488`。

## 値と判定

`std::getenv` で環境変数の有無を調べ、設定されていれば、値が完全一致で小文字 `off` の場合だけ cache を無効にする。それ以外は `std::strtod` で数値変換し、変換できない、末尾に未消費文字が残る、または値が 0 未満なら例外にする。`errno` や有限値の検査はない。`engine/src/split/src/model.cpp:1520-1533`。

この値を読む箇所に CLI 引数や設定ファイルの fallback はなく、split engine のプロセス環境から直接取得する。server が split 用 config を組み立てる場合は `base.env` の同名値を `off` で上書きする。`engine/src/split/src/model.cpp:1520-1529`、`terminal/strata_control/split_engine.py:273-284`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| `FNX_27B=0` の split engine で `choose_residency()` を呼ぶ場合 | `3.0` GiB | `0`、`1`、`3.5`、` 3`（先頭空白を含む数値） | 空文字、`off `、`OFF`、`0anything`、`3x`、`-1` |
| 同上、cache 無効化 | ― | `off`（大文字小文字を区別） | `OFF` は数値変換に失敗 |

`strtod` が受け付けた数値は、末尾まで消費され、負数でなければパーサーの検査を通る。`NaN` や無限大は明示的に拒否されていないが、GiB 値から byte 数への変換結果は通常の値として保証されないため、使用可能な設定値として扱えない。`-0` は C++ の比較で 0 未満ではないため、負数拒否には該当しない。`engine/src/split/src/model.cpp:1527-1531, 1535`。

要求 GiB は byte 数に換算され、expert 単位で RAM 側へ移す。端数の expert はないため実際の配置量は要求値と一致するとは限らない。各 expert-size pool には `EXPERT_WINDOW_SLOTS` 分を残す必要があり、その下限を満たせない配置は失敗する。`engine/src/split/src/model.cpp:1535, 1562-1565`、`engine/src/split/src/expert_residency.hpp:19-57`。

## 有効になる条件

- 対象は all-cards split engine の Flash-Next 経路。CUDA/HIP 向け split ターゲットは `FNX_27B=0` でビルドされる。27B の `PLAIN` load は `choose_residency()` を呼ばない。`engine/src/split/CMakeLists.txt:120-146`、`engine/src/split/src/model.cpp:1485-1488`。
- `FNX_EXPERT_RAM_GIB=off` を使う場合、`FNX_ARENA=0` が必要。`FNX_ARENA` が未設定なら arena は有効扱いとなり、`off` との組み合わせは例外になる。`FNX_ARENA` 自体は文字列 `0` または `1` のみ有効。`engine/src/split/src/model.cpp:1521-1533`。
- 数値を使う場合は ExpertCache が有効になり、expert 使用頻度のプロファイルを読み込む。`FNX_EXPERT_PROFILE` が設定されていればそのパス、未設定なら `<FNX_DIR>/data/expert-routes.bin` を使う。ファイルの tallies 数または長さが想定と異なると失敗する。`engine/src/split/src/model.cpp:1534-1544`。
- 頻度の低い expert から移す順序は、decode と prompt の tallies をそれぞれ合計で正規化し、両者を等しく重みづけした値を expert byte 数で割った score による。これは値の容量指定とは別に、どの expert を RAM に置くかを決める。`engine/src/split/src/model.cpp:1546-1563`。
- 数値指定でも pool ごとの最低 slot 数を保てない場合は配置できず、例外となる。arena が有効で初期配置後も VRAM が足りない場合、Engine は `ram_extra` を加えて配置をやり直す。`engine/src/split/src/expert_residency.hpp:37-56`、`engine/src/split/src/engine.cu:326-357`。
- Terminal の server が all-cards split 用設定を作ると、既存の `base.env` を展開した後に `FNX_ARENA=0` と `FNX_EXPERT_RAM_GIB=off` を設定する。この経路では base の同名環境設定は上書きされ、RAM cache を使わない。`terminal/strata_control/split_engine.py:267-284`。

## 実行時の詳細

通常の `PLAIN` load ではモデル構築時に `choose_residency()` が呼ばれ、その時点の環境を読み、expert の RAM/VRAM 配置計画を作る。`ATTACH` load は `place_experts()` を呼び、そこから同じ設定を読み直す。`HOLD` load は holder 側で配置せず、worker の配置を待つ。プロセス起動時に一度だけ保存する static cache はなく、`place_experts()` も `choose_residency()` を呼ぶ。arena の初期化で VRAM 不足が見つかると、既存配置を解放し、`ram_extra` を足して配置をやり直すため、その経路では環境変数も読み直される。`engine/src/split/src/model.cpp:1478-1488, 1514-1565, 1587-1604`、`engine/src/split/src/model.hpp:234-238`、`engine/src/split/src/engine.cu:333-357`。

cache を使う場合、expert 全体の host copy を mapped page-locked host memory に置き、resident と判定した expert の slot を VRAM に確保して初期データをコピーする。arena 使用時は最大 pool の slot を Engine の arena に渡す。`off` かつ arena 無効なら `resident` は空のままなので、モデル読み込み時の routed experts は cache 経由でなく VRAM に配置される。`engine/src/split/src/model.cpp:286-315, 857-895`、`engine/src/split/src/model.cpp:1514-1533`。

## ログと測定値

数値指定で配置計画が成立すると、stderr に `fnx: <count> of <total> routed experts (<GiB> GiB) in RAM, ranked by <profile>` が出る。`ram_extra` による追加配置があれば括弧内に理由と数が付く。`off` ではこの配置ログも profile 読み込みも行わない。`engine/src/split/src/model.cpp:1534-1565`。

不正な数値は `fnx: FNX_EXPERT_RAM_GIB: GiB (0 or more) or off, not '<value>'`、arena 有効のまま `off` にすると `fnx: FNX_EXPERT_RAM_GIB=off needs FNX_ARENA=0 (the arena lends the cache's slots)` の例外になる。Engine 起動中の例外は stdout の `ERR <理由>` と stderr の `sfnx: failed: <理由>` を出し、終了コード 1 で終了する。`engine/src/split/src/model.cpp:1530-1533`、`engine/src/split/tools/sfnx.cpp:1094-1102, 1123-1136`。

配置に必要な slot 数を割る場合は `expert residency: requested RAM placement leaves too few slots for a window in every size pool` などの例外、profile が想定サイズでない場合は `fnx: FNX_EXPERT_PROFILE <path>: not <count> tallies` になる。arena の VRAM 不足は coldest experts を追加で RAM に移し、8 回の再配置後にも不足すれば `FNX_ARENA: VRAM still short after placing the experts again 8 times` で失敗する。`engine/src/split/src/expert_residency.hpp:37-56`、`engine/src/split/src/model.cpp:1541-1544`、`engine/src/split/src/engine.cu:345-357`。

## 根拠

- `engine/src/split/src/model.cpp:1514-1565` — 値の読み取り、判定、既定値、profile、配置計画、配置ログ。
- `engine/src/split/src/expert_residency.hpp:19-57` — whole-expert 配置と各 pool の最低 slot 数。
- `engine/src/split/src/model.cpp:286-315, 341-379, 857-895, 1485-1488, 1587-1604` — host copy、VRAM cache、読み取り呼び出し、配置の再実行。
- `engine/src/split/src/engine.cu:326-357` — arena 条件での追加 RAM 配置と再試行上限。
- `engine/src/split/tools/sfnx.cpp:1094-1102, 1123-1136` — 起動時例外の表示と終了。
- `engine/src/split/CMakeLists.txt:120-146` — all-cards split ターゲットの CUDA/HIP build macro。
- `terminal/strata_control/split_engine.py:267-284` — server が split engine 用環境値を設定する箇所。
