# `strata-hy4-sycl --max-context`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--max-context` |
| 別名 | なし（`--ctx` は別の parser 表記として同じ内部値を設定） |
| 値 | `atoi` で整数化される引数。正数が明示値として使われる |

## 役割

実行時に保持する最大コンテキスト長を指定します。`--serve` では prompt の受理上限と生成可能数を制限し、通常のトークン入力経路では Runner のコンテキスト長と sparse KV cache の容量に使われます。

## 使い方

```sh
strata-hy4-sycl --serve --native model.strata --engram engram.strata --max-context 65536
```

通常のトークン入力経路でも parser はこの表記を受け付けます。たとえば `--model`、`--tokens` と併用できます。

## 値と既定値

- `--max-context` の直後の引数は `atoi` で整数に変換されます。数値形式や正の範囲を検証する処理はありません。数値として解釈できない文字列は `atoi` の結果 0 となり、負数と同様に既定値へ置き換わります（`engine/src/hy4flash/sycl/sy_main.cpp:109-115,131`）。
- 値を省略すると parser の `nxt()` が `ERR --max-context needs a value` を stdout に出して終了コード 2 で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:109-115,131`）。
- `--serve` では正数以外は `131072` に置き換わります（`engine/src/hy4flash/sycl/sy_main.cpp:215-230`）。
- 通常経路では正数以外が `max(T0 + gen + 16, 131072)` に置き換わります。`T0` は読み込んだ token 数、`gen` は `--gen` の値です（`engine/src/hy4flash/sycl/sy_main.cpp:266-278`）。
- `--ctx` も同じ `max_ctx` を設定します。引数は順に処理されるため、両方を指定した場合は後に現れた方が残ります（`engine/src/hy4flash/sycl/sy_main.cpp:105-107,131,156-159`）。

## 実行時の動作

parser は値を `max_ctx` に格納します。`--serve` の場合は `ServeOpts.max_ctx` に渡され、Runner を作るときにその値を使います。起動後、プロトコルの `READY` 行にも上限値が出ます（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`; `engine/src/hy4flash/sycl/sy_serve.h:258-263,323-334`）。prompt token 数が上限以上なら、その要求に `ERR prompt exceeds context` を返して処理を続けます。上限内の prompt では、新規生成数を `max_ctx - T0 - 1` 以下に制限します（`engine/src/hy4flash/sycl/sy_serve.h:380-388,464-472`）。

通常経路では Runner に渡され、sparse KV cache の slot 数を `max_ctx` に基づいて計算します。`max_ctx` が `kv_host_above` を超える sparse cache は host-mapped memory に割り当てる分岐があります（`engine/src/hy4flash/sycl/sy_main.cpp:276-294`; `engine/src/hy4flash/sycl/sy_graph.h:363-364,535-550`）。通常経路での生成（DFly2）も同じ上限を参照し、上限近くでは draft 長を縮め、残りがなければ長さ上限で止めます（`engine/src/hy4flash/sycl/sy_spec.h:177-187`）。

## 適用条件と副作用

- 正の値は `--serve` と通常経路の双方で使われます。モデルの最大 context length との適合性をこの parser で検証する処理は確認できません。
- 大きい値では sparse KV cache の slot 数に応じて確保量が増えます。利用可能な VRAM・host memory を超えた場合の具体的な失敗表示や終了経路は、このオプションの処理箇所だけからは特定できません（`engine/src/hy4flash/sycl/sy_graph.h:535-550`）。
- 明示値 0 や負数は拒否されず既定値扱いです。無効な文字列も `atoi` により 0 になり同じ扱いになります。

## 出力とエラー

欠落値は stdout に `ERR --max-context needs a value` を出し、終了コード 2 です（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。`--serve` が起動すると stdout の `READY <max_context> stop` で採用値を確認できます。prompt が長すぎる場合は stdout に `ERR prompt exceeds context (<prompt長> of <上限>)` を返します（`engine/src/hy4flash/sycl/sy_serve.h:333,385-388`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:104-115,129-159` — 初期値、値取得、`--max-context` と `--ctx` の parser。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,266-283` — `--serve` と通常経路での既定値、Runner への伝播。
- `engine/src/hy4flash/sycl/sy_graph.h:535-550` — context 上限に基づく sparse KV slot 数と host/device memory の選択。
- `engine/src/hy4flash/sycl/sy_serve.h:258-263,323-334,380-388,464-472` — serve 起動時の上限出力、prompt 拒否、生成上限。
- `engine/src/hy4flash/sycl/sy_spec.h:177-187` — 通常経路の speculative generation が上限に合わせる処理。
