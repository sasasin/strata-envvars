# `STRATA_DUMP_CTX`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

Qwen3.6 の比較用ツール `tools/qwen35/q36_llama_dump.cpp` が llama.cpp のコンテキストを初期化するとき、context・batch・ubatch の各サイズに使う整数を指定します。Strata の通常の実行ファイルやサーバーの設定ではなく、llama.cpp checkout にリンクして別途ビルドする比較用ダンプツールだけが読みます。

## 値と判定

| 環境変数の状態・値 | `nctx` として使う値 |
|---|---:|
| 未設定 | `4096` |
| 設定あり | `std::atoi` の戻り値 |
| 空文字、数字で始まらない文字列 | `0` |
| 数字の後ろに文字がある文字列 | 数字部分を `atoi` で変換した値（例: `128tokens` は `128`） |

`atoi` は先頭の空白と符号を受け付け、整数として読める先頭部分を変換します。文字列全体の妥当性確認、空文字時の既定値への戻し、値の clamp はありません。したがって、負数も変換された値のまま設定されます。整数型の範囲を超える入力の結果はこの実装から保証できません。

## 有効になる条件

この環境変数を読むのは `q36_llama_dump` のみです。ソース先頭のビルド手順は llama.cpp の include / library にリンクして別途コンパイルする形を示し、Strata の build には含まれないと明記しています。`tools/qwen35/parity.py` は `q36_llama_dump` を比較処理の一方として呼び出しますが、この変数自体はその Python スクリプトでは読まず、子プロセスへ明示的に値を設定する処理もありません。通常の Strata engine や他のツールへの効果は確認できません。

## 実行時の詳細

ツールはモデルをロードして prompt/token ID を準備した後、コンテキスト作成前に環境変数を一度読みます。未設定なら `nctx=4096`、設定されていれば `std::atoi(cx)` の結果を使い、`cp.n_ctx`、`cp.n_batch`、`cp.n_ubatch` のすべてに同じ値を代入してから `llama_init_from_model()` を呼びます。このコードには範囲検査やエラー処理がありません。無効なサイズを渡した場合にどうなるかは、リンク先 llama.cpp の実装に依存するため、Strata 側の挙動としては断定できません。

環境変数を再度読むループはなく、プロセス中に値を変更してもこの初期化済みコンテキストには反映されません。ソースコメントには、数百 token の parity sequence を扱う際、重みが大きく 4096-token compute buffer 用 VRAM が残らない場合に小さい context/batch を指定する用途が記されています。これは用途説明であり、特定の値でのメモリ使用量や性能は測定・保証されていません。

## 根拠

- `tools/qwen35/q36_llama_dump.cpp:1-13` — 比較用ダンプツール、外部 llama.cpp checkout にリンクした別ビルドであること。
- `tools/qwen35/q36_llama_dump.cpp:90-104` — 既定値 `4096`、`atoi` による読み取り、3つの context/batch パラメーターへの代入、context 初期化。
- `tools/qwen35/parity.py:1-10,44-70` — parity 比較が `q36_llama_dump` を呼び出すことと、呼び出し時の CLI 引数。
- `docs/QWEN36.md` および `docs/DETAILS.md` — この変数の値・判定・適用条件に関する追加説明は確認できませんでした。
