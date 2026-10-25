# `--model`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-q36ref` |
| コマンド | `strata-q36ref`（Qwen3.6 reference executable） |
| オプション | `--model` |
| 別名 | なし |
| 値 | 読み込む GGUF モデルファイルのパス。値の自動補完や形式変換はない |

## 役割

Qwen3.6 reference 実装に入力するモデル GGUF を指定します。この executable は Qwen3.6-35B-A3B の照合用で、モデルをロードして GPU 上に配置し、`--tokens` または `--tokens-file` の入力を処理します。CMake では GPU backend build 内で `strata-q36ref` target として定義されています。Release への同梱実績は索引・確認資料からは確認できません（`CMakeLists.txt:335,771-775`、`docs/cli/README.md:1490-1500`）。

## 使い方

```sh
strata-q36ref --model /models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf --tokens 248045,846,198 --n 64
```

この例はモデル GGUF と入力 token ID の両方を指定しています。`--model` だけでは実行できず、少なくとも一つの token ID も必要です（`src/qwen35/q36ref.cu:25-31,771-774`）。

## 値と既定値

- 値は次の argv 要素をそのまま文字列として受け取ります。parser に拡張子・パス存在・モデル名の事前検証はありません（`src/qwen35/q36ref.cu:727-735`）。
- 既定値は空文字列です。`--model` が省略された場合、または空文字列を指定した場合は、必須入力チェックで `q36ref: --model and --tokens are required` を stderr に出して終了コード 2 になります（`src/qwen35/q36ref.cu:723-724,771-774`）。
- 同じ option を複数回指定した場合は、各値を同じ変数へ代入するため最後の値が使われます（`src/qwen35/q36ref.cu:725-735`）。
- option の後に値がなければ `q36ref: --model needs a value` を stderr に出し、終了コード 2 で終了します。次の argv が別 option の表記でも、値として消費されます（`src/qwen35/q36ref.cu:727-735`）。

## 実行時の動作

受け取った文字列を `load()` に渡し、GGUF モデルを開きます。GGUF からモデル形状を読み取り、family が `Qwen35Moe`（Qwen3.6 の内部 family 名）であることとテンソル配置を検査します。条件を満たすと、モデルの shard を走査し、対象テンソルのデータを GPU に割り当ててコピーします。したがって、この値はモデル名やカタログ ID ではなく、読み込み対象ファイルのパスです（`src/qwen35/q36ref.cu:479-500,517-533,778-780`）。

モデルのパスは `GgufModel::open()` に渡されます。同 helper は指定 shard から split GGUF のパス一覧を解決して `GgufModel` を構築します（`include/strata/artifact/gguf_reader.hpp:562`）。モデルのダウンロードやファイル生成を行う処理は、この option の parser / load 経路では確認できません。

## 適用条件と副作用

- 対応 family は `Qwen35Moe` のみです。他 family の GGUF は `this reference path is for Qwen3.6-35B-A3B (qwen35moe) only` として拒否されます。GGUF の形状・テンソル配置の検査にも失敗すればロード失敗になります（`src/qwen35/q36ref.cu:481-488`）。
- 読み込み時にモデル重みを GPU に確保します。実際に利用可能な GPU/backend、VRAM 要件、個別モデルでの成功可否はこのソース確認だけでは実行検証していません。build target 自体は GPU backend 用の条件節内にあります（`CMakeLists.txt:335,771-775`）。
- 入力ファイルが開けない場合など `load()` 内の例外は catch され、メッセージを stderr に出して終了コード 1 になります。family・レイアウト検査が false を返す場合も stderr に理由を出して終了コード 1 です（`src/qwen35/q36ref.cu:777-784`、ファイル open は `include/strata/artifact/gguf_reader.hpp:414-443`）。
- ロード成功時は、指定ファイル名とロードした tensor 数、GPU 使用量、所要時間を stderr に出します（`src/qwen35/q36ref.cu:536-538`）。

## 根拠

- `src/qwen35/q36ref.cu:25-31` — usage と照合用 reference executable の説明。
- `src/qwen35/q36ref.cu:722-735,771-784` — parser、既定値、必須条件、エラー出力・終了コード、load 呼び出し。
- `src/qwen35/q36ref.cu:479-500,517-538` — GGUF の検査とモデル tensor のロード。
- `include/strata/artifact/gguf_reader.hpp:414-443,562` — ファイル open と split GGUF 解決。
- `CMakeLists.txt:335,771-775` — GPU build 内の target 定義。
- `docs/cli/README.md:1490-1500` — 文書の索引位置と `strata-q36ref` の分類。

`strata-q36ref` の実行ファイルはこの環境で起動しておらず、CLI `--help` と実機ロードは補助確認していません。上記は指定 revision のソースに基づきます。
