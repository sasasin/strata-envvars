# `--ctx`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--ctx` |
| 別名 | `--max-context`（同じ値へ代入。索引には未記載） |
| 値 | 整数として `atoi` で変換。正の値は context 上限、0 以下は実行モードごとの自動値 |

## 役割

Metal runner が確保する context/KV cache の長さを指定する。serve では prompt と生成に使える context の上限になり、オフライン実行では runner の KV 用領域のサイズを決める。大きい値ほど sparse KV、index、pooled key 用の Metal buffer が大きくなる。

## 使い方

```sh
# オフライン実行で context 上限を 8192 にする
strata-hy4-metal --model model.strata --tokens prompt.ids --ctx 8192

# serve の context 上限を 32768 にする
strata-hy4-metal --model model.strata --serve --ctx 32768
```

## 値と既定値

- parser は `--ctx` と `--max-context` の直後の文字列を `atoi` で整数化し、どちらも `max_ctx` に代入する。オプションの範囲検証や変換エラーの検出はない。両方または同じ表記を複数指定した場合は、引数走査で後に現れた値が残る（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1514`, `1591-1592`）。
- serve (`--serve`) では `max_ctx > 0` の値を使い、それ以外は `131072`。serve 分岐は token file を読むオフライン経路より前にある（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1643`）。
- オフラインでは token 入力と画像 pad 展開後の token 数 `T0` を確認し、`max_ctx <= 0` なら `T0 + gen + 16` にする。したがって省略、0、負数、`atoi` が 0 を返す文字列は自動値になる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1682-1707`）。

## 実行時の動作

- runner に `max_ctx` を渡し、非 sliding-window 層の sparse KV slot 数を `max_ctx` に基づいて丸める。各層の補助 buffer と index score の長さも `max_ctx` から算出されるため、この値は Metal memory 使用量に影響する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:380-396`, `615-625`, `1713-1715`）。起動後は KV cache の概算サイズと `ctx` 値を stderr に出す（同 `:745-747`）。
- serve は起動時に `READY <max_ctx>` を出し、要求 prompt が `max_ctx` 以上なら `ERR prompt exceeds context` を返してその要求を拒否する。生成数は `min(q.max_new, max(0, max_ctx - T0 - 1))` に制限される（`engine/src/hy4flash/metal/hy4_metal_serve.h:302-304`, `352-359`, `505-507`）。
- offline speculative decode は `max_ctx` を `Spec::run` に渡し、context 末尾に近づくと `finish="length"` で生成を止め、draft 長も残り枠に合わせて縮める（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1912`, `1936`; `engine/src/hy4flash/metal/hy4_metal_spec.h:747-754`）。

## 適用条件と副作用

- `--ctx` は serve / offline の双方で同じ `max_ctx` を設定するが、非正値の既定値は異なる（上記「値と既定値」）。
- 正の値について prompt 長との整合や最小値の validation は parser にない。serve は prompt を明示的に拒否する一方、オフライン prefill に同等の `T0 >= max_ctx` 拒否は確認できない。offline speculative decode の context 停止条件はあるが、通常の greedy decode に対する同じ上限判定はソース上で確認できなかった（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1789-1805`, `1944-1966`）。
- 大きな値は KV 関連 Metal buffer の割当量を増やす。Metal allocation が失敗する場合の具体的な表示・復旧動作は、このオプションの処理経路からは特定できなかった。

## 出力とエラー

- serve は context 上限を `READY` 行で stdout に出し、長すぎる prompt には `ERR prompt exceeds context (<prompt length> of <limit>)` を stdout に出して次の要求へ進む（`engine/src/hy4flash/metal/hy4_metal_serve.h:304`, `357-359`）。
- 起動時には runner の stderr ログに KV cache の GB、context、chunk、Metal allocation を出力する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:745-747`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1514`, `1591-1592` — Metal CLI の引数 parser と同一変数を使う `--max-context`。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1643`, `1682-1715` — serve / offline の既定値と runner への伝達。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:380-396`, `613-625` — context に応じた KV・index buffer の算出。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:302-304`, `352-359`, `505-507` — serve の表示、prompt validation、生成枠。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:747-754` — speculative decode の context 上限処理。
