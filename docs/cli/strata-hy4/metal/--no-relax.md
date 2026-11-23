# `strata-hy4-metal --no-relax`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--no-relax` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Metal runner が forward 計算中に独立 dispatch の barrier を外す最適化を抑止するフラグです。dispatch が重なる実行で挙動を調べる場合に指定できます。実際に barrier を外す候補があるか、MPP 経路かどうかによって効果が変わります。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 32 --no-relax
```

値は不要です。モデルと token ファイルを指定した通常の Metal 実行に付けます。

## 値と既定値

parser は `--no-relax` を見つけると `no_relax` を `true` にします。値引数は読み取りません。未指定時の `no_relax` は `false` であり、Runner に渡される `relax_ok` は既定で `true` です。値の validation はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1490,1545,1750`）。

## 実行時の動作

Runner の `forward_chunk` ごとに `allow_nb` を `relax_ok` と MPP 条件の論理積で設定します。具体的には、MPP が有効で、かつ chunk 長 `T` が `min(mpp_min, moe_mm_min)` 以上の場合は、`--no-relax` の有無にかかわらず `allow_nb` が `false` になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1291-1297`）。

各所の `relax()` は `allow_nb` が false なら何もせず、true なら dispatch リスト末尾から最大 `n` 件（既定 1 件）の `barrier` を false にします。Runner のコメントではこれは独立 dispatch の前に barrier を置かず、重ねて実行可能にする扱いです。`--no-relax` により `relax_ok` が false になると、該当する `relax()` 呼び出しは barrier を変更しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:457-460,994,996,1004,1149-1158,1243`）。

## 適用条件と副作用

設定は全 `forward_chunk` に渡されますが、MPP 条件だけでも `allow_nb` が false になるため、その場合はこのフラグによる追加の変化はありません。MPP の scratch 共有と barrier 省略の関係は runner のコメントに記されています（`engine/src/hy4flash/metal/hy4_metal_main.cpp:457,1296`）。このフラグが出力ファイルやネットワーク・別プロセスを直接操作する処理は確認できません。性能や GPU 実行時間への定量的な影響は調査していません。

## 出力とエラー

このフラグ固有の出力・エラー処理はありません。未知の引数は別経路で `unknown arg` を stderr に出して終了コード 2 になりますが、`--no-relax` は parser に登録されています（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1545,1604-1608`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490,1504-1547` — `no_relax` の初期値と引数 parser。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:457-460,994,996,1004,1149-1158,1243` — `relax_ok` / `allow_nb` と barrier を変更する `relax()`、その呼び出し箇所。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1291-1297,1750` — chunk ごとの条件と parser 値の Runner への転送。
- `docs/cli/README.md:1358-1417` — Metal runner の階層と `--no-relax` の索引リンク。
