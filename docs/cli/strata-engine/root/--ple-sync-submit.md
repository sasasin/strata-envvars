# `strata generate --ple-sync-submit`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--ple-sync-submit` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

PLE n-gram テーブルを直接読み込むとき、読み込み要求の投入と完了処理を専用 I/O worker に任せず、呼び出し側のスレッドで行う A/B 用フラグです。既定では worker thread が使われます。この設定はスレッド配置を変えるもので、読み込み方式そのものを選ぶ `--ple-io` とは別です。実測による速度上の推奨は、このソース調査からは判断できません。

## 使い方

```sh
# PLE テーブルを直接読み込む構成で、I/O worker を使わずに実行する
strata generate --pack pack/full --tokens "1,2,3" --ple-gguf /path/to/ple.gguf --ple-sync-submit
```

`--tokens` はこのエンジンの通常実行に必要です。`--ple-gguf` を省略しても `--native` のモデルに PLE tensor があり `--no-ple` が指定されていなければ、その tensor を含む shard が PLE table として選ばれる場合があります。

## 値と既定値

このオプション自体は値を取りません。未指定時は `ple_sync_submit = false` で、`io_thread` は有効になります。指定時は `ple_sync_submit = true` となり、`io_thread` が無効になります。parser は同じ引数を複数回受けても真を再設定するだけです。後続の値を消費する処理はなく、値・範囲の validation もありません。

## 実行時の動作

parser は `--ple-sync-submit` を見つけるとフラグを true にします。PLE table を開く段階で `pio.io_thread = !o.ple_sync_submit` として `PleTable::open` に渡し、direct 読み込みではさらに `PleReader::open` に転送します（`engine/src/program/generate.cpp:3905, 6270-6288`; `engine/src/kernels/ngram.cpp:449-460`）。

direct 読み込みでは、既定の worker 方式は worker が direct-file 操作を行い、呼び出し側は要求を組み立てて worker を起こします。`--ple-sync-submit` を付けると worker を生成せず、`issue` 側が読み込みを投入し、呼び出し側が完了を処理します（`engine/src/ngram/ple_reader.cpp:105-108, 375-389, 548-579`）。worker 方式では thread 作成に失敗すると PLE table の open が失敗し、エンジンはエラーを stderr に出して終了します。このフラグを有効にした経路ではその worker 作成は行われません（`engine/src/ngram/ple_reader.cpp:376-389`; `engine/src/program/generate.cpp:6288-6290`）。

## 適用条件と副作用

- PLE table が有効なときだけ設定が読み込み経路に伝わります。`--ple-gguf` で明示するほか、`--native` のモデルに `per_layer_token_embd.weight` があれば、`--no-ple` がない場合に shard が自動選択されます（`engine/src/program/generate.cpp:3899-3905, 5127-5134`）。PLE table が開かれない場合、このフラグの実行時効果はありません。
- `--ple-io direct`（既定）の場合に I/O worker の有無に作用します。`--ple-io mmap` / `ram` は mapped table の経路なので、このフラグによる `io_thread` 設定は読み込みに使われません（`engine/src/program/generate.cpp:6271-6276`; `engine/src/kernels/ngram.cpp:448-466`）。
- direct から mmap に切り替える自動 residency / probe 経路でも、最終的に mmap table が開かれれば `PleReader` の worker は使われません（`engine/src/program/generate.cpp:6304-6347, 6352-6375`）。
- direct 読み込み時は I/O worker thread の作成を抑止し、読み込み処理の担当スレッドを変えます。ファイル内容や PLE の値は変更しません。別スレッドでの処理による速度差や最適な設定は、性能測定をしていないため記載しません。
- CUDA 系 parser と SYCL parser の両方に同じフラグと `io_thread` の反転設定があります（`engine/src/program/generate.cpp:823, 3905, 6276`; `engine/sycl/src/program/generate.cpp:507, 1944, 3357`）。

## 出力とエラー

このフラグ専用の標準出力・警告はありません。PLE table を開けない場合は open のエラー文字列を `strata generate:` 付きで stderr に出し、終了コード 1 になります。I/O worker の作成失敗は、worker を必要とする既定経路で `PleReader: cannot create I/O worker`（例外文字列があればその内容を付加）として返されます。direct 読み込み・table open に必要なファイルなど、他の失敗要因まではこのフラグで回避されません（`engine/src/ngram/ple_reader.cpp:376-389`; `engine/src/program/generate.cpp:6288-6290`）。

## 根拠

- `engine/src/program/generate.cpp:823, 1228, 3905` — CUDA 系 option の既定値、help 表記、parser 登録。
- `engine/src/program/generate.cpp:6270-6288, 6304-6375` — PLE I/O 設定、direct/mmap 選択、自動切替、table open。
- `engine/src/kernels/ngram.cpp:449-466` — direct mode だけが `PleReader` を開き、`io_thread` を渡す。
- `engine/src/ngram/ple_reader.cpp:105-108, 375-389, 548-579` — worker 方式と呼び出し側処理の違い、worker 作成失敗経路。
- `engine/sycl/src/program/generate.cpp:507, 816, 1944, 3351-3357` — SYCL 系 parser と I/O 設定。
- `docs/cli/README.md:1036-1041, 1169-1175` — `strata-engine` の root scope と対象リンク（索引のみ。動作説明の根拠には使用していません）。
