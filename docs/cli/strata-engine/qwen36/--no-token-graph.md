# `strata` / `strata-q36` `--no-token-graph`（Qwen3.6）

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 専用実行経路（別 executable は `strata-q36`） |
| オプション | `--no-token-graph` |
| 別名 | なし（同じ効果を持つ別表記 `--no-graph` も受理） |
| 値 | なし。boolean フラグ |

## 役割

Qwen3.6 用エンジンで既定の CUDA Graph capture/replay を無効にし、グラフ実行箇所の処理を通常の stream launch で行います。これは汎用 `strata-engine/root` の同名オプションとは別スコープです。Qwen3.6 では「1 token を1 graphにまとめる方式を、レイヤーごとの2 graphに切り替える」という意味ではありません。

## 使い方

```sh
# Qwen3.6 GGUF を指定し、入力 token IDs を処理するときに graph 実行を無効化
strata --model ./qwen36.gguf --tokens 1,2,3 --no-token-graph
```

Qwen3.6 GGUF のヘッダーが family switch により認識されると、この引数列は専用 parser に渡されます。`strata-q36` を直接起動する場合も同じ parser が使われます。

## 値と既定値

値は取りません。parser 内の `graph` は初期値 `true` で、`--no-token-graph` を受け取ると `false` になります。`--no-graph` も同じ変数を `false` にするため同じ効果です。どちらも複数回指定しても状態は変わりません。値の範囲検証はなく、`--no-token-graph` の後ろに `false` などを値として付ける構文もありません（`engine/src/qwen35/q36_engine.cu:5346-5358`, `engine/src/qwen35/q36_engine.cu:5371`）。

## 実行時の動作

parser 完了後、`graph` の値が `Engine::use_graph` に設定されます。`graph_run` は `use_graph == false` の場合、stream capture・graph instantiate・graph launch を行わず、渡された処理本体を直接実行します。これは単一 token の処理だけでなく、batch row window や verify window など、同じ helper を通る実行にも適用されます（`engine/src/qwen35/q36_engine.cu:3612-3634`, `engine/src/qwen35/q36_engine.cu:3707-3709`, `engine/src/qwen35/q36_engine.cu:3762-3764`, `engine/src/qwen35/q36_engine.cu:3801`, `engine/src/qwen35/q36_engine.cu:4003-4006`, `engine/src/qwen35/q36_engine.cu:5466-5474`）。

通常の `strata --model ...` はモデルの GGUF family を確認し、Qwen3.6 (`Qwen35Moe`) の場合に `strata::qwen35::run(argc, argv)` へ引数を渡します。したがってこの文書の parser が対象にするのはその専用経路です（`engine/src/program/generate.cpp:3804-3818`）。

プロンプトの複数 token は chunk 単位で eager に処理される経路があり、このオプションが一律にプロンプト処理全体を graph 化／非 graph 化するわけではありません（`engine/src/qwen35/q36_engine.cu:3685-3689`）。

## 適用条件と副作用

- Qwen3.6 専用 parser が使われる呼び出しで有効です。モデル family が Qwen3.6 として振り分けられない場合、`strata` は汎用 parser 側に進みます（`engine/src/program/generate.cpp:3804-3818`）。
- graph capture を避けるため、CUDA Graph instantiate 時のエラー経路も通りません。通常どおり stream launch 等で発生した CUDA エラーは `CK` 経由で stderr に出て、プロセスは終了コード `1` で終了します（`engine/src/qwen35/q36_engine.cu:82-89`, `engine/src/qwen35/q36_engine.cu:3612-3634`）。
- graph が有効なとき instantiate に失敗した場合、`volta-forever` 状態では警告を出して stream launch に切り替えます。それ以外は `CK` のエラー経路です。この切替は本オプションが無効化した状態とは別の fallback です（`engine/src/qwen35/q36_engine.cu:3614-3632`）。
- フラグ自体に専用の stdout/stderr 出力やファイル変更処理はありません。

## 出力とエラー

このフラグ単独では出力しません。Qwen3.6 parser で未認識の引数があると stderr に usage を出し、終了コード `2` を返します。usage の表記は `--no-graph` ですが、parser は `--no-token-graph` も明示的に受理します（`engine/src/qwen35/q36_engine.cu:5357`, `engine/src/qwen35/q36_engine.cu:5371`, `engine/src/qwen35/q36_engine.cu:5412-5417`）。

## 根拠

- `engine/src/program/generate.cpp:3804-3818` — GGUF family に基づく Qwen3.6 専用 parser への振り分け。
- `engine/src/qwen35/q36_engine.cu:5346-5358` — `graph` の既定値と `--no-token-graph` の parser 定義。
- `engine/src/qwen35/q36_engine.cu:5371`, `engine/src/qwen35/q36_engine.cu:5412-5417` — `--no-graph` との同一設定、usage と未知引数の失敗経路。
- `engine/src/qwen35/q36_engine.cu:3612-3634`, `engine/src/qwen35/q36_engine.cu:5466-5474` — 設定の `Engine::use_graph` への反映、capture/replay と直接実行の分岐。
- `engine/src/qwen35/q36_engine.cu:3685-3689`, `engine/src/qwen35/q36_engine.cu:3707-3709`, `engine/src/qwen35/q36_engine.cu:3762-3764`, `engine/src/qwen35/q36_engine.cu:3801`, `engine/src/qwen35/q36_engine.cu:4003-4006` — eager prompt 経路および token / batch / verify 実行から graph helper への呼び出し。
- `engine/src/qwen35/q36_engine.cu:82-89` — CUDA 呼び出しエラーの stderr 表示と終了コード。
