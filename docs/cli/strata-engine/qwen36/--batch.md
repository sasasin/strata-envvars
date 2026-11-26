# `strata` / `strata-q36` `--batch`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | Qwen3.6 専用 parser（`strata` のモデル選択後、または `strata-q36`） |
| オプション | `--batch` |
| 別名 | `--slots` |
| 値 | 整数。実際に使うセッション数は 1〜8 |

## 役割

Qwen3.6 エンジンが保持する独立した会話セッション数を指定します。`--serve` のバッチプロトコルでは、各セッションを slot として複数リクエストを同時に進めます。1 slot ごとにコンテキスト長に応じた KV キャッシュと GDN 状態を確保するため、枠を増やすと必要 VRAM も増えます（`engine/src/qwen35/q36_engine.cu:1752-1767, 1962-1967, 2140-2159, 4720-4724`）。

## 使い方

```sh
# Qwen3.6 エンジンを4セッションで起動し、serve プロトコルを使う
strata --model /path/to/qwen36.gguf --serve --batch 4

# 専用実行ファイルでも同じ parser を使う
strata-q36 --model /path/to/qwen36.gguf --serve --slots 4
```

## 値と既定値

値は必須で、parser は `std::atoi` で整数化します。省略時の parser 値は `0` で、セッション数への変換時に 1〜8 へ clamp されるため、実効既定値は 1 です。負数、0、整数として読めない文字列は `atoi` の結果が 0 以下となる場合は1枠になります。9以上は8枠になります。明示的な範囲エラーはありません。複数回指定した場合は parser の最後の代入値が使われます（`engine/src/qwen35/q36_engine.cu:5345, 5348-5353, 5382, 1962-1967`; 上限8は同ファイル `1640`）。

値を省略すると `strata-q36: --batch needs a value` を標準エラーへ出して終了コード2で終了します（`engine/src/qwen35/q36_engine.cu:5350-5352`）。

## 実行時の動作

`--batch N` は `Engine::init` に渡され、内部セッション数を1〜8に正規化します。その数だけセッション状態とキャッシュを確保し、複数枠ではセッション状態を参照するデバイステーブルも作ります（`engine/src/qwen35/q36_engine.cu:5522, 1962-1967, 2140-2148, 2184-2203`）。

`--serve` では起動時に複数枠の数を `INFO batch_slots=N slot_cache=1` として標準出力へ出し、`READY` の後に入力を受けます。複数枠のリクエストは `BGEN <slot> ...` / `BGENI <slot> ...` で slot を指定し、他 slot の decode window をプロンプト読み込みの合間に実行します。単独枠では BGEN は拒否されます（`engine/src/qwen35/q36_engine.cu:4720-4724, 5012-5023, 5281-5285`）。

自動 `--chunk` の一部の経路では、複数枠時にプロンプト chunk の候補上限が1024になります。これは expert が VRAM に収まる条件での chunk 選択に限られ、明示的な `--chunk` や hybrid 経路の chunk 選択とは別です（`engine/src/qwen35/q36_engine.cu:5493-5517`）。

## 適用条件と副作用

- 枠数は `--serve` の有無にかかわらずエンジン初期化へ渡され、セッション状態を確保します。一方、複数リクエストを slot 指定で投入する BGEN/BGENI は serve プロトコルの機能です（`engine/src/qwen35/q36_engine.cu:5522, 5559-5563, 4720-4724`）。
- 複数枠では各枠の KV キャッシュと再帰状態の合計を見積もり、見積もりにさらに1 GiBの余裕を加えた量が確保前の空きVRAMを超えると、必要量を示すメッセージを標準エラーへ出して `exit(1)` します。メッセージは `--batch` の縮小または `--max-context` の短縮を案内します（`engine/src/qwen35/q36_engine.cu:2142-2159`）。
- `--batch-mtp` は `--batch` で複数枠があり、かつ `--mtp N` が正の場合にだけ有効です。条件を満たさない `--batch-mtp` は無視され、その理由を標準エラーへ出します（`engine/src/qwen35/q36_engine.cu:5556-5561`）。

## 出力とエラー

複数枠のVRAM見積もり失敗は標準エラーに診断を出して終了コード1です。`--batch` 値の欠落は標準エラーと終了コード2です（`engine/src/qwen35/q36_engine.cu:5350-5352, 2155-2159`）。serve 起動時には `INFO batch_slots=...` と `READY ...` を標準出力へ出します（`engine/src/qwen35/q36_engine.cu:5281-5285`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5345-5353, 5382`: 既定 parser 値、値の取得、`--batch` / `--slots` の別名、整数変換、値欠落の処理。
- `engine/src/qwen35/q36_engine.cu:1640, 1962-1967`: セッション数の最大値8と1〜8への正規化。
- `engine/src/qwen35/q36_engine.cu:2140-2159, 2184-2203`: セッション別状態の確保、複数枠のVRAM見積もりと失敗経路、バッチ用デバイステーブル。
- `engine/src/qwen35/q36_engine.cu:4720-4724, 5012-5023, 5281-5285`: serve の BGEN/BGENI slot 利用、slot 検証、起動時出力。
- `engine/src/qwen35/q36_engine.cu:5493-5517, 5522, 5556-5563`: 自動 chunk との相互作用、初期化への値の受け渡し、batch MTP 条件と実行モード分岐。

索引の Qwen3.6 専用 parser scope に対応する `--batch` リンクを確認しました（`docs/cli/README.md`）。
