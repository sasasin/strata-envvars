# `--draft-vocab`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | macOS の `setup.py` → `metal/setup_mac.py` |
| オプション | `--draft-vocab` |
| 別名 | なし |
| 値 | `cjk`、`en`、`cyrillic`、`fr` のいずれか |

## 役割

Apple Silicon の Metal setup で、MTP（投機的デコード）の draft head が使うトークン subset を選びます。選択値に対応する配布済み subset を MTP runtime ディレクトリへ置き、生成する実行設定にも選択値を保存します。setup の選択肢であり、エンジン CLI に渡すオプションではありません。

## 使い方

Strata のソースディレクトリで、モデルの setup とともに指定します。

```sh
./setup.sh --setup --draft-vocab en
```

macOS では `setup.py` が `metal/setup_mac.py` に引数を転送します。既存設定がある状態で `--draft-vocab` だけを付けると通常起動経路に入り、値は適用されません。明示的に再 setup するには `--setup` を付けてください。

## 値と既定値

- `cjk`: 中国語・日本語・韓国語を含む標準 subset。
- `en`: 英語とコード向け subset。
- `cyrillic`: 英語・コードに加えてキリル文字を含む subset。
- `fr`: 英語・コードとフランス語向け subset。

parser は `choices=list(S.DRAFT_VOCABS)` で値を検証します。別名や短縮形はありません。既定値は parser 上 `None` です。setup の MTP runtime 更新時には未指定を `cjk` として扱いますが、設定 JSON の `draft_vocab` キーは明示指定時だけ書かれます。したがって、Mac で後から再 setup する際にこのオプションを省略すると、保存済みの選択を読み戻さず `cjk` を使用します。

## 実行時の動作

setup が既存設定から通常起動へ進まず、モデル準備を行う場合、MTP が使用されていれば `data/draft_vocab*.bin` の対応ファイルを `rt/draft_vocab.bin` に反映します。標準の `cjk` は `data/draft_vocab.bin`、他の値は `data/draft_vocab_en.bin`、`data/draft_vocab_cyrillic.bin`、`data/draft_vocab_fr.bin` に対応します。setup は `rt` ディレクトリを作成してから更新を呼び出します。

更新 helper は対象ファイルが存在しないか runtime ディレクトリがない場合は何もせず戻ります。既存の `rt/draft_vocab.bin` が Strata 配布 subset（旧 subset を含む）なら選択値と異なる場合に置き換え、同じ subset ならコピーしません。配布物の hash と一致しない手作り subset は保持します。更新後、生成する `strata-*.json` の `draft_vocab` に明示値を記録します。

既存 Metal config が見つかり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定されていないと、setup は既存 config を使って起動し、setup の選択処理を通りません。この早期分岐の条件に `--draft-vocab` は含まれないため、単独指定では既存の subset や config は変更されません。また、Mac のモデル条件により MTP を使わない場合は subset の更新処理自体が実行されません。

## 適用条件と副作用

- 対象は `setup.py` から `metal/setup_mac.py` に委譲される macOS の通常 setup（Apple Silicon / Metal）です。`STRATA_CONTROL_INSTALL=1` の Control mode はこの委譲を避けます。
- setup は選択した配布 subset を runtime ファイルへコピーし、実行設定 JSON を書き換えます。コピー先が手作り subset と判定される場合は上書きしません。
- Mac setup の parser は `parse_known_args` を使います。認識しない余剰引数は `not used on a Mac: ...` と警告して続行します。このオプションの不正な値は既知引数の `choices` 検証で拒否されます。
- setup 終了時は、`--no-start` がなければモデルサーバーを起動します。これはこのオプション固有の動作ではありません。

## 出力とエラー

配布 subset の置換時には `draft layer: ...` の状態メッセージを出します。配布元ファイルがない場合は helper が何もせず戻るため、この更新処理から専用エラーは出ません。選択肢外の値は argparse の validation で拒否され、setup 本体へ進みません。

## 根拠

- `setup.py:82`, `setup.py:7703-7707`, `setup.py:9062-9069`: Control mode 判定、Mac setup への委譲。
- `setup.sh:6-12`: 呼び出し元からの引数を `setup.py` へ転送。
- `metal/setup_mac.py:302-323`: 既存 config の起動処理。MTP があれば保存済み subset（未設定時 `cjk`）で runtime を更新。
- `metal/setup_mac.py:327-358`: parser、`--draft-vocab` の choices、未知引数の警告。
- `metal/setup_mac.py:369-371`: 既存 config がある場合の通常起動への早期分岐条件。
- `metal/setup_mac.py:518-540`: MTP 使用時の runtime ディレクトリ作成と subset 更新。
- `metal/setup_mac.py:551-560`: 明示値を config に記録し、設定ファイルを書き出す処理。
- `setup.py:7265-7270`: subset 名と配布ファイルの対応。
- `setup.py:7534-7553`: コピー条件、配布済み subset の置換、手作り subset の保持、出力。
