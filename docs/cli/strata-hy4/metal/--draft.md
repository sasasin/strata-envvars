# `--draft`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--draft` |
| 別名 | なし |
| 値 | `auto`、`dfly2`、`off` |

## 役割

HY4-Flash の Metal runner で DFly2 speculative decoding を使うかを指定します。省略時は `auto` で、モデルファイルに DFly2 drafter の重みがあり、実行条件を満たすときに使います。`off` は使用を止めます。`dfly2` は使用を明示指定し、serve モードでは利用できない条件や初期化失敗をエラーにします。

## 使い方

```sh
# オフライン生成で利用可能なら DFly2 を使う（既定も auto）
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 128 --draft auto

# オフライン生成で DFly2 を明示指定
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 128 --draft dfly2

# serve モードで DFly2 を無効化
strata-hy4-metal --serve --native model.strata --draft off
```

## 値と既定値

- 値は引数の次の文字列として受け取られます。parser は列挙型変換をせず、runner の分岐前に `auto`、`dfly2`、`off` のいずれかと照合します。ほかの値は拒否されます。
- 既定値は `auto` です（`hy4_metal_main.cpp:1501,1548`）。
- `--draft` に短縮別名はありません。

## 実行時の動作

### オフライン実行

モデルの manifest に DFly2 の必要テンソルがあるかを確認し、生成 (`--gen`) または該当ベンチマーク (`--bench-m`、`--par-m`) が指定され、`--draft off` ではなく、chunk 幅 `r.Tc` が16以上で、`--all-logits` がなく、画像入力がない場合に speculative mode を有効にします（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1761`）。この条件で DFly2 を初期化し、生成時は `Spec::run` による DFly2 経路で token を生成します（同 `:1766-1770,1929-1942`）。

`auto` と `dfly2` はこの有効条件では同じ経路を使います。条件を満たさない場合、通常の decode に切り替わります。`dfly2` を指定していて `--gen > 0` の場合は「drafter がない、chunk が16未満、または `--all-logits`」の可能性を示す警告を stderr に出しますが、オフライン実行そのものは継続します（同 `:1760-1762,1944-1975`）。画像入力では speculative decode は無効です（同 `:1760`）。

条件を満たして speculative mode に入った後、DFly2 の初期化そのものが失敗した場合は stderr に `dfly2: <理由>` を出し、終了コード1で終了します（同 `:1766-1770`）。

`--bench-m` または `--par-m` だけでも上記の `spec_mode` 条件に含まれ、DFly2 初期化を試みますが、それぞれの計測・比較処理は生成分岐より先に終了します。これらの測定結果を speculative decode の生成性能として扱うことはできません（同 `:1857-1896`）。

### serve 実行

`--serve` では `--draft` の値が serve 設定へ渡されます。`auto` と `dfly2` は、`off` ではなく、モデル内に必要な DFly2 tensor があり、runner の chunk が16以上なら初期化を試みます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1656`、`engine/src/hy4flash/metal/hy4_metal_serve.h:219-247`）。`auto` は DFly2 初期化に失敗しても通常経路へ進みます。`dfly2` は同じ条件を満たさない場合、または初期化に失敗した場合にエラーを返します（`hy4_metal_serve.h:234-251`）。実際の serve request では生成上限が正で画像入力がなければ speculative path を使い、それ以外は通常生成経路です（同 `:505-524`）。

## 適用条件と副作用

- `--draft` の値検査はモデル読み込み後に行われます。値が不正なら serve は engine line protocol の `ERR --draft …: expected off, dfly2 or auto` を出して終了コード2、オフライン実行は stderr に同趣旨のメッセージを出して終了コード2です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1626,1657-1659,1755-1759`）。したがってモデルの読み込み失敗が先に発生した場合は、そのエラーが先に返ります。
- `dfly2` が必要条件を満たさない serve 起動は protocol の `ERR --draft dfly2: no drafter in the file or --chunk < 16`、終了コード2になります。serve 中の DFly2 初期化失敗も protocol error となり終了コード2です（`engine/src/hy4flash/metal/hy4_metal_serve.h:234-251`）。
- `auto` で DFly2 を利用できない場合、serve は通常生成にフォールバックします。オフラインでは `[info] drafter=dfly2(off)` または `none` が stderr に表示されます（`hy4_metal_main.cpp:1760-1772`、serve の fallback は `hy4_metal_serve.h:245-255`）。
- speculative mode は DFly2 初期化を行い、serve ではリクエスト時に生成経路を切り替えます。オフラインの生成結果 ID は標準出力と `--out` 配下の `gen_ids.txt` に書かれます（`hy4_metal_main.cpp:1929-1942`）。ファイル出力の詳細はこのオプション単独ではなく生成処理によるものです。

## 根拠

- parser、既定値、serve 設定への受け渡し、無効値検査: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1501,1548,1636-1674,1755-1762`
- オフラインの利用条件、初期化、speculative decode と通常 decode: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1772,1929-1975`
- serve の利用条件、失敗・fallback、リクエストごとの生成経路: `engine/src/hy4flash/metal/hy4_metal_serve.h:219-255,505-524`

調査範囲は上記 checkout の Strata 所有 Metal runner と serve 実装です。Metal 実機での実行や DFly2 の性能差は確認していません。
