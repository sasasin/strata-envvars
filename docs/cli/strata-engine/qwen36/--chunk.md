# `--chunk`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` / `strata-q36`（Qwen3.6 専用 parser） |
| オプション | `--chunk` |
| 別名 | `--prefill` |
| 値 | prompt をまとめて処理する token 数。`auto` または `0` で自動選択。数値指定は 0〜4096。 |

## 役割

Qwen3.6 の prompt を一度に forward する token 数を指定します。省略時や `auto` では GPU の空き容量と expert 配置などから値を選び、明示値ではその chunk を使います。chunk は処理ごとの GPU バッファ確保量にも関わります。

## 使い方

```sh
# prompt の chunk を 1024 token に指定
strata --model model.gguf --chunk 1024 --tokens '1,2,3'

# 自動選択（省略時と同じ自動選択経路）
strata-q36 --model model.gguf --prefill auto --tokens '1,2,3'
```

## 値と既定値

- `--chunk` と `--prefill` は同じ変数 `chunk` に値を設定するため、同じ意味の別名です。後に指定された方が値を置き換えます（`engine/src/qwen35/q36_engine.cu:5348-5364`）。
- 省略時の初期値は `0` で、自動選択されます。値 `auto` も `0` に変換されます。数値 `0` も自動選択です（`engine/src/qwen35/q36_engine.cu:5342`, `5363`, `5475`）。
- 数値指定は 0〜4096 が受理範囲です。負数または 4096 超では `strata-q36: bad --chunk / --max-context` を stderr に出し、終了コード 2 で終了します（`engine/src/qwen35/q36_engine.cu:5457`）。
- parser は `std::atoi` で変換し、厳密な数値形式の検査はしていません。数値に変換できない値は `0` となり、自動選択へ入ります。数値で始まる文字列は先頭の数値部分が使われます（`engine/src/qwen35/q36_engine.cu:5363`）。
- 1〜7 の明示値は範囲検査を通りますが、初期化時に `tmax = max(tmax_, 8)` とされるため、実効 chunk は 8 です（`engine/src/qwen35/q36_engine.cu:1962-1968`）。

## 実行時の動作

自動選択時は `cudaMemGetInfo` で空き VRAM を取得し、モデルの expert 容量、packed expert コピー、`--expert-vram`、`--expert-slots` を考慮します。expert 群が収まると判定された場合は基本 512 から始め、batch 数、context 長、KV cache 形式などを使った追加の容量判定を満たせば 1024、2048、4096 の候補から大きい chunk を選びます。収まらない場合は空き容量に応じて 512、1024、2048 を選びます（`engine/src/qwen35/q36_engine.cu:5475-5515`）。

自動値は `STRATA_Q36_CHUNK` が設定されていればその値で上書きされ、256〜4096 に丸められます。この環境変数の上書きは自動選択経路だけで評価され、明示した `--chunk N` は上書きしません（`engine/src/qwen35/q36_engine.cu:5475-5477`, `5517`）。`STRATA_Q36_PLACE_DEBUG` が設定されている場合、自動選択の容量と選んだ値を stderr に出します（同 `5518-5520`）。

選ばれた値は `Engine::init` に渡され、`tmax` として prompt 用の各種バッファ確保に使われます（`engine/src/qwen35/q36_engine.cu:5522`, `1962-1985`）。prompt 処理は `tmax` ごとに入力 token を分割して GPU へ転送し、各区間を forward します。最後の区間だけ長さが短くなる場合があります（同 `3689-3727`）。

## 適用条件と副作用

- 対象は `strata-engine` の Qwen3.6 parser です。通常の `strata --model` 呼び出しでは GGUF の model family を読んで Qwen3.6 用 `strata::qwen35::run` へ切り替えます（`engine/src/program/generate.cpp:3804-3818`）。
- GPU の空き容量を参照する自動選択は実行時の配置状態に依存します。選択値は `--batch`、`--max-context`、`--kv`、expert 関連の指定によっても変わり得ます（`engine/src/qwen35/q36_engine.cu:5487-5515`）。
- chunk を大きくすると、そのサイズに応じた prompt バッファが確保されます。CUDA の確保・処理失敗時の詳細なエラー文や CUDA エラーコードはこのオプション固有には定められていません。
- ソース内の usage 文字列は `[--chunk 512]` と表示しますが、現在の parser 初期値は 0 であり、未指定時は前述の自動選択です（`engine/src/qwen35/q36_engine.cu:5342`, `5412-5416`）。

## 出力とエラー

- 値がない場合は `strata-q36: --chunk needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/qwen35/q36_engine.cu:5350-5352`）。
- 値が範囲外の場合は `strata-q36: bad --chunk / --max-context` を stderr に出し、終了コード 2 で終了します（同 `5457`）。
- 自動選択の詳細出力は `STRATA_Q36_PLACE_DEBUG` が設定されている場合に限られます（同 `5518-5520`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5339-5364` — 初期値、parser、`--chunk` と `--prefill` の alias、値変換。
- `engine/src/qwen35/q36_engine.cu:5412-5417`, `5457` — 未知引数の usage 表示と値の範囲検査。
- `engine/src/qwen35/q36_engine.cu:5475-5522` — 自動選択、環境変数上書き、Engine への適用。
- `engine/src/qwen35/q36_engine.cu:1962-1985`, `3689-3727` — 実効 `tmax`、バッファ確保と prompt の分割処理。
- `engine/src/program/generate.cpp:3804-3818` — model family による Qwen3.6 engine への切り替え。
- `docs/cli/README.md:1240-1248`, `docs/cli/000_cli_tools.md:10` — 文書の tool ID、コマンド階層、option scope。
