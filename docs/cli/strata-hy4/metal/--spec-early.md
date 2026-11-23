# `strata-hy4-metal --spec-early`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--spec-early` |
| 別名 | なし |
| 値 | 数値を 1 個取り、`atof` で `float` に変換する。ソースに値域検証・クランプはない。 |

## 役割

DFly2 speculative decoding のドラフト候補木を作るとき、候補 frontier の最大到達値 `reach` が指定値を下回った段階で候補木の拡張を早期終了する閾値を設定します。`reach` は校正した受理確率を候補経路に沿って積算した値です。これは生成を有効にするフラグではなく、speculative decoding が実行される場合のドラフト探索量に作用します（`engine/src/hy4flash/metal/hy4_metal_spec.h:437-442, 476-501, 546-568, 576-586`）。

## 使い方

```sh
# DFly2 を使う生成で、ドラフト候補木の早期終了閾値を 0.08 に指定
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 32 --draft dfly2 --spec-early 0.08
```

Metal runner の parser は `--spec-early` の次の引数を読み、`SpecCfg::early_cut` に格納します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1501-1506, 1565`）。例のモデル・token ファイル名は説明用です。

## 値と既定値

- 値は `atof` で変換された `float` です。指定がない場合の `SpecCfg::early_cut` は `0.08f` です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1565`、`engine/src/hy4flash/metal/hy4_metal_spec.h:576-586`）。
- ソースに数値範囲の検査や値のクランプはありません。閾値判定は `early_cut > 0` のときだけ働くため、`0` 以下では早期終了しません（`engine/src/hy4flash/metal/hy4_metal_spec.h:552-555, 565`）。
- 同じオプションを複数回指定すると、引数走査中に同じフィールドへ順次代入され、最後に指定した値が残ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506, 1565`）。
- 引数欠落時の専用エラー処理はありません。parser の `nxt()` は次の `argv` 要素へ進む実装です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506, 1565`）。

## 実行時の動作

設定値は `SpecCfg` としてオフラインの speculative decoding に渡されます。また `--serve` 経路でも `ServeOpts::spec` にコピーされ、サーバーが Spec を使う要求では同じ設定が利用されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1655-1656, 1760-1769, 1929-1937`、`engine/src/hy4flash/metal/hy4_metal_serve.h:233-254, 505-517`）。

Spec の各ドラフト反復では、`--spec-early` の値が実効閾値として渡されるのは `adaptive` が有効、`--spec-cut` の値が負、かつ `--spec-sabotage` が無効な場合です。それ以外では `0` が渡され、早期終了判定は無効です。既定の `adaptive=true` と `cut=-1` では、指定を省略しても既定閾値 `0.08` が使われます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1556-1565`、`engine/src/hy4flash/metal/hy4_metal_spec.h:576-586, 767-770`）。

ドラフト木の構築中、木に少なくとも root と 1 候補が入った後、frontier 内で最大の `reach` が閾値未満なら探索ループを終了します。採用した候補の `reach` が閾値未満の場合も、その候補をさらに展開しません。したがって、この閾値は verification 側で何個の候補を検証するかを直接指定するものではなく、ドラフト木の候補数・形に影響します（`engine/src/hy4flash/metal/hy4_metal_spec.h:546-568`）。

相互作用は次のとおりです。

- `--spec-fixed` は `adaptive=false` にするため、閾値は適用されません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1557`、`engine/src/hy4flash/metal/hy4_metal_spec.h:576-586, 767-770`）。
- `--spec-cut` が `0` 以上なら早期終了閾値は渡されず、`--spec-cut` が検証候補を選ぶ経路になります。負の値なら adaptive の cost model 経路となり、他の条件も満たす場合に `--spec-early` が適用されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1558`、`engine/src/hy4flash/metal/hy4_metal_spec.h:642-658, 767-770`）。
- Spec の実行自体は、オフラインでは生成・bench・parity のいずれかが要求され、draft が `off` でなく、モデルに DFly2 tensor があり、chunk が 16 以上、`--all-logits` でなく、画像入力もない場合に有効です。条件を満たさない場合、この閾値は使用されません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1754-1762`）。
- `--serve` では DFly2 が使える設定で Spec が構築されますが、画像付き要求は `spec_path` から除外されます（`engine/src/hy4flash/metal/hy4_metal_serve.h:233-254, 505-517`）。

## 適用条件と副作用

このオプション自体がファイルを書き換えたり、閾値用の追加処理を常時起動したりはしません。閾値が適用された場合、ドラフト木の frontier 探索が途中終了し、早期終了回数が Spec の stderr 統計 `early_exits` に含まれます。offline speculative decoding では通常の Spec 統計が stderr に出力され、生成 token ID は stdout と `--out` 配下の `gen_ids.txt` に出力されます（`engine/src/hy4flash/metal/hy4_metal_spec.h:552-555, 956-965`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1938-1943`）。`--serve` では Spec の失敗がプロトコルの `ERR spec: ...` として出力されます（`engine/src/hy4flash/metal/hy4_metal_serve.h:510-517`）。

同じ Metal 実装の Spec 機能を使う場面が対象です。CUDA/HIP 版や SYCL 版は別 parser・実装なので、本書の値の適用範囲には含めません。

## 出力とエラー

`--spec-early` 専用の値域エラーや警告は確認できません。値は Spec のレポート先頭にも `early=...` として stderr に表示されます。ドラフト処理が失敗した場合、オフライン経路は `spec: draft failed` を stderr に出して終了コード `1`、serve 経路は `ERR spec: draft failed` をプロトコル出力して終了コード `1` となる経路があります（`engine/src/hy4flash/metal/hy4_metal_spec.h:767-774, 956-965`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1936-1941`、`engine/src/hy4flash/metal/hy4_metal_serve.h:510-517`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1501-1506, 1556-1565` — 初期設定、parser、Spec 関連オプションの代入。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1655-1659, 1754-1772, 1929-1943` — 設定のserve/offline への引き渡し、Spec 有効条件、offline 実行・出力。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:576-586, 642-658, 767-774` — `SpecCfg` の既定値、`--spec-cut` を含む adaptive の選択条件、ドラフト処理。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:437-442, 476-501, 546-572, 956-965` — `reach` の計算、frontier の早期終了・追加展開条件、統計出力。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:233-254, 505-517` — serve 時の Spec 構築・使用条件と失敗経路。
