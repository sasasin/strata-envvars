# `strata-inkling --export-tokenizer`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--export-tokenizer` |
| 別名 | なし |
| 値 | 入力モデルのパスと出力ディレクトリの2値。順に `PATH OUT_DIR` |

## 役割

モデルを開いて、モデルに含まれる tokenizer JSON と chat template を出力ディレクトリへ取り出すメタデータモードです。引数解析後、通常の推論・serve・benchmark 初期化より先に実行され、GPU backend は初期化しません。CUDA/HIP ビルドの `strata-inkling` トップレベルで使います（`engine/src/inkling2/ink_main.cpp:1-2,32-56,544-549`）。

## 使い方

```sh
# 既存モデルから tokenizer 関連ファイルを ./tokenizer-export へ取り出す
strata-inkling --export-tokenizer ./model.strata ./tokenizer-export
```

入力には Inkling が開ける `.strata`、safetensors、または GGUF のモデルパスを指定します。入力パスの形式判定と各形式の読み込みは `InkModelFile::open` が行います（`engine/src/ink_manifest.h:454-477`）。

## 値と既定値

- `--export-tokenizer` の後に、入力パス、出力ディレクトリの順で2値が必要です。値の拡張子やディレクトリ存在を CLI parser が検証する処理はありません（`engine/src/inkling2/ink_main.cpp:379-391`）。
- いずれかの値が欠けると `missing value after --export-tokenizer` を標準エラーへ出し、終了コード 2 で終了します（`engine/src/inkling2/ink_main.cpp:381-383`）。既定値はありません。
- 同じオプションを複数回指定した場合、走査中に保存先変数が更新されるため、最後に解析された組が使われます（`engine/src/inkling2/ink_main.cpp:379-392`）。

## 実行時の動作

- `InkModelFile::open(..., keep_tokenizer=true)` で入力を開き、モデル形式に応じて tokenizer と chat template を読み取ります。Strata manifest では両項目は任意の文字列として読み込まれます（`engine/src/inkling2/ink_main.cpp:32-36`; `engine/src/ink_manifest.h:454-477,329-330`）。safetensors 入力では `chat_template.jinja` と `tokenizer.json` を読みます（`engine/src/ink_safetensors_loader.h:505-509`）。GGUF 入力では埋め込み tokenizer を抽出します（`engine/src/ink_gguf_loader.h:914-918`）。
- 指定ディレクトリを `std::filesystem::create_directories` で作成し、内容が空でない場合に `chat_template.jinja` と `tokenizer.hf.json` を書きます。空の内容は対応ファイルを作らずにスキップします（`engine/src/inkling2/ink_main.cpp:39-53`）。
- 出力ファイルは `wb` で開くため、同名ファイルがあれば上書きします。成功時は標準出力に入力形式名と各内容の byte 数を表示し、終了コード 0 です（`engine/src/inkling2/ink_main.cpp:40-56`）。
- 引数解析で両方のモードが認識された場合（例: `--info FILE --export-tokenizer MODEL DIR`）、分岐順により `--info` が先に実行され、tokenizer の書き出しには進みません。`--export-tokenizer` は `--selfcheck`、`--bench`、通常生成などより先に処理されます（`engine/src/inkling2/ink_main.cpp:544-550`）。

## 適用条件と副作用

- 入力モデルの読み込みに失敗すると `open: <理由>` を標準エラーへ出し、終了コード 1 で戻ります（`engine/src/inkling2/ink_main.cpp:32-38`）。
- 出力先ディレクトリがなければ作成します。既存ファイルは上書きされ、空の tokenizer/template はファイル出力されません（`engine/src/inkling2/ink_main.cpp:39-53`）。
- ファイルを開けない、または `fwrite` が全 byte を書けない場合は `cannot write <path>` を標準エラーへ出し、その時点で終了コード 1 となります。先に書いたファイルや失敗時の部分ファイルを削除する処理はありません（`engine/src/inkling2/ink_main.cpp:40-53`）。
- `create_directories` の例外処理はこの関数内にありません。ディレクトリ作成失敗時の具体的な表示・終了状態は、このコードからは確認できません（`engine/src/inkling2/ink_main.cpp:39`）。
- tokenizer の抽出処理は通常のモデル backend 初期化より先に分岐します（`engine/src/inkling2/ink_main.cpp:544-550`）。ただし `main` 冒頭の HIP NUMA helper と CUDA module loading helper は引数解析前に実行されます（`engine/src/inkling2/ink_main.cpp:360-369`）。

## 出力とエラー

| 条件 | 出力・結果 |
| --- | --- |
| 必須値不足 | 標準エラー `missing value after --export-tokenizer`、終了コード 2（`engine/src/inkling2/ink_main.cpp:381-383`） |
| 入力モデルを開けない | 標準エラー `open: ...`、終了コード 1（`engine/src/inkling2/ink_main.cpp:32-38`） |
| 出力ファイルの open/write 失敗 | 標準エラー `cannot write <path>`、終了コード 1（`engine/src/inkling2/ink_main.cpp:40-47`） |
| 成功 | 標準出力 `format=... chat_template: ... bytes, tokenizer_json: ... bytes`、終了コード 0（`engine/src/inkling2/ink_main.cpp:54-56`） |

## 根拠

- `engine/src/inkling2/ink_main.cpp:32-56` — モデルを tokenizer 保持モードで開く処理、出力ディレクトリ作成、空内容のスキップ、出力ファイル名・書き込み・結果表示。
- `engine/src/inkling2/ink_main.cpp:379-391,488-502,544-550` — parser の引数順序と不足値処理、help 表記、モード分岐の優先順。
- `engine/src/ink_manifest.h:454-477,329-330` — Strata / safetensors / GGUF の入力振り分けと Strata manifest 内の任意 tokenizer/template 値。
- `engine/src/ink_safetensors_loader.h:505-509` — safetensors 由来の tokenizer/template ファイル読み込み。
- `engine/src/ink_gguf_loader.h:914-918` — GGUF 由来の埋め込み tokenizer 抽出。
- `docs/cli/README.md:1509-1523` — `strata-inkling` のトップレベル scope と本オプションの索引リンク。索引は配置確認にのみ使用し、動作説明の根拠にはしていません。
