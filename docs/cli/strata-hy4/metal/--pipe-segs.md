# `--pipe-segs`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Hy4-Flash の Metal runner） |
| オプション | `--pipe-segs` |
| 別名 | なし |
| 値 | 整数として扱う引数。正の値は分割数の目安。実装上の下限は 1。 |

## 役割

Metal runner が大きな GPU dispatch graph を複数の非同期 graph に分けて投入するとき、その分割粒度を調整します。分割された先行 dispatch を GPU で実行している間にホスト側が後続 dispatch を encode できる経路で使われます。

## 使い方

```sh
strata-hy4-metal --model SQ64.strata --tokens ids.txt --gen 32 --pipe-segs 8
```

モデルと token ID ファイルを指定した通常の非 serve 実行で、分割数の目安を 8 にします。

## 値と既定値

- 省略時の値は 8 です。
- 値は `atoi` で整数化されます。数値として解釈できない文字列は 0 になり、負数・0 と同様に、Runner へ渡す直前に `std::max(1, pipe_segs_arg)` で 1 に補正されます。専用の範囲検証エラーはありません。
- 同じ引数を複数回指定すると、引数走査中に値が上書きされ、最後の指定が残ります。

## 実行時の動作

`Runner::run_all()` は dispatch が空なら何もせず、パイプライン encode が有効で dispatch 数が 400 以上の場合にこの値を使います。dispatch 数を値で割った切り上げ数を各区間の大きさとして、dispatch 列を順に複数区間へ分けます。各区間を `run_graph_async` で投入し、返された token をすべて `wait_async` で待って GPU 時間を集計します。条件に満たない場合は `run_graph` で dispatch 全体を実行します。

`--no-pipe` を併用すると `pipe_enc` が無効になり、この分割経路には入りません。値の上限は明示されていません。分割数が dispatch 数より大きい場合も、切り上げ計算により区間サイズは 1 となります。

この値は非 serve runner の `Runner` に設定されます。`--serve` 経路は serve 用設定を組み立てて `hy4_serve_main` を呼び出し、そこで `main` から戻るため、後続の `Runner` 初期化・設定は行われません。したがって `--pipe-segs` は serve の動作に反映されません。

## 適用条件と副作用

- 効果があるのは非 serve 実行で、`--no-pipe` がなく、`run_all()` に渡された dispatch 数が 400 以上の場合です。
- Metal runner 内の graph 分割・非同期投入と待機にだけ影響します。値自体をファイルやモデル設定へ保存する処理は確認できません。
- 値の妥当性について警告やエラーを出す検証はありません。引数を省略して値を付けない場合の安全なエラー処理は parser に見当たらず、`argv[++i]` を読みます。その入力形での結果は本調査では実行して確認していません。

## 出力とエラー

`--pipe-segs` 自体に専用の出力・失敗経路はありません。未知のフラグは標準出力に `ERR unknown flag ...`、標準エラーに `unknown arg ...` を出して終了コード 2 になりますが、このオプションは parser に登録されています。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1492-1494` — `--no-pipe` の既定値と `pipe_segs_arg = 8` の初期値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1551-1553` — argv 走査と `--pipe-segs` の値取得（`atoi`）。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:462-478` — Runner の既定値、400 dispatch 以上の条件、区間計算、非同期投入・待機、および通常実行への分岐。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1632-1660` — serve 分岐が serve 本体を呼び出して返ること。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1720-1733` — 非 serve runner への `pipe_enc` と 1 以上に補正した分割数の設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1609` — 未知フラグ時の出力と終了コード。
