# `--index-topk`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--index-topk` |
| 別名 | なし |
| 値 | 整数。圧縮 index attention の key リスト上限として渡される |

## 役割

圧縮 indexer が過去の pool から選ぶ key リストの規模を決めます。生成時の語彙サンプリング用 `--top-k` とは別の値です。指定値は通常推論・Metal の `--serve` のどちらでも Runner に渡され、index attention のバッファ容量、選択 pool 数、疎な key リストを使い始める位置に反映されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1519,1644,1723-1724`）。

## 使い方

```sh
# 通常の Metal 実行で index key 上限を 2048 にする
strata-hy4-metal --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --index-topk 2048

# serve モードでも同じ設定を Runner に渡す
strata-hy4-metal --model SQ64.strata --engram Engram-Q8.strata --serve --index-topk 2048
```

## 値と既定値

- 省略時は `2048` です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491`）。
- parser は `atoi` で整数に変換し、正値・範囲・pool 単位への整合性を検査しません（同 `:1519`）。したがって数値でない文字列は `atoi` の規則により 0 になります。負数や 0 も parser では拒否されません。
- `c.kpool` で割った値から保持 pool 数を作り、Metal kernel に上限値を渡します（同 `:881-895`; `engine/src/hy4flash/metal/hy4.metal:1321-1329`）。受理値の安全な範囲や、0・負数・pool 単位で割り切れない値に対する正常動作はソース上で保証されていません。範囲外値は指定しないでください。

## 実行時の動作

通常経路では Runner が key リスト用領域を `Tc * (index_topk + 8)` 個分確保し、index 選択 kernel に `n_top = index_topk / c.kpool - 1` と `index_topk` を渡します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:576-577,626,881-895`）。Metal kernel は過去の pool のうち上位 `n_top` 個を選び、各 pool の 4 token を key リストに出力した後、現在 token が属する pool 内の因果的な token を追加します。まだ `grp <= n_top` の位置では、過去の選別をせず位置 0 から現在位置までをリストにします（`engine/src/hy4flash/metal/hy4.metal:1319-1330,1385-1421`）。

非 SWA 層で index が有効なとき、各 forward で index を更新し、`end_pos > index_topk` になってから選択済み key リストを attention に使います。SWA 層はこの分岐に入らず window attention を使います（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1032-1050`）。`--no-index` を付けると index 更新・リスト選択を無効にして causal/window mode になりますが、通常経路の key バッファ確保自体は Runner 初期化時に行われます（同 `:626,1032-1040,1047-1050,1723-1724`）。

`--serve` では値を `ServeOpts` に格納し、serve 側の Runner に引き継ぎます（同 `:1636-1645`; `engine/src/hy4flash/metal/hy4_metal_serve.h:219-225`）。DFly2 の speculative 経路でも index key リストを捕捉・再利用するバッファ stride に使われます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:827-848,1281-1282`; `engine/src/hy4flash/metal/hy4_metal_spec.h:229-230,301-311`）。

## 適用条件と副作用

- index key 上限が働くのは index 有効時の非 SWA 層です。`--no-index` は選択そのものを止めます。`--load-only` はモデル読み込み後、Runner の作成前に終了するため、この値を使った推論処理は行いません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1630-1636`）。
- 値を増やすと、少なくとも Runner の key buffer 容量は比例して増えます。DFly2 用の捕捉 buffer も同じ上限に応じて確保されます（同 `:626,836-837`）。
- 負数などでこの計算がどう失敗するか、Metal device の割当失敗時にどの診断・終了コードになるかは、このオプション固有の経路として確認できません。parser に値検査がないため、メモリ量を含む実行時の結果を推測していません。

## 出力とエラー

この値に対する parser 固有のエラー表示はありません。範囲検証も見つかりません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1519`）。未知の引数には別途 stdout の `ERR unknown flag ...` と stderr の `unknown arg ...` を出して終了コード 2 を返しますが、`--index-topk` 自体は認識されます（同 `:1604-1608`）。不正値や割当失敗時の具体的なエラー出力・終了コードは、該当する明示的な処理をソースから確認できませんでした。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1519` — 既定値と parser（`atoi`）。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:576-577,626,881-895` — Runner の領域確保と index 選択 kernel の引数。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1032-1050` — SWA/index の適用条件、切替位置、attention mode と上限の設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1645,1723-1724`; `engine/src/hy4flash/metal/hy4_metal_serve.h:219-225` — load-only の早期終了、および serve / 通常経路から Runner への値の受け渡し。
- `engine/src/hy4flash/metal/hy4.metal:1319-1330,1385-1421` — pool の選択、4 token 単位の key 出力と現在 pool の追加。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:827-848,1281-1282`; `engine/src/hy4flash/metal/hy4_metal_spec.h:229-230,301-311` — DFly2 speculative 経路の key list capture と再利用。
