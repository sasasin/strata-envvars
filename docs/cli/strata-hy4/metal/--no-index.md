# `strata-hy4-metal --no-index`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--no-index` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

HY4-Flash Metal runner の非 SWA 層で使う圧縮 index attention を無効にし、選択済み key list を使う attention から causal attention に切り替えます。SWA 層の window attention はこのフラグの対象外です。オフライン実行と `--serve` の両方で有効です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1032-1050,1636-1646,1723-1724`、`engine/src/hy4flash/metal/hy4_metal_serve.h:219-225`）。

## 使い方

```sh
# offline 推論で圧縮 index を使わずに実行
strata-hy4-metal --model model.strata --tokens ids.txt --no-index

# serve モードでも同じ設定を適用
strata-hy4-metal --model model.strata --serve --no-index
```

## 値と既定値

- 値を取りません。parser は `--no-index` を見つけると真偽値 `no_index` を `true` にします。既定値は `false` で、指定しない場合は index が有効です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1490,1520`）。
- parser に専用の範囲 validation はなく、複数回指定しても同じ `true` を再設定するだけです。直後に値らしい引数を置くとその値は消費されず、次の引数として解釈されます。未知の引数なら `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出して終了コード 2 で終了します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1520,1604-1608`）。

## 実行時の動作

offline 経路では `no_index` から `Runner::index_on` を 0 に設定します。各 forward で非 SWA 層に対して行う index 更新は `!swa && index_on` の条件下にあり、index が有効なら `end_pos > index_topk` のときだけ候補選択と key list の利用に進みます。`--no-index` 指定時はこのブロックを通らず、attention mode は非 SWA 層で `MODE_CAUSAL`、SWA 層で従来どおり `MODE_WINDOW` になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1032-1050,1723-1724`）。

`--serve` 経路でも `ServeOpts` に値をコピーし、serve 用 Runner の `index_on` を 0 にします（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1646`、`engine/src/hy4flash/metal/hy4_metal_serve.h:219-225`）。

`--index-topk` は別の値設定ですが、このフラグで index を無効にしても、Runner 初期化時の `keys` バッファ確保は条件分岐なしに行われます。従って `--no-index` が index 関連バッファの割り当て自体をなくすとは言えません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:626,1519-1520`）。

## 適用条件と副作用

- 対象は Metal runner の HY4-Flash です。`strata-hy4` CUDA/HIP や `strata-hy4-sycl` の挙動はこの文書の対象外です（Metal parser: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1520`）。
- DFly2 speculative 経路で取得する index key list も使わなくなります。`dfly_capture` は `use_list` を `cap_list` に保存し、真の場合だけ key list をコピーします。`--no-index` 時は `use_list` が立たないため、DFly2 の attention は `MODE_CAUSAL` を選びます。speculative decoding 全体を無効化する処理は確認できません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:841-849,1032-1042`、`engine/src/hy4flash/metal/hy4_metal_spec.h:281-312`）。
- forward 時の index 更新、候補選択、tree commit 時の index-vector compact と pooled-index 更新を抑止します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1032-1040,1260-1275`）。モデルや出力ファイルをこのフラグが直接変更する処理は確認できません。
- `--load-only` を指定した場合、モデル読み込み後に Runner 作成前で終了するため、この設定による推論時 attention の変更は起きません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1630-1636`）。

## 出力とエラー

`--no-index` 自体の受理時に専用のメッセージや警告を出す処理はありません。値を取らないため値を付けてしまった場合、余分な引数が未知引数として処理されれば stdout に `ERR unknown flag <引数>`、stderr に `unknown arg <引数>` を出し、終了コード 2 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1520,1604-1608`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1520` — parser の変数初期値と flag 登録。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1032-1050` — index 更新・選択の条件と attention mode の選択。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:626,1260-1275,1630-1646,1723-1724` — key buffer の確保、tree commit の index 処理、load-only / serve / offline への値伝達。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:219-225` — serve Runner への値適用。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:281-312` — DFly2 での key-list 有無による attention mode の分岐。
