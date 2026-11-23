# `--no-mpp`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--no-mpp` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

Metal runner の初期化で Metal 4 matmul2d（MPP）カーネルのコンパイルを試さず、通常カーネルで実行させます。Metal 実装の通常実行で MPP カーネルとの切り分けをするときに使えます。`--serve` 経路にはこの設定が引き継がれません。

## 使い方

```sh
# オフライン実行で MPP カーネルを無効にする
strata-hy4-metal --model model.strata --tokens ids.txt --no-mpp
```

## 値と既定値

値は不要です。指定すると parser の `no_mpp` が `true` になり、指定しない場合は `false`（MPP を試行）です。値の validation はなく、同じフラグを複数回指定しても同じ真偽値を再設定します。parser は位置引数として値を消費しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1527`）。

## 実行時の動作

offline 実行では `r.mpp_try = !no_mpp` として runner に渡されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1720-1730`）。初期値が `true` の `mpp_try` が false になると、runner の初期化は MPP カーネル群を含む `compile_try` を飛ばし、ベースの Metal カーネル群をコンパイルします。そのため `mpp_ok` と `mpp_flash_ok` は false のままになり、MPP 用 scratch buffer の確保も行いません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:328-332, 522-558`）。

この状態では dense GEMM は通常の線形カーネル分岐へ進み、MPP grouped GEMM を使う MoE prefill 分岐も選ばれません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:481-510, 1182-1185`）。Attention の MPP Flash 経路も `mpp_flash_ok` が false のため選ばれず、通常の simdgroup 系経路などへ進みます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1052-1079`）。`--mpp-min`、`--moe-mm-min`、`--mpp-tile` など MPP 有効時の閾値・タイル指定は、MPP が無効ならこれらの MPP 分岐を有効にしません。

## 適用条件と副作用

- `--serve` を指定すると、main は `ServeOpts` を組み立てて `hy4_serve_main` に渡しますが、`ServeOpts` に `no_mpp` 相当の項目はなく、server 側の `Runner` は `mpp_try` の既定値 `true` のまま初期化されます。そのため `--serve --no-mpp` では MPP 試行は無効になりません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1495, 1527, 1636-1674`、`engine/src/hy4flash/metal/hy4_metal_serve.h:24-38, 219-242`）。
- offline の画像入力では、runner とは別に Vision encoder がロードされます。`--no-mpp` がこの encoder のカーネル選択にも適用されるかは、確認した呼び出し経路では設定の受け渡しを確認できませんでした（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1782`）。
- フラグ自身によるファイル書き換えやネットワーク通信はありません。Metal カーネルのコンパイルと GPU 実行経路の選択に作用します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:533-558`）。

## 出力とエラー

`--no-mpp` が指定されていない場合、MPP コンパイルが失敗すると fallback の診断を stderr に出すコードがあります。`--no-mpp` 指定時は MPP 試行自体をスキップするため、この MPP コンパイル失敗診断は出ません。ベースカーネルのコンパイルが失敗した場合の具体的な出力・終了コードは、このオプションの分岐だけからは確認できません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:533-556`）。未知の引数は `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出して終了コード 2 ですが、`--no-mpp` 自体は parser に登録されています（同:1527, 1603-1608）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1527` — Metal CLI parser のフラグ登録と既定値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:328-332, 522-558` — runner の MPP 状態、コンパイル試行と fallback。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:481-510, 1052-1079, 1182-1185` — dense GEMM、attention、MoE の MPP 利用条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1720-1730, 1760-1765` — offline 実行で runner に設定を渡す経路。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674`、`engine/src/hy4flash/metal/hy4_metal_serve.h:24-38, 219-242` — server 設定と runner 初期化。`--no-mpp` が server に伝わらない根拠。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1782` — offline 画像入力での別個の Vision encoder 初期化。
