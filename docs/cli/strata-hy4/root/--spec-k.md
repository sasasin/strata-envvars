# `--spec-k`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root、CUDA/HIP） |
| オプション | `--spec-k` |
| 別名 | なし |
| 値 | 整数。実行時に 1〜7 に補正される |

## 役割

DFly2 speculative decoding で、1回の draft/verify に使うトークン数の上限を指定する。値は speculative decoding の設定 `SpecCfg::K` に入り、実際に検証する長さは適応制御やコンテキスト残量によって短くなることがある。

## 使い方

```sh
# server モードで上限を 5 にする（draft は既定の auto）
strata-hy4 --serve --native model.strata --spec-k 5

# offline 生成で DFly2 を明示し、上限を 4 にする
strata-hy4 --model model.strata --tokens prompt.ids --gen 64 --draft dfly2 --spec-k 4

# offline 生成で固定幅の verify を指定する
strata-hy4 --model model.strata --tokens prompt.ids --gen 64 --draft dfly2 --spec-k 3 --spec-fixed
```

## 値と既定値

値は `atoi` で整数変換される。省略時の `SpecCfg::K` は 7。`Spec` の初期化時に 7 より大きい値は 7、1 未満の値は 1 に補正されるため、実効範囲は 1〜7 である。parser に数値形式や範囲の明示的な検査はない。数値として解釈できない文字列は `atoi` の結果 0 となり、初期化時に 1 へ補正される。

値自体を省略すると parser の `nxt()` が `ERR --spec-k needs a value` を stdout に出して終了コード 2 で終了する。

## 実行時の動作

`--spec-k N` は `scfg.K` に保存され、server 起動時は `ServeOpts::spec` に渡される。offline では `--draft dfly2`、`--gen` が正数、`--dfly-alloc-only` なしの場合に speculative decoding が実行される。server では `--draft off` 以外で、chunk が 8 以上かつ DFly2 の初期化に成功した場合に `Spec` が作られる。server の既定 draft は `auto` だが、offline の既定 draft は `auto` では speculative decoding を有効にしない。

`Spec` は設定を受け取る際に値を 1〜7 に補正する。各反復ではこの値を `Kd` として使い、残りの context が足りなければ `max_ctx - a - 3` まで短縮する。適応モードでは tree draft の長さを上限にしつつ、verify に進む長さをコスト推定・信頼度に基づいて選ぶ。`--spec-fixed` を付けるとこの適応的な verify 長選択を行わず、draft tree の長さまで verify する。draft が利用できない状態や controller の plain 区間では通常の decode に進むため、指定値が常に使われるわけではない。

このオプションは値を設定するだけで、単独でファイルを作成・変更しない。offline の speculative decoding を行う経路では生成結果を `out_dir/gen_ids.txt` に書き出すが、これは `--spec-k` 固有の副作用ではない。

## 適用条件と副作用

- DFly2 speculative decoding の `Spec` が作られる実行経路で適用される。`--draft off`、offline で `--draft dfly2` を指定しない場合、`--gen` が 0 の場合はこの値で speculative decode の反復数は変わらない。
- server で chunk が 8 未満、または DFly2 初期化に失敗した場合は drafter なしで続行するため、`--spec-k` は使われない。
- context 上限、draft 状態などの条件により実際の draft 長が短縮されたり、plain decode に切り替わったりする。
- `--spec-fixed` との組み合わせでは適応的な verify 長選択を無効にする。`--spec-cut` は適応モードで使う信頼度しきい値だが、`--spec-fixed` が有効な場合は固定長分岐が先に選ばれる。
- speculative decoding は GPU 上の DFly2 draft と verify を実行する。`--spec-k` による別個のファイル・ネットワーク操作は確認できない。

## 出力とエラー

値省略時は parser が stdout に不足値エラーを出し、終了コード 2 で終了する。未知の引数は stderr に `unknown arg ...` を出して終了コード 2 となる。数値の範囲外は parser error にならず、`Spec` 初期化時に 1〜7 へ補正される。server では drafter が使えない条件があっても、該当コードは警告を stderr に出して drafter なしで続行する。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-384` — 値取得、値省略時の stdout エラーと終了コード。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:401-414` — `--spec-k` の parser 登録と `atoi` による `scfg.K` への代入。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-30, 91-96` — `K` の既定値 7、設定値の 1〜7 補正、spec 設定の初期化。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-570, 701-716, 992-1008` — server への設定引き渡し、offline speculative mode 条件、Spec 実行と結果出力。
- `engine/src/hy4flash/run/hy4_serve.hip.h:319-341` — server 側の drafter 有効条件と `Spec` 作成。
- `engine/src/hy4flash/run/hy4_spec.hip.h:127-144, 267-287, 336-354` — verify 幅の選択、context による短縮、plain decode への切替。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:578-592` — draft 可否判定と有効範囲 1〜7。
- `engine/src/hy4flash/run/hy4_spec.hip.h:179-194` — `--spec-fixed` 時の固定幅選択、および適応時の verify 幅選択。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:498-505` — 未知引数の stderr 出力と終了コード 2。
