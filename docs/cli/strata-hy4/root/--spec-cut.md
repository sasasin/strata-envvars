# `strata-hy4 --spec-cut`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP） |
| オプション | `--spec-cut` |
| 別名 | なし |
| 値 | 数値。`atof` で `float` に変換される。 |

## 役割

DFly2 speculative decoding の適応幅を、ドラフト木ノードの confidence 閾値で決めます。既定値 `-1` は閾値選択を使わず、推定スループットに基づく幅選択を行います。`--spec-cut` は `strata-hy4` の CUDA/HIP 実装に対する設定で、Metal と SYCL の同名オプションは別実装です。

## 使い方

```sh
# CUDA/HIP 版で DFly2 を有効にして生成する例
strata-hy4 --model model.strata --tokens prompt.ids --gen 32 --draft dfly2 --spec-cut 0.4
```

通常の CLI 生成では `--draft` の既定値は `auto` であり、`spec_mode` に入る条件は `--draft dfly2`、`--gen` が正、かつ `--dfly-alloc-only` でないことです。そのため、このオプションの適応幅設定を通常生成に反映させる例では `--draft dfly2` を明示します（`engine/src/hy4flash/run/hy4_main.hip.cpp:363-364, 397-410, 701`）。

## 値と既定値

- 省略時は `SpecCfg.cut = -1.f` です（`engine/src/hy4flash/run/hy4_spec.hip.h:18-31`）。
- 指定値は `atof` で `float` に変換され、そのまま `scfg.cut` に格納されます。CLI parser に範囲検証、拒否、clamp はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:408-410`）。したがって、`0` 以上は confidence 閾値として扱われ、負値はコストモデル経路になります。
- 数値としての受理範囲はソースで制限されていません。数値でない文字列などの変換詳細は C ライブラリの `atof` に委ねられます。

## 実行時の動作

`--draft dfly2` の通常生成では `SpecCfg` が `Spec` に渡され、各 speculative 反復で作成されたドラフト木の幅を `choose_m()` が選びます（`engine/src/hy4flash/run/hy4_main.hip.cpp:701, 712-716, 992-1000`、`engine/src/hy4flash/run/hy4_spec.hip.h:74-97, 334-339`）。DFly2 は各ノードの confidence を `node_conf` に格納します（`engine/src/hy4flash/run/hy4_dfly2.hip.h:1133-1135, 1235-1243`）。

- `cut >= 0` かつ adaptive モードでは、`choose_m()` は先頭のドラフトノードから `node_conf[m] > cut` が続く間だけ検証幅を伸ばします。閾値と等しい confidence は条件を満たさず、そのノードより先は幅に含めません。選ばれた幅がアンカーだけの `M=1` なら、ドラフト検証をせず通常の 1 token 推論へ進みます（`engine/src/hy4flash/run/hy4_spec.hip.h:179-195, 336-354`）。
- 負値では、既定の `-1` を含め `choose_m()` は confidence 閾値を使わず、各検証幅の推定 throughput を比較します（同 `:186-194`）。適応モードかつ `cut < 0` の場合に限り、適応コントローラの実測による backoff 更新も行われます（同 `:215-238`）。
- `--spec-fixed` を併用すると `adaptive=false` が先に判定され、常にドラフト木全体の幅を返します。この場合 `--spec-cut` は幅の選択に作用しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:408-410`、`engine/src/hy4flash/run/hy4_spec.hip.h:179-185`）。
- `--spec-cut` が `0` 以上だと `--spec-early` に相当するドラフト早期終了閾値は `0` となり、早期終了判定へ渡されません。早期終了値が有効になるのは `adaptive && cut < 0 && !sabotage && !nodraft` の場合です（`engine/src/hy4flash/run/hy4_spec.hip.h:284-310`）。
- `choose_k()` にも同種の閾値分岐がありますが、この revision では呼び出し箇所を確認できず、生成経路で実際に呼ばれるのは `choose_m()` です（定義: `engine/src/hy4flash/run/hy4_spec.hip.h:127-144`、呼び出し: 同 `:336`）。

## 適用条件と副作用

- 通常 CLI では `--draft dfly2` と正の `--gen` が必要です。`--draft` の有効値は `off`、`dfly2`、`auto` で、それ以外はエラーになります。`dfly2` の初期化に失敗した場合、生成には進まず `dfly2: <理由>` を標準エラーへ出して終了コード 1 です（`engine/src/hy4flash/run/hy4_main.hip.cpp:406, 550-553, 701, 712-716`）。
- `--serve` では parser が同じ `SpecCfg` を `ServeOpts` に渡します。サーバー側で `--draft` が `off` 以外、chunk が 8 以上、かつ DFly2 初期化に成功すると speculative 経路を作り、リクエスト生成時に `Spec::run()` を呼びます。条件を満たさない場合は drafter なしで続行する経路があります（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-570`、`engine/src/hy4flash/run/hy4_serve.hip.h:320-341, 540-556`）。
- オプション自体はファイルやネットワークを操作しません。通常 CLI の speculative 生成経路では生成 ID を標準出力へ出し、`<out-dir>/gen_ids.txt` に書き込みます（`engine/src/hy4flash/run/hy4_main.hip.cpp:992-1011`）。サーバー経路では生成 token をプロトコル応答として送信します（`engine/src/hy4flash/run/hy4_serve.hip.h:546-556`）。

## 出力とエラー

- オプションの値が欠けると、parser の `nxt()` が `ERR --spec-cut needs a value` を標準出力へ出して終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383, 410`）。
- 不明な引数は `unknown arg <引数>` を標準エラーへ出し終了コード 2 です（`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505`）。
- CLI speculative 実行中の失敗は `spec: <理由>` を標準エラーへ出し終了コード 1 です。サーバー経路では `ERR spec: <理由>` をプロトコル応答へ送ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:1000-1005`、`engine/src/hy4flash/run/hy4_serve.hip.h:550-553`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:363-364, 406-410` — CLI 既定設定と parser 登録・型変換。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-31, 74-97` — `SpecCfg` の既定値と `Spec` への設定引き渡し。
- `engine/src/hy4flash/run/hy4_spec.hip.h:127-144, 179-195, 215-238, 284-310, 334-354` — 閾値／コストモデルの幅選択、backoff、早期終了条件、選択幅の実利用。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:1121-1135, 1228-1247` — DFly2 ドラフト木の confidence を生成・保存する箇所。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-570, 701-716, 992-1011`、`engine/src/hy4flash/run/hy4_serve.hip.h:320-341, 540-556` — 適用経路、初期化失敗、CLI と server の出力。
