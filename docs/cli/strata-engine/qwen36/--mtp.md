# `--mtp`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 専用 parser。`strata-q36` も同じ実装を呼ぶ） |
| オプション | `--mtp` |
| 別名 | なし |
| 値 | 整数として扱うドラフト数。受理範囲は `0..7` |

## 役割

Qwen3.6 の GGUF 内にある MTP (multi-token prediction) ブロックを用いて、次トークン候補を指定数だけ先読みする設定です。候補は通常モデルの推論で検証され、採用された場合に複数トークンを一度に進めます。Qwen3.6 では `--mtp` の値は外部ドラフト層のパスではなくドラフト数です。

## 使い方

```sh
# Qwen3.6 GGUF を使い、通常のトークン入力で最大2個の候補を先読みする
strata --model qwen36.gguf --tokens 1,2,3 --mtp 2

# serve モードでも MTP を有効にする（サンプリング要求では既定で MTP の先読みを使わない）
strata --model qwen36.gguf --serve --mtp 2
```

## 値と既定値

- 省略時は `0` で、投機的な MTP ドラフトを行いません。明示できる数値範囲は `0..7` で、範囲外はエラーになります。
- 値は `--mtp` の直後の引数から読みます。引数がなければ `needs a value` を stderr に出して終了コード 2 で終了します。
- 先頭文字が数字でない値は数値化せず、`ignoring --mtp <値>` の警告を出してその指定を無視します。負数もこの扱いです。先頭が数字なら `atoi` で変換するため、例えば `2x` は `2` として扱われます。変換後が `0..7` 外なら `--mtp takes 0 .. 7 drafts` を stderr に出して終了コード 2 です。
- 複数回指定した場合、数値として解析された指定は後の値で更新されます。後続の非数値指定は無視されるため、それ以前の数値を消しません。

## 実行時の動作

Qwen3.6 専用 parser は値を `mtp_d` に格納し、範囲検証後にモデルを読み込みます。MTP ブロックの有無は `--mtp` ではなく GGUF の `qwen35moe.nextn_predict_layers` メタデータで決まり、ファイルにブロックがあれば `--mtp 0` でもモデル読込時にロードされます。逆にファイルにブロックがなければ、正の数を指定しても実行時のドラフト数は 0 になります。

数値が正で MTP ブロックもある場合、プロンプト処理時に MTP の状態を準備し、デコード時に最大指定数の候補を作って通常モデルの出力と比較します。`--serve` では単独の greedy 要求が対象で、サンプリング要求は既定では一トークンずつ処理されます。環境変数 `STRATA_Q36_MTP_SAMPLED` が設定され、値が `0` 以外ならサンプリング要求でもこの経路を使います。別要求が同時に進行中の要求や batch admission 要求も単独 speculative 経路の対象外です。バッチで MTP を使うには複数 slot と `--batch-mtp` または `STRATA_BATCH_MTP` が必要です。

非 serve の通常生成では、強制トークン列 (`--force`) や全 logits 出力 (`--dump-full-logits`) がない場合に MTP 生成経路へ入り、それ以外は通常の greedy 生成です。ウォームアップが有効なら、正のドラフト数のとき起動時にも speculative step を実行します。

## 適用条件と副作用

- この `qwen36/` スコープは、`--model` / `--native` の GGUF architecture が `qwen35moe` の場合に `strata` から振り分けられる parser です。別 family の `strata-engine/root/--mtp` は別スコープで、値の意味も異なります。
- MTP ブロックはモデルファイル内のブロックです。Qwen3.6 parser は `--mtp <ドラフト層ディレクトリ>` を受け取った場合、先頭文字が数字でなければその値を無視して警告します。これは同じ `strata` バイナリの他 family で使われるパス指定と混同しないでください。
- 正のドラフト数は MTP の GPU 推論・検証処理を追加します。MTP ブロック自体はドラフト数 0 でも読み込まれるため、`--mtp 0` が MTP ブロックのロードや VRAM 使用を無効化するわけではありません。
- MTP ブロックの構造・テンソルを読めない場合や GPU 資源の確保に失敗した場合、ロード／初期化経路が失敗します。メモリ不足の診断には、より小さい `--max-context`、`--mtp 0`、slot 数の削減などを案内する経路があります。

## 出力とエラー

- 引数不足、ドラフト数の範囲外、未知の引数などは stderr に usage またはエラーを出し、終了コード 2 で終了します。
- MTP ブロックのモデル読込エラーは stderr に理由を出し終了コード 1 です。C++ 例外もそのメッセージを stderr に出し、終了コード 1 です。
- `--mtp` に非数値を渡した場合は警告だけを stderr に出し、その指定については起動を継続します。ロード後にモデル内 MTP ブロックがなければ、正の指定も実効値 0 になります。

## 根拠

- `engine/src/program/generate.cpp:3805-3818` — `--model` / `--native` の GGUF architecture を確認し、Qwen3.6 (`qwen35moe`) なら専用 `strata::qwen35::run` に振り分ける。
- `engine/src/qwen35/q36_engine.cu:5339-5379` — Qwen3.6 parser、既定値、値の読み方、非数値の警告。
- `engine/src/qwen35/q36_engine.cu:5456-5465` — `0..7` の検証、モデルロードの失敗コード。
- `engine/include/strata/artifact/gguf_reader.hpp:734-742` と `engine/include/strata/core/family_layout.hpp:63-81` — GGUF メタデータの MTP 層数の読取と通常層数への反映。
- `engine/src/qwen35/q36_engine.cu:1453-1461` — GGUF の MTP ブロック有無で読込対象を決め、`want_mtp` / CLI 値にかかわらずブロックをロードする。
- `engine/src/qwen35/q36_engine.cu:3728-3736`, `4010-4019`, `5177-5181`, `5238-5255` — プロンプト中の MTP 状態準備、候補検証と採用、serve で MTP を使う条件。
- `engine/src/qwen35/q36_engine.cu:4038-4053`, `5554-5562`, `5614-5637` — ウォームアップ、GGUF による実効ドラフト数、serve / 通常生成の分岐。
- `engine/src/qwen35/q36_engine.cu:4413-4425` — VRAM 割当失敗時の stderr とメモリ不足案内。
