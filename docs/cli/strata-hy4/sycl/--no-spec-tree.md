# `strata-hy4-sycl --no-spec-tree`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-sycl` |
| コマンド | `strata-hy4-sycl`（SYCL backend） |
| オプション | `--no-spec-tree` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

DFly2 による推測デコードで Tree-8 の分岐ドラフトを無効にし、各深さで第1候補だけを伸ばす設定です。推測デコードそのものを無効にするものではありません。通常の生成経路では `--draft dfly2` と正の `--gen` が指定された場合に設定が使われます。serve 経路ではドラフターが有効になり、リクエストが推測デコードを使う場合に適用されます。

## 使い方

```sh
# DFly2 推測デコードを使いながら Tree-8 の分岐を無効化する
strata-hy4-sycl --model model.strata --tokens prompt.ids --draft dfly2 --gen 64 --no-spec-tree
```

serve で使用する場合も同じフラグを起動引数に指定します。たとえば `--serve --native model.strata --draft dfly2 --no-spec-tree` のようにします。

## 値と既定値

このフラグは値を取りません。`SpecCfg::tree` の既定値は `true` で、指定すると `false` になります。数値や `0` / `1` を付ける構文はありません。複数回指定した場合も同じ `false` を代入します。対になる `--spec-tree` もあり、両方を指定した場合は引数走査中の最後の指定が残ります。

## 実行時の動作

parser は `--no-spec-tree` を見つけると `scfg.tree = false` とし、その `SpecCfg` を通常の DFly2 `Spec` に渡すか、serve 設定に格納します（`engine/src/hy4flash/sycl/sy_main.cpp:96,187-189,247,379-381`）。

推測デコードのドラフト生成は `cfg.tree` を `draft_tree` の `enable_tree` 引数として渡します（`engine/src/hy4flash/sycl/sy_spec.h:201-205`）。無効時は greedy モードの第2候補分岐と、確率的モードの第2兄弟候補生成を行いません。一方で第1候補の展開は続き、選択した候補を線形のドラフトとして検証します（`engine/src/hy4flash/run/hy4_dfly2.hip.h:1175-1184,1200-1219`; `engine/src/hy4flash/sycl/sy_spec.h:234-249`）。したがって、通常の DFly2 ドラフト・検証の仕組みを止める指定ではありません。

## 適用条件と副作用

- 通常の非 serve 経路では `--draft dfly2` かつ `--gen` が正の場合だけ推測デコード経路に入ります。`--gen` が 0 以下、または `--draft` が `off`（既定）ならこの設定によるドラフト分岐への効果はありません（`engine/src/hy4flash/sycl/sy_main.cpp:250,279,379-381`）。
- `--serve` 経路では parser が設定を `ServeOpts` に渡します。serve 側は `--draft` が `off` でなく、モデルに drafter があり、chunk が 8 以上の場合に推測デコードを試みます。`auto` で drafter 初期化に失敗すれば推測デコードを使わず、`dfly2` を明示して失敗した場合はエラーになります（`engine/src/hy4flash/sycl/sy_main.cpp:241,247`; `engine/src/hy4flash/sycl/sy_serve.h:253-278,303-307`）。
- このフラグ自身によるファイル出力や環境変数変更は確認できません。推測デコードが実行された場合、既存の生成結果・統計出力は通常どおりです。レポートには tree 設定値が表示されます（`engine/src/hy4flash/sycl/sy_spec.h:414-420`）。

## 出力とエラー

このフラグ専用の警告・エラー出力はありません。オプションの値を要求する処理もありません。値を後続に置くとその文字列は次の引数として解釈され、認識されない引数なら `unknown arg ...` を stderr に出して終了コード 2 になります（`engine/src/hy4flash/sycl/sy_main.cpp:107-115,188-196`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:96,187-189` — `SpecCfg` の生成と parser。値なしで `tree=false` を設定し、隣接する `--spec-tree` との指定順も決まる。
- `engine/src/hy4flash/sycl/sy_spec.h:21-31` — `tree` の既定値と設定の説明。
- `engine/src/hy4flash/sycl/sy_spec.h:201-205` — speculative decode が設定をドラフト生成に渡す箇所。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:1175-1219` — `enable_tree` によって追加分岐を省く箇所。
- `engine/src/hy4flash/sycl/sy_spec.h:234-249,414-420` — 線形ドラフトの検証とレポート出力。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,279,379-381`、`engine/src/hy4flash/sycl/sy_serve.h:253-278,303-307` — standalone / serve で設定が使われる条件。
- `engine/src/hy4flash/sycl/sy_main.cpp:107-115,190-196` — 値欠落時の共通 parser 処理と未知引数の失敗経路。

調査開始時の Strata checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。CLI の help は実行せず、ソースを根拠にしています。
