# `strata-hy4-metal --no-pipe`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-metal` |
| コマンド | `strata-hy4-metal`（Metal runner、root） |
| オプション | `--no-pipe` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Metal runner の dispatch graph を分割して非同期投入する経路を無効にし、グラフを一括で実行します。これは Metal 用の HY4 runner の設定です。

## 使い方

```sh
strata-hy4-metal --model SQ64.strata --tokens ids.txt --gen 32 --no-pipe
```

`--model` と `--tokens` を指定した通常のオフライン実行に追加します。実行ファイルの引数としてフラグだけを渡します。

## 値と既定値

値を取りません。未指定時は parser 側の `no_pipe` が `false` で、runner の `pipe_enc` は `true` です。複数回指定しても同じ真偽値を設定するだけです。数値などの後続値を読む処理はありません。

## 実行時の動作

parser は `--no-pipe` を認識すると `no_pipe = true` にします（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1492-1493,1551-1552`）。オフライン runner の初期化時に `pipe_enc = !no_pipe` として反映します（同 `:1732-1733`）。

runner の `run_all()` は dispatch が空なら何もせず、通常は `cx.run_graph(ds)` を呼んでグラフを一括実行します。既定の `pipe_enc=true` かつ dispatch 数が400以上のときだけ、dispatch を `pipe_segs` 個相当の区間に分けて `cx.run_graph_async()` へ順に渡し、返された token を `cx.wait_async()` で待ちます。`--no-pipe` はこの分割・非同期投入条件を無効にし、dispatch 数にかかわらず一括実行側へ進ませます（同 `:462-478`）。

`run_all()` は初期化時の warmup、prefill、decode/verify など複数の実行点から呼ばれます（同 `:745,1288,1327,1803-1811,1833-1844`）。一方、`--pipe-segs` は既定8で、正の値になるよう `max(1, pipe_segs_arg)` で下限補正されます（同 `:1493,1552,1732-1733`）。`--no-pipe` が有効なら区間数の設定は実行経路に影響しません。

## 適用条件と副作用

効果があるのはオフライン runner です。`--serve` の分岐は `Runner` の生成・`pipe_enc` の設定より前に server 起動関数へ戻るため、このオプションは server 側へ渡されず、server 実行時の動作はここから確認できません（同 `:1635-1675,1715,1732-1733`）。

オフライン実行でも、`run_all()` に積まれた dispatch が400未満なら既定でも一括実行なので、実行方式に差はありません（同 `:464-478`）。400以上の場合、既定の区間分割・非同期投入を抑止します。コード上で変わるのは実行の投入方法であり、性能上の推奨や速度差はこのソース調査からは判断できません。

## 出力とエラー

このフラグ専用の出力・validation・エラー処理は確認できません。未知の引数は `ERR unknown flag ...` を stdout に出し、`unknown arg ...` を stderr に出して終了コード2で戻りますが、`--no-pipe` 自体は parser に登録されています（同 `:1551,1604-1608`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1492-1493,1551-1552` — フラグの初期値と parser 登録。
- 同 `:462-478` — `run_all()` の非同期区間分割条件、通常の一括実行、および実行後の dispatch 消去と GPU 時間加算。
- 同 `:1732-1733` — オフライン runner への設定と `--pipe-segs` の下限補正。
- 同 `:1635-1675,1715` — `--serve` の分岐が runner 設定より先に処理されること。
- 同 `:745,1288,1327,1803-1811,1833-1844` — warmup、prefill、decode/verify 経路からの `run_all()` 呼び出し例。
- 同 `:1604-1608` — 未知引数の出力と終了コード。
