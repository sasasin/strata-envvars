# `STRATA_PROMPT_MERGEH`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の prompt-chain にある QSA attention merge の出力経路を選びます。既定では merge の結果をそのまま fp16 バッファへ書き、`STRATA_PROMPT_MERGEH=0` のときは従来どおり fp32 の prepared-activation バッファへ書いた後、別 dispatch で fp16 に変換します。これは prompt-chain の QSA に限る設定です。

## 値と判定

文字列全体を `"0"` と比較します。数値変換や真偽値 parse はありません。

| 値 | 結果 |
|---|---|
| 未設定 | 有効（direct fp16 merge） |
| 空文字 | 有効（direct fp16 merge） |
| 厳密に `0` | 無効（fp32 merge の後に fp16 変換） |
| その他すべて | 有効。例: `1`, `00`, `false`, ` 0`, `0 ` |

比較は大文字小文字を区別しますが、値を文字列 `"0"` と比べるため、`false` なども有効側です。読み取り結果は関数内 `static const bool` に保存されます。

## 有効になる条件

この変数を参照するのは `Window::pc_chunk()` の prompt-chain です。Metal の prompt 実行で、`STRATA_METAL_PROMPT` が厳密に `window` ではなく、非 streaming で、prompt 長が `STRATA_METAL_PROMPT_MIN`（未設定時 32）以上の場合に `prompt_run_rows()` から `Window::prompt()` が呼ばれます。`Window::prompt()` は chunk ごとに `pc_chunk()` を実行します。

以下の経路ではこの設定は使われません。

- `STRATA_METAL_PROMPT=window`、または prompt 長が `STRATA_METAL_PROMPT_MIN` 未満の場合は decode-window fallback を通ります。
- streaming 時は別実装の prompt GEMM 経路（条件を満たさない場合は decode-window fallback）を通り、`STRATA_PROMPT_MERGEH` の参照箇所はありません。
- prompt-chain の QSA dispatch がない処理では、この値による分岐もありません。prompt-chain は 48 layer のうち `l % 4 == 3` の attention layer で QSA merge を積みます。

## 実行時の詳細

`pc_chunk()` の QSA attention 計算後に環境変数を一度評価します。未設定または `"0"` 以外なら `qsa_merge_h` を dispatch し、merge 結果 `y` を `half(y)` として fp16 出力 `xqh` に書きます。その後の attention output GEMM はこの fp16 バッファを読みます。

厳密に `"0"` の場合は `qsa_merge` を dispatch し、merge 結果を fp32 prepared-activation バッファ `XQ` に書いた後、`act16()` を追加 dispatch して `xqh` に変換してから同じ attention output GEMM へ進みます。カーネル実装では両経路とも QSA の重み付き merge と gate の sigmoid 適用を行い、direct 経路はその結果を `half` に変換して格納します（`qsa_prompt.metal:156-180`, `qsa.metal:384-417`）。

関数ローカル static のため、最初に QSA merge 分岐へ到達した時点の値がプロセス内でキャッシュされます。実行中に環境を書き換えても再評価されません。変数専用のログや警告はありません。通常の prompt-chain 起動時には `prompt kernels ... ready` が stderr に出ますが、これは merge 選択を報告するものではありません。prompt 自体は context 超過時に `metal prompt: the prompt runs past the context`、setup 失敗時に `metal prompt: setup failed` で失敗し得ますが、これらはこの変数固有の失敗経路ではありません。

## 根拠

- 対象名を読む唯一の箇所と `qsa_merge_h` / `qsa_merge` の dispatch 選択: `metal/src/engine/prompt_chain.inc:402-409`。
- prompt-chain の作成、chunk 実行、`prompt kernels ... ready` ログ: `metal/src/engine/prompt_chain.inc:49-60,136-139,564-590`。
- prompt の経路選択、`window` 指定、行数しきい値、streaming 分岐: `metal/src/engine/window.cpp:3593-3626`。
- prompt-chain が QSA を使う layer 条件、QSA merge dispatch: `metal/src/engine/prompt_chain.inc:307-310,357-410`。
- direct fp16 merge と従来 merge の出力処理: `metal/kernels/qsa_prompt.metal:156-180`, `metal/kernels/qsa.metal:384-417`。
- prompt-chain context 超過エラー: `metal/src/engine/prompt_chain.inc:574-578`。
