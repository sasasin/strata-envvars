# `--ple-gguf`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--ple-gguf` |
| 別名 | なし |
| 値 | `PATH`。PLE tensor `per_layer_token_embd.weight` を含む GGUF ファイルのパス |

## 役割

モデルの PLE（Per-Layer Embeddings、n-gram 表）を読み込むファイルを指定する。推論時に PLE 表を開き、モデルの PLE 実行に接続する。通常の `strata generate` では `--no-ple` による診断用 ablation を明示しない限り、この引数が必要。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --native model-00001-of-00002.gguf --ple-gguf model-00002-of-00002.gguf
```

`--native` は省略時に同じモデルの shard から PLE tensor を探すが、別ファイルを明示する場合やモデル形式に応じた shard を指定する場合は `--ple-gguf PATH` を渡す。

## 値と既定値

- 値は一つの文字列として受け取る。parser は `--ple-gguf` の直後の argv 要素を保存し、値の形式・拡張子・存在確認はこの時点では行わない。値を省くと `--ple-gguf needs a value` を stderr に出して終了コード 2 で終了する（`engine/src/program/generate.cpp:3842-3846,3899`）。
- 同じ引数を複数回指定した場合、parser は各値を順に同じ設定へ代入するため最後の値が残る（`engine/src/program/generate.cpp:3842-3847,3899`）。
- `--native` がない経路では自動設定されず、PLE を有効にする実行では必須。`--native` がある場合は、明示値が空で、かつ `--no-ple` でないとき、モデル全 shard から `per_layer_token_embd.weight` を探し、その tensor を含む shard を設定する（`engine/src/program/generate.cpp:5127-5134`）。
- `--native` の shard 群にその tensor がなければ、`--native requires --ple-gguf ...` のエラーを stderr に出して終了コード 2。`--no-ple` と同時指定した場合も相互排他エラーで終了コード 2（`engine/src/program/generate.cpp:5155-5158,5205-5207`）。PLE 無効化を明示しないまま値が空の場合は `--ple-gguf is required` で終了コード 2（`engine/src/program/generate.cpp:5213-5215`）。

## 実行時の動作

指定ファイルを `PleTable::open` で GGUF として開き、`per_layer_token_embd.weight` の存在、shape、形式、スケール metadata（対象形式の場合）、データ範囲とファイルサイズを検証する。ファイルを開けない場合や検証に失敗した場合、理由を `strata generate:` に続けて stderr に出し、終了コード 1 で終了する（`engine/src/program/generate.cpp:6269-6290`; `engine/src/kernels/ngram.cpp:364-405,413-446`）。

`--native` の場合、dense GGUF の入力群に PLE shard が含まれるかを同一ファイル判定で確認し、PLE tensor だけのファイルでなければ必要に応じて dense shard 群へ追加する。これはモデル shard を PLE 表としても使う構成を処理するためである（`engine/src/program/generate.cpp:5166-5190`; `engine/src/kernels/ngram.cpp:259-267`）。

読み込み方式やキャッシュはこのオプション単独では指定せず、`--ple-io`、`--ple-inflight`、`--ple-row-cache`、`--ple-sync-submit` 等の設定から `PleIoOptions` を組み立てて同じファイルを読む（`engine/src/program/generate.cpp:6270-6276`）。構築後は PLE の準備完了を確認し、読み込んだ表の行数とパスを stderr に表示する（`engine/src/program/generate.cpp:7756-7762`）。セッション識別情報にも PLE 入力パスを渡す（`engine/src/program/generate.cpp:13970-13979`）。

## 適用条件と副作用

- `--native` を使わない実行でも PLE は既定で有効であり、このパスの指定が必要。`--no-ple` は診断用の明示的 ablation であり、本オプションと併用できない（`engine/src/program/generate.cpp:5205-5215`）。
- `--native` では、モデル shard 内に PLE tensor がある場合、明示指定を省略してもその shard が選ばれる。明示したパスは自動選択より優先される（`engine/src/program/generate.cpp:5127-5134`）。
- `--ple-io` の実効モードにより読み込み時の副作用が異なる。`direct` では GGUF header を検証した後に mapping を解放し、行を直接読み込む。`mmap` は表を map し、`ram` は map した表の lock を試みる。lock に失敗した場合は警告してページを読み込み、実行を続ける（`engine/src/kernels/ngram.cpp:448-490`）。
- `--ple-io` を明示せず direct 読み込みを使う場合、メモリ余裕などの条件で residency policy が RAM 常駐を選ぶことがある。明示指定はこの自動選択より優先される（`engine/src/program/generate.cpp:6292-6307,6324-6347`）。低速 direct read の probe は警告を出す場合があり、`STRATA_PLE_AUTO_MMAP` 等の条件で mmap へ切り替える場合もある（`engine/src/program/generate.cpp:6350-6383`）。
- 本オプション自身は指定ファイルを変更しない。実際の読み込みは表データを読むため、選択した方式に応じて OS file cache や RAM の使用量が変わる（`engine/src/kernels/ngram.cpp:448-490`）。

## 根拠

- `engine/src/program/generate.cpp:774-775` — `Options` の保存先と `--no-ple` の診断用途。
- `engine/src/program/generate.cpp:1218-1220,1386-1387` — ソース内 usage 表示。説明文には必須指定と未指定時にスキップする記載が併存するが、現行 parser 後の検証では、`--no-ple` なしの未指定をエラーにする `engine/src/program/generate.cpp:5213-5215` を実際の挙動として扱った。
- `engine/src/program/generate.cpp:3899` — parser 登録。
- `engine/src/program/generate.cpp:5127-5190,5205-5215` — `--native` 時の推定、shard 処理、必須条件と相互排他。
- `engine/src/program/generate.cpp:6264-6290,7756-7762` — PLE 表の読み込み・エラー・起動時表示。
- `engine/src/kernels/ngram.cpp:259-267,364-446,448-490` — table-only shard 判定、GGUF tensor 検証、direct/mmap/lock の動作。
- `engine/src/program/generate.cpp:13970-13979` — セッション入力への PLE パス登録。

調査範囲は上記 checkout のエンジン parser と PLE 読み込み・利用箇所。ビルド済み CLI の `--help` は実行していない。
