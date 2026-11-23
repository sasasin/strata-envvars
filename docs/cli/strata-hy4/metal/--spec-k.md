# `strata-hy4-metal --spec-k`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | Metal runner `strata-hy4-metal` |
| オプション | `--spec-k` |
| 別名 | なし |
| 値 | 整数。推測生成ブロックあたりの drafter 予測トークン数。`Spec` 作成時に `1..7` へ補正される |

## 役割

DFly2 による推測生成で、1 ブロックに drafter が予測するトークン数を指定する。`SpecCfg` の既定値は `5` である。値は Metal 側の `Spec` に渡され、ブロックのドラフト幅として使われる（`engine/src/hy4flash/metal/hy4_metal_spec.h:576-586,620-626,752-770`）。

## 使い方

```sh
# Metal runner で生成し、推測生成のドラフト幅を 4 にする
strata-hy4-metal --model model.strata --tokens ids.txt --gen 64 --spec-k 4
```

## 値と既定値

- 値は `atoi` で整数として読み取られる。明示的な書式・範囲検証や不正値エラーはない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1554-1557`）。
- 未指定時の `SpecCfg::K` は `5`（`engine/src/hy4flash/metal/hy4_metal_spec.h:576-586`）。
- `Spec` 構築時に、7 より大きい値は `7`、1 未満は `1` に補正される。従って、たとえば `0` や負数も拒否されず `1` として扱われる（`engine/src/hy4flash/metal/hy4_metal_spec.h:620-624`）。数値でない入力の `atoi` 結果も 0 となり、同じ補正で 1 になる。
- `DFLY_KMAX` は 7 と定義され、Tree-8 用の上限とされている（`engine/src/hy4flash/metal/hy4_metal_spec.h:174-176`）。

## 実行時の動作

Metal runner の引数解析で値を `scfg.K` に設定し、オフライン推測生成では `Spec(r, df, scfg)` に渡す。サーバーモードでは同じ `scfg` を `ServeOpts::spec` にコピーし、serve 側もそれを使って `Spec` を作る（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1556,1655-1656,1929-1930`; `engine/src/hy4flash/metal/hy4_metal_serve.h:24-38,254`）。

推測生成の各反復では補正後の `cfg.K` を候補幅とし、残り context が少ないときは `max_ctx - a - 3` まで縮める。ドラフターがその位置・幅で予測できない場合や初期校正中は通常の 1 トークン生成へフォールバックする（`engine/src/hy4flash/metal/hy4_metal_spec.h:747-770`; `engine/src/hy4flash/metal/hy4_metal_spec.h:248-254`）。このため、指定値は常に各反復で使われる実幅を保証するものではない。

推測生成は、生成・`--bench-m`・`--par-m` のいずれかが要求され、モデル manifest に DFly2 の必要な重みがあり、runner の chunk (`r.Tc`) が 16 以上で、`--all-logits` がなく、画像入力もない場合に有効になる。さらに `--draft off` は無効化する。条件を満たさない場合、この値は推測生成に使われない。サーバーモードでは `--draft` が `off` でなく、DFly2 重みがあり、chunk が 16 以上のときに DFly2 を初期化する。各リクエストでは生成上限が正で、画像を含まない場合に推測経路を使う（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762`; `engine/src/hy4flash/metal/hy4_metal_serve.h:234-254,510`）。

## 適用条件と副作用

- この文書の対象は索引上の Metal runner (`strata-hy4-metal`) であり、同名の `--spec-k` を持つ HIP / SYCL runner の挙動は対象外（索引 `docs/cli/README.md` の `strata-hy4-metal` 節、parser: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1556`）。
- `--spec-k` 自体はファイルを書き出さない。ただし、適用条件を満たす通常の推測生成では生成 ID を `--out` 配下の `gen_ids.txt` に保存し、A/B 実行では `gen_ids_plain.txt` と `gen_ids_spec.txt` を書き出す（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1929-1943,1898-1927`）。
- サーバーモードでは設定がリクエスト処理に渡される。モデルに drafter がない、または chunk が 16 未満なら推測生成は有効にならない（`engine/src/hy4flash/metal/hy4_metal_serve.h:234-254`）。

## 出力とエラー

`Spec::report` は推測生成の集計行に、補正後の `K` と adaptive/fixed・tree・early の設定を stderr に出す（`engine/src/hy4flash/metal/hy4_metal_spec.h:956-960`）。`--spec-k` 専用の拒否メッセージや終了コードは実装されておらず、範囲外・数値でない値は前述のとおり補正される。推測生成中にドラフト処理が失敗した場合は `spec: draft failed` を stderr に出して終了コード 1 となるが、これは `--spec-k` 固有の失敗条件ではない（`engine/src/hy4flash/metal/hy4_metal_spec.h:767-774`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:1936-1941`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1502-1504,1556-1565` — 設定の初期化と引数の読み取り。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:174-176,576-586,620-626` — 上限、既定値、範囲補正、drafter への反映。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:747-770` — context による実効幅の縮小、plain fallback、ドラフト呼び出し。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762,1898-1943` — 推測生成の適用条件、A/B と通常生成の処理・出力。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:24-38,234-254` — serve 設定とサーバー側の有効条件。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:956-960` — 集計出力。
