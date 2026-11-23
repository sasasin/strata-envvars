# `--no-index`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP root） |
| オプション | `--no-index` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

HY4-Flash の疎 attention 層で行う IndexPool によるキー選択を無効にし、疎層でも全キーを使う因果 attention にします。CUDA/HIP 実行ファイルの通常生成と `--serve` のどちらにも渡されます。

## 使い方

```sh
# トークンファイルを使った通常生成で IndexPool 選択を無効にする
strata-hy4 --model model.strata --tokens prompt.bin --gen 128 --no-index

# serve 起動時に同じ設定を適用する
strata-hy4 --serve --model model.strata --no-index
```

## 値と既定値

値は指定しません。省略時は `no_index` が `false` のため IndexPool 選択は有効です。指定すると `true` になり、同じ引数を複数回指定しても真偽値を戻す処理はありません。数値・文字列を値として検証する処理はありません。値を別途付けた場合、その値は次の引数として解析され、認識されない引数なら終了コード `2` で失敗します。

## 実行時の動作

通常生成では parser がフラグを `no_index` に設定し、Runner の `index_on` を `0` にします。`--serve` 経路では `ServeOpts.no_index` に渡し、サーバー側 Runner でも同様に `index_on = 0` にします。Runner は疎層で `index_on` が真のときだけ index 更新・選択を行い、選択リストがある場合に `MLA_LIST` attention を使います。無効時はこれらの選択を行わず、疎層は `MLA_CAUSAL` で全キーを参照します。SWA の窓 attention はこの分岐の対象外です。

IndexPool 選択が始まる既定の系列長しきい値は `index_topk = 2048` ですが、`--no-index` が有効なら選択分岐に入らないためこのしきい値は使われません。Runner 初期化では IndexPool のキャッシュ領域なども別途確保されており、このフラグがそれらの割り当てまで省くことは確認できません。

## 適用条件と副作用

対象は索引上の CUDA/HIP 実装です。Metal と SYCL にも同名フラグがありますが、別 parser・別 scope のため本書の対象外です。フラグによって IndexPool の選択処理は抑止されますが、全キー attention となるため、計算量や性能がどう変化するかはソースだけからは断定できません。ファイル書き込みやネットワーク動作をこのフラグが直接起こす処理は見つかりませんでした。

## 出力とエラー

`--no-index` 固有の出力や validation error はありません。一般の parser は未知の引数に `unknown arg ...` を stderr に出し、serve モードでは `ERR unknown flag ...` も stdout に出して終了コード `2` を返します。このエラー経路は、フラグ自体ではなく、フラグに誤って値を付けるなど未対応引数が残った場合に該当します。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:351-353` — `no_index` の初期値は false。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-383, 493-499` — 引数読み取りと `--no-index` の値なし登録。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:498-505` — 未知引数の stderr / serve 時 stdout 出力と終了コード `2`。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:555-563, 692-696` — serve への転送と通常生成 Runner の `index_on` 設定。
- `engine/src/hy4flash/run/hy4_serve.hip.h:43-49, 307-315` — serve 設定とサーバー側 Runner の `index_on` 設定。
- `engine/src/hy4flash/run/hy4_graph.hip.h:220-221, 2127-2146` — `index_on` の意味、疎層の index 更新・選択、attention mode の切り替え。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1627-1651` — IndexPool 関連領域の初期化・確保が `index_on` 条件なしに行われること。
- `docs/cli/README.md:1277-1284, 1318-1324` — `strata-hy4` CUDA/HIP root scope と対象リンクの確認。
