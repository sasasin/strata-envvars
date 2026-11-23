# `strata-hy4-metal --max-context`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--max-context` |
| 別名 | `--ctx` |
| 値 | 整数（`atoi` で変換）。正の値が明示上限として使われる |

## 役割

Metal runner のコンテキスト長を指定します。KV cache などの容量計算にも使われるため、値を大きくすると必要な Metal メモリも増えます。`--ctx` も同じ変数に値を設定します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1513,1591`）。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids --max-context 8192
```

モデルと入力 token ファイルを指定する通常実行の例です。serve モードでは `--serve` と併用します。

## 値と既定値

値は `atoi` で整数に変換されます。専用の範囲検証はありません。0 以下の値は明示上限として採用されず、実行モードごとの既定値に置き換わります。数値として解釈できない文字列も `atoi` の結果が 0 となり、同じ既定値経路に入ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1591,1642,1706`）。

同じオプションを複数回指定した場合や `--ctx` と併用した場合は、引数走査で最後に現れた値が残ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1513,1591`）。値を省略した場合の専用エラー処理は parser にありません。省略時の挙動はソースから安全に特定できないため、値を必ず指定してください。

既定値は実行モードで異なります。

- `--serve` あり: 値が正ならその値、0 以下なら `131072`（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1643`）。
- 通常の offline 実行: 値が正ならその値、0 以下なら入力 token 数 `T0` + `--gen` の値 + 16（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1701-1707`）。

## 実行時の動作

parser は `--max-context N` を `max_ctx` に格納します。通常実行では、この値が `Runner` に渡され、sparse slot 数、KV/index/pool buffer の容量、attention score buffer の長さの計算に使われます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:615-625,1706-1715`）。初期化に失敗した場合は `init: ...` を stderr に出して終了コード 1 で戻ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1762-1765`）。

`--serve` では値が `ServeOpts.max_ctx` に渡り、Runner の初期化と会話ごとの token buffer 容量に使われます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1643`; `engine/src/hy4flash/metal/hy4_metal_serve.h:220-222,258,268`）。入力 prompt の token 数が上限以上なら、その要求に `ERR prompt exceeds context (入力数 of 上限)` を返して処理を続けます（`engine/src/hy4flash/metal/hy4_metal_serve.h:352-359`）。生成可能数も残り枠 `max_ctx - T0 - 1` 以下に制限されます（同:505-506）。

## 適用条件と副作用

この parser は Metal 版 `strata-hy4-metal` のものです。通常実行では明示値を入力 token 数や生成数と照合して拒否する処理は確認できません。SpecInfer が有効な場合（生成・bench・par mode のいずれかで、draft が有効、モデルに drafter があり、chunk が 16 以上、`--all-logits` でなく、画像入力もない場合）、上限に近づくと `finish = "length"` として生成を止め、検証候補数も残り枠に合わせます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1761`; `engine/src/hy4flash/metal/hy4_metal_spec.h:748-754`）。通常の生成経路における同等の上限判定は、この調査範囲では確認できません。

`max_ctx` を用いた cache および score buffer の容量確保は GPU メモリ使用量に影響します。Runner は初期化時に KV cache 容量を stderr に表示します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:384-396,615-625,747`）。負値や極端に大きな値について、値そのものを検証・拒否する処理は見当たりません。

## 出力とエラー

serve モードで prompt が上限に達している場合のエラー応答は上記のとおりです。通常実行の初期化失敗は stderr の `init: ...` と終了コード 1 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1762-1765`）。Metal buffer 確保失敗の具体的なエラー文や、過大値に対する一律の終了動作はこのオプションの処理からは確認できません。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1504-1515,1591` — 初期値、引数走査、`--ctx` と `--max-context` の代入。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1643,1701-1715` — serve / offline の既定値と Runner への伝達。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:384-396,615-625,747,1762-1765` — 容量計算、診断出力、初期化失敗経路。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:220-222,258,268,352-359,505-506` — serve での利用、prompt 上限判定、生成枠。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:748-754` — SpecInfer の context 上限判定。
