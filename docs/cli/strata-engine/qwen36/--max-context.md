# `strata` / `strata-q36` の `--max-context`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。調査時の Strata 作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

## 対象と値

Qwen3.6 専用 parser における `--max-context N` は、推論セッションのコンテキスト容量をセル数で指定します。短縮 alias は `--ctx N` で、同じ値に設定されます。既定値は `32768` です。parser は `std::atoi` で整数変換し、`ctx < 256` の場合は `strata-q36: bad --chunk / --max-context` を stderr に出して終了コード `2` で終了します。引数が欠ける場合も `needs a value` を stderr に出して終了コード `2` で終了します。通常エンジン側の `--max-context` とは別 parser・別スコープです。

根拠: `src/qwen35/q36_engine.cu:3735-3757`（既定値、alias、変換）、`src/qwen35/q36_engine.cu:3744-3746`（値なしの処理）、`src/qwen35/q36_engine.cu:3807-3809`（下限検証）、`docs/cli/README.md:1318-1340`（Qwen3.6 スコープと索引）。

## 効果と適用される経路

- 起動時に値は `Engine::init(m, ctx, ...)` へ渡され、エンジンの `ctx` として保持されます。初期化ログには `context N cells` として出力されます（`src/qwen35/q36_engine.cu:1339-1345`, `1505-1509`, `3863`）。
- `Engine::init` は `ctx` を使って attention の KV キャッシュ量を決め、各セッションのキャッシュを確保します。vision 有効時の画像位置テーブルも `ctx` に基づくサイズです（`src/qwen35/q36_engine.cu:1452-1471`, `1497-1500`）。したがって容量を上げるとコンテキスト関連の VRAM 需要も増えます。複数セッションでは各 slot の KV/state 消費を見積もり、VRAM が足りずに判定にかかると `not enough VRAM ... use fewer slots ... or a shorter --max-context` を stderr に出して終了します（`src/qwen35/q36_engine.cu:1452-1469`）。ほかの割り当て失敗は CUDA 呼び出しの `CK` 経路に従います。
- `--serve` では READY 行に容量を通知し、GEN/GENI 要求は prompt token 数と `max_new` の合計が容量を超えると `ERR prompt ... exceeds the context` を stdout に返し、その要求を処理しません。通常の生成中も容量端で生成を止め、DONE の finish 値を `length` にします（`src/qwen35/q36_engine.cu:3505-3508`, `3660-3670`, `3678-3681`）。batch 経路も slot ごとに `E.ctx` を参照して MTP の2 token採用や終了位置を制限します（`src/qwen35/q36_engine.cu:3278-3295`）。
- `--tokens` の単発生成は prompt を `E.process` に渡した後、`n_gen` 回の出力を行う経路で、serve のような prompt+生成数の事前拒否は同箇所にはありません（`src/qwen35/q36_engine.cu:3916-3933`, `3960-3978`）。利用可能なモードにより上限到達時の扱いが異なるため、指定容量内に prompt と生成分が収まるようにしてください。
- chunk が `auto`（内部値 `0`）の場合、その自動 chunk 選択の VRAM 余裕見積もりでも `ctx` を使います。明示した `--chunk` の値はこの自動選択を通りません（`src/qwen35/q36_engine.cu:3818-3858`）。`--batch` と組み合わせるとセッション数分のキャッシュ量が必要になり、容量を下げるか slot 数を減らすよう案内されることがあります（`src/qwen35/q36_engine.cu:1452-1468`, `3843-3848`）。

Qwen3.6 のモデル選択時、通常 `strata` の入口は GGUF architecture を調べて専用 `strata::qwen35::run` に振り分けるため、この文書の意味が適用されます。別 executable `strata-q36` も同じ `run` parser を使います（`src/program/generate.cpp:2393-2407`, `src/qwen35/q36_main.cpp:1-4`）。

## 検証上の注意

parser に明示された数値検証は `ctx >= 256` のみで、ソース上にこのオプション固有の上限値検証はありません。`atoi` のため、小数・単位付きの値を受け付ける仕様ではありません。コンテキスト容量を大きくできるかはモデル・GPU の空き VRAM・batch slot 数などの実行時条件にも左右されます。値の最大安全量や任意の環境での実用上限は、このソース調査だけでは確定できません。

調査範囲は parser、初期化、serve・batch・単発生成の参照箇所です。同一 revision の CLI `--help` は実行していません。性能測定や GPU 実行は行っていません。
