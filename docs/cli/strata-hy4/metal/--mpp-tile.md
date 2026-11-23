# `--mpp-tile`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner） |
| オプション | `--mpp-tile` |
| 別名 | なし |
| 値 | 整数。MPP dense GEMM のタイル選択値として `64` または `128` を認識する。 |

## 役割

Metal 4 の MPP dense GEMM が選ばれたときに、使用するカーネルタイルを指定します。`64` は `64×64` カーネルを選び、`128` は条件を満たす行列で `128×128` カーネルを選びます。省略時やその他の値では通常の `128×64` カーネルになります。この設定は dense GEMM の分岐に適用され、MoE の grouped GEMM タイルを指定するものではありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:341,481-510`）。

## 使い方

```sh
# MPP dense GEMM で 64×64 タイルを指定
strata-hy4-metal --model model.strata --tokens prompt.ids --mpp-tile 64
```

## 値と既定値

- parser は `atoi` で値を整数化し、初期値は `0` です。オプションを複数回指定した場合、parser の逐次代入により最後の値が残ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1504-1505,1540`）。
- `64` は `mpp_mm_64_64_4` を選びます。
- `128` は、行列の出力幅 `N` が `1024` 以上かつ `128` の倍数で、入力行数 `M` が `128` 以上のときだけ `mpp_mm_128_128_4` を選びます。条件を満たさない場合は `mpp_mm_128_64_4` に戻ります。
- 省略時の `0` および `64`・`128` 以外の整数は `mpp_mm_128_64_4` になります。専用の値検証や拒否処理はありません。数値として解釈できない文字列は `atoi` により `0` となり、既定のタイル分岐になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:490-495,1540`）。
- 値の後続引数がない場合の明示的な引数数チェックは、この parser 箇所では確認できません。値を省略しないでください（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1505,1540`）。

## 実行時の動作

parser の値は `Runner::mpp_tile_arg` に渡されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1743-1746`）。dense GEMM の `lin()` では、MPP カーネルが利用可能で、実際の行数 `M` が `--mpp-min` の閾値以上、重み形式が `F_Q8ROW` ではなく、行列要素数 `N*K` が dequant scratch の容量以下の場合に MPP 分岐へ進みます。その分岐で本オプションの値に応じてタイルカーネルを選びます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:328,332,487-495,557-558`）。

MPP は既定で試行されますが、`--no-mpp` が指定されると試行されず、このオプションは dense GEMM のカーネル選択に作用しません。Metal 4 MPP カーネルのコンパイルに失敗した場合も `mpp_ok` が有効にならず、runner は通常のカーネル群へフォールバックします。コンパイル可否は `--mpp-tile` の値に対する validation ではありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:533-558,1729`）。

## 適用条件と副作用

- 効果があるのは Metal runner の MPP dense GEMM 分岐だけです。実際の `M`、`N`、`K` や重み形式、MPP カーネルの利用可否によっては分岐自体が使われず、この値は参照されません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:487-495`）。
- 選択されるのは dense GEMM カーネル名と grid の寸法です。`64` のとき `ceil(N/64) × ceil(M/64)`、条件を満たす `128` のとき `N/128 × ceil(M/128)`、それ以外は `ceil(N/64) × ceil(M/128)` が指定されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:490-495`）。
- この引数自体にファイル出力や追加のログ出力はありません。MPP が使えるときの scratch buffer 等の確保は runner 初期化に伴う動作であり、タイル値で分岐する処理ではありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:557-569`）。

## 出力とエラー

整数値の範囲検査や不正値エラーはなく、認識しない整数は既定の `128×64` 分岐に流れます。`--mpp-tile` そのものに固有の stdout/stderr メッセージや終了コード設定は確認できません。未知の引数は別の一般処理で `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出し、終了コード `2` で終了します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1540,1604-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1504-1505,1540` — 既定値、引数の取り込み、`atoi` による整数化。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1729,1743-1746` — MPP の有効化指定と runner への値の受け渡し。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:328-332,487-495` — MPP dense GEMM の適用条件とタイル選択。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:533-558` — MPP カーネルのコンパイル試行、フォールバック、scratch 確保。
- 索引上の scope は `docs/cli/README.md:1358-1401` の `strata-hy4-metal`（Metal）節。
