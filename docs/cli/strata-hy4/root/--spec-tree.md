# `--spec-tree`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP root） |
| オプション | `--spec-tree` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換。0 は無効、それ以外は有効 |

## 役割

DFly2 speculative decoding の draft 検証で Tree-8 の分岐候補を使うかを切り替える。既定は有効で、ドラフターが不確かな位置に複数候補を作れた場合、候補を木構造にして一度の検証 chunk にまとめる。無効にするとドラフトは線形になり、推測デコード自体は継続する。

## 使い方

```sh
# オフライン生成で Tree-8 の分岐を無効にする
strata-hy4 --model model.strata --tokens prompt.ids --draft dfly2 --gen 64 --spec-tree 0

# serve の DFly2 生成で Tree-8 の分岐を有効にする（既定値を明示）
strata-hy4 --serve --model model.strata --draft dfly2 --spec-tree 1
```

## 値と既定値

- `SpecCfg::tree` の初期値は `true`。したがって省略時は有効（`engine/src/hy4flash/run/hy4_spec.hip.h:18-30`）。
- parser は値を `atoi` で整数変換し、0 かどうかで bool にする。`0` は無効、`1` など 0 以外は有効。値域検証やエラー処理はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,408-414`）。
- 値なしの場合、共通の値取得処理が `ERR --spec-tree needs a value` を標準出力へ出して終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383`）。
- `atoi` のため、数値として解釈できない値や空文字列は 0 相当となり、拒否されず無効になります。複数回指定した場合は parser が順に処理し、最後に設定された値が残ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,413`）。

## 実行時の動作

parser は値を `scfg.tree` に格納します。`--serve` 経路では `scfg` を `ServeOpts::spec` に渡し、サーバー側は DFly2 が利用可能な場合にその設定を `Spec` に渡します（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-577`、`engine/src/hy4flash/run/hy4_serve.hip.h:319-341`）。オフライン経路では、`--draft dfly2`、`--gen` が正数、かつ `--dfly-alloc-only` ではない場合に speculative mode となり、その `Spec` に `scfg` が渡ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:701-717,992-1000`）。

Spec はドラフト木生成時に `cfg.tree && !cfg.sabotage` を `DFly2::draft_tree` へ渡します。無効なら兄弟候補を追加せず、有効なら greedy 経路では上位2候補の条件を満たす場合、確率的 sampling 経路では分布からの条件を満たす場合に枝を作ります（`engine/src/hy4flash/run/hy4_spec.hip.h:284-314`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:1114-1122,1157-1183,1195-1219`）。生成されたノードは最大 `min(K + 1, DFLY_BMAX)` 個で、`K` は `--spec-k` の設定に関係します（`engine/src/hy4flash/run/hy4_dfly2.hip.h:1223-1231`）。

検証対象に分岐があれば `Runner::forward_chunk` に木を渡し、なければ線形 chunk として処理します（`engine/src/hy4flash/run/hy4_spec.hip.h:356-372`）。したがって `--spec-tree 0` は speculative decoding 全体を止める指定ではありません。`--spec-sabotage` や `--spec-nodraft` が有効なときも `!cfg.sabotage` により木の分岐は抑止されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:425-428`、`engine/src/hy4flash/run/hy4_spec.hip.h:310`）。

## 適用条件と副作用

- DFly2 を使う speculative decoding が実際に動くときに適用されます。オフライン実行では `--draft dfly2 --gen N`（`N > 0`）が必要です。サーバーでは `--serve` に加えてドラフターが利用可能である必要があります。サーバーは chunk が 8 未満の場合や drafter 初期化失敗時に speculative mode を使わず続行する実装です（`engine/src/hy4flash/run/hy4_main.hip.cpp:701-717`、`engine/src/hy4flash/run/hy4_serve.hip.h:319-341`）。
- `--spec-tree` 自体はモデル・GPU・ファイルを直接変更せず、生成中のドラフト候補と検証経路を切り替えます。生成処理の通常の出力・GPU 計算は発生します。
- ソース上で、ツリー分岐の有効化は greedy / probabilistic の両方に渡されています。ただし候補数や枝の採用条件はドラフト状態・確率・`K` などにも依存し、値を有効にしただけで毎回分岐するとは限りません（`engine/src/hy4flash/run/hy4_dfly2.hip.h:1157-1183,1195-1219,1223-1231`）。

## 出力とエラー

オプション値の妥当性エラーは実装されていません。ドラフト生成または検証の失敗は speculative run のエラー経路で `spec: <理由>` を標準エラーへ出し、オフライン実行は終了コード 1 を返します（`engine/src/hy4flash/run/hy4_spec.hip.h:310-314,367-372`、`engine/src/hy4flash/run/hy4_main.hip.cpp:1000-1005`）。serve 実行では各要求の応答にエラーが返される経路があります（`engine/src/hy4flash/run/hy4_serve.hip.h:527-529,533-556`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:408-414` — CUDA/HIP root parser の登録と `atoi` 変換。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-30,284-314,356-372` — 既定値、木生成への設定伝達、分岐木と線形 chunk の検証経路。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:1114-1122,1157-1183,1195-1219,1223-1231` — Tree-8 の候補生成・分岐条件・ノード上限。
- `engine/src/hy4flash/run/hy4_serve.hip.h:319-341,527-556` — サーバー経路でのドラフター利用条件と speculative run。

調査範囲は索引が指定する CUDA/HIP root parser とその実装経路です。Metal/SYCL の同名または類似オプションの挙動はこの文書の対象に含めていません。
