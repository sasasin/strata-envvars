# `strata-hy4-sycl --dbg-layers`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL） |
| オプション | `--dbg-layers` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

通常推論で `--dump` と併用すると、MoE 層の中間テンソルを層別の NumPy `.npy` ファイルとして保存します。単独では `dbg` フラグを立てるだけで、層別保存の条件を満たしません。parser は `--dbg-layers` を値なしの真偽値として扱い、Runner に渡します（`engine/src/hy4flash/sycl/sy_main.cpp:99-100, 165-168, 280-287`）。

## 使い方

```sh
strata-hy4-sycl --model model.strata --engram engram.strata \
  --tokens ids.txt --dump --dbg-layers --out ./layer-dumps
```

`--model`、`--engram`、`--tokens` は通常推論に使う入力です。例の `--out` はダンプ先ディレクトリを指定します。出力先は既定で `.` です（`engine/src/hy4flash/sycl/sy_main.cpp:93-95, 152-155, 251-253`）。

## 値と既定値

値を取りません。既定値は無効（`dbg = false`）で、指定すると `true` になります。同じ指定を複数回しても真偽値を再設定するだけです。範囲検証や値検証はありません（`engine/src/hy4flash/sycl/sy_main.cpp:99, 107-116, 165-168`）。

## 実行時の動作

通常推論では `dbg` を `Runner::dbg_layers` に設定します。層別の追加保存は `dump && dbg_layers` が真の場合にだけ実行され、各対象層について `L<層番号>_z_folded.npy`、`L<層番号>_topk_idx.npy`、`L<層番号>_topk_w.npy`、`L<層番号>_z_out.npy`、`L<層番号>_shared_out.npy` を `dump_dir` 配下に書きます。テンソルは float32 で、形状は順に `[T,1536]`、`[T,16]`、`[T,16]`、`[T,1536]`、`[T,HID,F3]` です。条件分岐とファイル名・形状は `engine/src/hy4flash/sycl/sy_graph.h:1215-1227`、float32 `.npy` 形式での書込は同 `:52-71` にあります。

この経路はデバイス処理の待機、ホストへのコピーを行ってから保存します（`engine/src/hy4flash/sycl/sy_graph.h:1215-1226`）。`--dump` は別の中間出力も有効にし、`dump_dir` を `Runner` に渡します（`engine/src/hy4flash/sycl/sy_main.cpp:284-288`、`engine/src/hy4flash/sycl/sy_graph.h:797-807, 1412-1419`）。したがって `--dbg-layers` 自体は出力先を指定せず、保存を有効にするには `--dump` が必要です。

## 適用条件と副作用

- 対象は SYCL 実装の通常推論経路です。`--serve` では parser がフラグを受理しますが、serve 分岐は `Runner` を作って `dbg_layers` を設定する前に `hy4s_serve_main` へ移るため、層別ダンプへの効果は確認できません（`engine/src/hy4flash/sycl/sy_main.cpp:165-168, 215-249, 280-287`）。
- `--dump` なしでは層別保存の条件を満たさず、追加ファイルは保存されません（`engine/src/hy4flash/sycl/sy_graph.h:1215`）。
- 指定した `--out` ディレクトリへのファイル書込が発生します。保存関数は `fopen(path, "wb")` を使い、開けない場合はその場で戻ります。また `fwrite` の戻り値を検査しません。そのためディレクトリが存在しない、または書込に失敗した場合でも、この関数から CLI へエラーは返されません（`engine/src/hy4flash/sycl/sy_graph.h:52-71`）。ディレクトリの自動作成はこの保存コードでは確認できません。

## 出力とエラー

`--dbg-layers` に値を付ける構文ではありません。フラグの後ろに別の引数を置くと、それは別の CLI 引数として解析されます。認識されない引数は stderr に `unknown arg <引数>` を出して終了コード `2` を返します（`engine/src/hy4flash/sycl/sy_main.cpp:107-116, 165-168, 190-197`）。層別ファイルのオープン失敗・書込失敗については、保存関数がエラーを通知しないため、CLI の明示的な失敗出力は確認できません（`engine/src/hy4flash/sycl/sy_graph.h:60-71`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:99, 107-116, 165-168` — フラグの初期値、値を取らない parser 分岐。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-249, 280-287` — serve と通常推論の分岐、Runner への値の設定。
- `engine/src/hy4flash/sycl/sy_graph.h:320-323, 1215-1227` — Runner の状態と追加ダンプ条件・出力名・形状。
- `engine/src/hy4flash/sycl/sy_graph.h:52-71, 797-807, 1412-1419` — `.npy` 書込、通常ダンプ条件と他の中間出力。
- `docs/cli/README.md:1452-1460` — `strata-hy4-sycl` の SYCL scope と索引上の配置。
