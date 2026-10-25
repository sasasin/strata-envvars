# `--native`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` エンジン引数（`generate`） |
| オプション | `--native` |
| 別名 | なし（Qwen3.6 専用 parser では `--model` が同じ入力の別名） |
| 値 | GGUF モデルのファイルパス。単一ファイル、または分割モデルの任意の shard |

## 役割

GGUF モデルをネイティブ重みの供給元として指定します。エンジンは GGUF のモデル形状、PLE 表、埋め込み、head、dense projection を読み、ネイティブ実装の経路を有効にします。ネイティブ pack の expert を実行するときにも、この GGUF が量子化テンソルの供給元になります。`--native` 単独では pack ディレクトリを指定しません。pack は別途 `--pack` で指定します（`src/program/generate.cpp:813, 856-863, 3232-3282, 3753-3773`）。

## 使い方

```sh
strata generate --pack /path/to/pack --native /path/to/model-00001-of-00002.gguf \
  --tokens "1,2,3"
```

`--native` の後にはモデルファイルのパスを一つ渡します。分割 GGUF の場合はどの shard のパスでも受け付け、番号順に全 shard を解決します。ネイティブ pack を使う場合は、この例に加えて pack 用の `--spec` と `--prefill` の指定が必要です（`src/program/generate.cpp:18-49, 3753-3759`）。

## 値と既定値

- `--native PATH` は次の argv 要素を文字列として受け取ります。数値範囲や拡張子の parser validation はありません。値を省略すると `--native needs a value` を標準エラーに出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2421, 2500`）。
- 省略時は空文字列で、ネイティブ GGUF の処理は無効です。オプションを複数回指定した場合は `native_preset` への単純な代入なので最後の値が残ります（`src/program/generate.cpp:476, 2500, 3232`）。
- パスが `<name>-00001-of-0000N.gguf` 形式の分割 shard に一致する場合、`00001` から `N` までの全 shard を同じディレクトリ・stem で解決します。その他の名前は単一ファイルとして扱います。分割 shard が一つでも欠けていれば、不足ファイル名を含む例外になります（`include/strata/artifact/gguf_split.hpp:18-49`）。

## 実行時の動作

`--native` が空でなければ、まず GGUF shard を列挙し、先頭 shard のモデル family を確認します。認識済みでもこの経路で未対応の family は、未対応理由を標準エラーに出して終了コード 2 になります。通常の対象モデルでは、GGUF からモデル形状を読み、ビルド済みカーネル形状と照合します（`src/program/generate.cpp:3232-3245, 3653-3679`）。

PLE テーブル (`per_layer_token_embd.weight`) は、`--ple-gguf` が未指定かつ `--no-ple` でない場合に、全 shard から名前で検索して該当 shard を選びます。`--native` では PLE が必須で、`--no-ple` を指定した場合、または該当テンソルを見つけられない場合はエラーになります（`src/program/generate.cpp:3247-3261`）。

このオプションは次の設定も自動で有効にします。

- `--stream-token`、`--gr-native-mmvf`、`--native-bf16`、`--native-bf16-extra`、`--native-ple-key`、`--native-moe-combine`、`--native-gdn`、`--native-router`、`--native-qsa`、`--native-qsa-indexer`、`--native-rope`、`--native-ple-postops`。
- `--native-head-gguf` が未指定なら `--native` と同じ GGUF を head の供給元にします。
- `--native-dense-gguf` が未指定ならモデルの全 shard を指定元とし、PLE shard が別ファイルで PLE 専用形式 (`general.architecture = strata-ple`) でなければ、その shard も追加します。明示した `--native-head-gguf` / `--native-dense-gguf` は自動設定で置き換えません（`src/program/generate.cpp:3263-3282`）。

ネイティブ形式で提供される dense/head tensor は、既定で通常の canonical pack から重複ロードしないよう除外されます。`--keep-canonical` を指定すると canonical tensor もロードしますが、ネイティブ pack では `--keep-canonical` 自体が拒否されます（`src/program/generate.cpp:3753-3759, 3774-3783`）。

## 適用条件と副作用

- `--native` が有効なときは、GGUF のメタデータ・tensor を読み込みます。分割モデルでは全 shard が存在する必要があります。モデル family、GGUF の形状、tensor 構成が実装やビルドに合わなければ処理は続行しません（`src/program/generate.cpp:3232-3256, 3653-3679`; `include/strata/artifact/gguf_split.hpp:38-47`）。
- `--pack` がネイティブ pack（native expert layout）の場合は、`--native` に加えて `--spec T`（`T >= 2`）、`--keep-canonical` なしが必要です。プロンプトが複数 token なら `--prefill CHUNK` も必要です。これらを満たさないと終了コード 2 になります。これは native pack の条件であり、全ての `--native` 利用に対する共通条件ではありません（`src/program/generate.cpp:3753-3759`）。
- ネイティブ pack では token embedding を指定した GGUF から mapped host memory に読み込みます。`--embd-gguf` を指定すれば埋め込みの供給元だけを切り替えます（`src/program/generate.cpp:3761-3772, 860-862`）。Metal build では `--native` の shard を model shard として登録し、expert を mmap する設定になります（`src/program/generate.cpp:3422-3424`）。
- `STRATA_HAVE_QWEN35` build では、parser 本体の前に GGUF family を調べ、Qwen3.6-35B-A3B なら引数一式を専用 engine に転送します。転送先 parser では `--native` と `--model` が同じモデル値を設定します。この場合の専用 parser の詳細は [`strata-engine/qwen36/--native.md`](../qwen36/--native.md) を参照してください（`src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3742-3750`）。

## 出力とエラー

分割 shard が欠けている、GGUF が開けない、またはモデル family が未対応のときは、`strata generate: --native <path>: ...` 形式の診断を標準エラーへ出し、終了コード 2 で終了します。PLE が無効または検出できない場合も同じく終了コード 2 です（`src/program/generate.cpp:3237-3261`）。モデル形状の読込・検査で失敗する経路は `strata generate:` の診断を出し、終了コード 1 で終了します（`src/program/generate.cpp:3658-3678`）。成功時はネイティブ pack の経路で、pack 名、expert 形式、埋め込み形式・サイズと読込時間を標準エラーに表示します（`src/program/generate.cpp:3761-3772`）。

## 根拠

- 索引上の scope と配置: [`docs/cli/README.md`](../../README.md) の `strata-engine` / `root`（本書のリンク先）。同索引は `src/program/generate.cpp` parser と、`--native` による別 family 実装への引数転送を対象としています。
- usage と parser: `src/program/generate.cpp:813-863, 2418-2421, 2500-2503`。
- shard 解決: `include/strata/artifact/gguf_split.hpp:18-49`。
- PLE の解決、自動設定、拒否条件: `src/program/generate.cpp:3232-3285`。
- native pack の必要条件と埋め込み読込: `src/program/generate.cpp:3753-3773`。
- family 振り分け: `src/program/generate.cpp:2393-2407`; 専用 parser の受理: `src/qwen35/q36_engine.cu:3742-3750`。

調査範囲は上記 checkout のソースとリポジトリ内 CLI usage です。同 revision の安全な build 済み CLI help や Release artifact は確認していません。CUDA/HIP/Metal の全 build、各 GGUF variant の実行時挙動は実行確認していません。
