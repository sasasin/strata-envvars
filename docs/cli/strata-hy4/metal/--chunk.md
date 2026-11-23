# `strata-hy4-metal --chunk`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner） |
| オプション | `--chunk` |
| 別名 | なし |
| 値 | 整数。正の値が有効。 |

## 役割

プロンプトの prefill を一度に処理する token 数の上限を指定します。Metal runner は入力 prompt をこの値以下のまとまりに分けて順に処理します。生成時の decode は別経路で1 tokenずつ実行されるため、この値はその decode 幅を指定するものではありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1789-1796,1829-1834`）。

## 使い方

```sh
# prompt を最大 1024 token ずつ prefill する
strata-hy4-metal --model SQ64.strata --tokens ids.txt --chunk 1024
```

サーバーモードでも同じ parser オプションを使用できます。

```sh
# server の prompt prefill 幅を 1024 token にする
strata-hy4-metal --serve --native SQ64.strata --chunk 1024
```

## 値と既定値

- 値は `atoi` で整数に変換されます。`--chunk` 自体に対する範囲検証や変換エラー処理はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1515`）。
- 正の値は指定値を基準に使います。0以下は既定値へフォールバックします。既定値は cold experts が有効なモデルでは 2048、それ以外では 4096 です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1617-1618,1642-1644,1713-1715`）。
- `atoi` の結果が0になる値（例: 数字として解釈できない文字列や空文字列）も既定値にフォールバックします。数値として厳密に受理されたかを判定する処理はありません（同 `:1514,1713-1714`）。
- offline 実行では、Runner に渡す実効値を `max(1, min(eff_chunk, max(prompt token 数, 16)))` に制限します。そのため prompt が短い場合、指定した正の値より Runner の chunk が小さくなることがあります（同 `:1701-1715`）。サーバーモードではこの prompt 長による上限処理はなく、Runner は `max(so.chunk, 1)` を使います（`engine/src/hy4flash/metal/hy4_metal_serve.h:219-223`）。

## 実行時の動作

offline 実行では、実効 chunk 値が Runner の `Tc` になります。prompt は `min(Tc, 残り token 数)` ごとに `forward_chunk` へ渡され、最後のまとまりで logits を計算します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1713-1715,1789-1808`）。サーバーモードでも `Tc` を使って各 request の prompt を分割し、prefill の進捗を `PP` 行として出力します（`engine/src/hy4flash/metal/hy4_metal_serve.h:219-223,471-485`）。

`Tc` に比例する prefill 用バッファや Engram 用バッファが確保され、SWA ring の容量にも加算されます。したがって大きな値は chunk に関連する Metal メモリ使用量を増やします（`engine/src/hy4flash/metal/hy4_metal_main.cpp:614-627,708-713`）。正の値に対する上限検証は見当たりません。

## 適用条件と副作用

- `--draft dfly2` による speculative decoding の有効条件には chunk が16以上であることが含まれます。サーバーでは条件を満たさないと `ERR --draft dfly2: no drafter in the file or --chunk < 16` を protocol stdout に出し、終了コード2で終了します（`engine/src/hy4flash/metal/hy4_metal_serve.h:233-237`）。
- offline 実行では、chunk が16未満などで `--draft dfly2` を有効化できず、かつ `--gen > 0` の場合、stderr に利用不可の警告を出します。ここでは `--chunk` 自体を理由に終了しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762`）。
- サーバーモードで `--chunk` を省略した場合も main 側で cold experts の状態に応じた 2048 / 4096 が `ServeOpts` に設定されます。`ServeOpts` の構造体単独の初期値は2048ですが、CLI 経由の通常経路では main の設定値が渡されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1644`; `engine/src/hy4flash/metal/hy4_metal_serve.h:24-29`）。
- `--chunk` の値が無効であることを理由とした固有のエラー出力は確認できません。引数名自体が未知の場合は別経路で `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出し、終了コード2になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1515` — parser の初期値と `--chunk` の整数変換。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1618,1635-1644` — model 読み込み後の serve 分岐、サーバー用既定値とオプション値の設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1701-1715,1789-1808,1829-1834` — offline prompt 長、Runner の実効 chunk、prefill 分割と decode の呼び出し。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:614-627,708-713` — `Tc` に依存する ring・prefill・Engram buffer の確保。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1764` — offline speculative mode の条件、無効時の警告、Runner 初期化エラー経路。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:219-242,466-485` — server Runner の `Tc`、DFly2 の chunk 条件と失敗、request prefill の分割・進捗出力。

調査範囲はこの checkout の Metal runner とその server 実装です。`--chunk` の大きな値で Metal buffer 確保が失敗する場合の下位 Metal runtime の具体的なエラー表示・終了動作は、このオプションの使用箇所からは特定できないため記載していません。
