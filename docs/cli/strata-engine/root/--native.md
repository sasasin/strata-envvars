# `strata --native`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジンの root 引数） |
| オプション | `--native` |
| 別名 | なし（Qwen3.6 専用 parser の別スコープでは `--model` の別名として受理） |
| 値 | GGUF モデルファイルのパス。split GGUF なら任意の shard のパスを指定できる |

## 役割

量子化済み pack と組み合わせる GGUF モデルを指定し、その GGUF から dense projection と出力 head などの native 経路を構成します。native (IQ) pack の場合は GGUF から token embedding もロードします。通常の root parser では指定時に native 推論用の複数機能もまとめて有効になり、split GGUF の shard 群を検出してモデルの geometry や重みを読みます。索引で別項目になっている Qwen3.6 専用 parser は `generate.cpp` から family 判定後に別実装へ分岐するため、本書の値や動作の説明には含めません（`engine/src/program/generate.cpp:3804-3818`）。

## 使い方

```sh
# native (IQ) pack とモデルの split GGUF を指定して token ID から推論する例
strata --pack /models/iq3_s --native /models/model-00001-of-00002.gguf \
  --ple-gguf /models/model-00002-of-00002.gguf --tokens '1,2,3' \
  --spec 2 --prefill 512
```

パスと token ID は利用環境の実ファイル・入力に置き換えます。native pack では `--spec` が 2 以上であること、および複数 token の prompt では `--prefill` が必要です。PLE tensor がモデル shard のいずれかにあれば `--ple-gguf` は省略でき、実装がその shard を選びます（`engine/src/program/generate.cpp:5127-5134`, `5782-5787`）。

## 値と既定値

- 値は1個のパス文字列です。値のない `--native` は `--native needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3842-3847`, `3926`）。
- 省略時は `native_preset` が空のままで、native GGUF の探索・関連する一括有効化は行いません（`engine/src/program/generate.cpp:814`, `5112`）。同じ引数を複数回指定した場合、parser は値を都度代入し、重複指定を拒否しません。後の値が残ります（`engine/src/program/generate.cpp:3842-3847`, `3926`）。
- パーサー段階で拡張子やファイル存在を検証しません。後段の `gguf_split_paths` は、ファイル名が `-NNNNN-of-MMMMM.gguf` 形式なら番号を 1 から M まで書き換えて各 shard を確認し、それ以外は指定パス1個をモデルとして扱います。欠けた shard は例外になります（`engine/include/strata/artifact/gguf_split.hpp:18-49`）。

## 実行時の動作

1. root parser は `--native` の次の argv を `native_preset` に保存します。空文字列を渡すと保存値も空のままなので、後段の native 設定処理には入りません（`engine/src/program/generate.cpp:3842-3847`, `3926`, `5112`）。
2. 値が空でなければ、split shard 一式を名前から列挙します。最初の shard の GGUF metadata で未対応 family を検出した場合は stderr に理由を出して終了コード 2、shard 読込などで例外になった場合もメッセージを出してコード 2 で終了します（`engine/src/program/generate.cpp:5112-5125`, `5151-5154`）。
3. `--ple-gguf` が未指定かつ `--no-ple` でなければ、shard 群から `per_layer_token_embd.weight` を持つファイルを探して PLE 入力に設定します。`--native` 指定中に `--no-ple` を使うか、どの shard にもその tensor がなければエラーとなり、コード 2 で終了します（`engine/src/program/generate.cpp:5127-5134`, `5155-5158`）。
4. native 一括設定として `--stream-token`、`--gr-native-mmvf`、`--native-bf16` / `--native-bf16-extra`、`--native-ple-key`、MoE combine、GDN、router、QSA、indexer、RoPE、PLE postops を有効にします。head の入力が未指定なら `--native` のモデルを使い、dense projection の入力が未指定なら全 shard を使います（`engine/src/program/generate.cpp:5160-5170`）。`--native-flash-attn-short` はこの一括設定では有効になりません。
5. native pack の場合、`--native` は pack が GGUF 形式で保持する tensor の供給元にもなり、token embedding をロードします。`--native` がない、`--spec` が 2 未満、`--keep-canonical` が指定されている、または複数 prompt token に対して prefill chunk がない場合はコード 2 で拒否します（`engine/src/program/generate.cpp:5383-5385`, `5781-5800`）。pack の canonical weights は pack から読み、native 経路に置き換えた tensor はスキップされます（`engine/src/program/generate.cpp:6055-6067`）。

GGUF split 名の5桁 shard 番号が正しく連続していることが必要です。split に該当しないファイル名は単一 shard として扱われ、内容の妥当性は後続の GGUF reader / model loader が判断します（`engine/include/strata/artifact/gguf_split.hpp:23-49`, `engine/src/program/generate.cpp:5116-5124`）。

## 適用条件と副作用

- 通常 root parser は `--native` を `--model` の別名として登録していません。`--model` による family 事前判定は Qwen3.6 分岐で使われ、Qwen3.6 専用 parser には別スコープの `--model` / `--native` が定義されています（`engine/src/program/generate.cpp:3804-3818`; `engine/src/qwen35/q36_engine.cu:5355`）。
- shard 探索と GGUF の読み込みを行い、後段では native projection と head の重みを GPU などの実行領域へロードします。split shard 不足、未対応 family、tensor / geometry 不一致、ロード失敗時には起動が失敗します（`engine/src/program/generate.cpp:5112-5154`, `6060-6067`, `8388-8400`）。
- 起動時に native 機能の選択・モデル読み込みを行います。実行中にこの CLI 値を変更する経路は確認できません。

## 出力とエラー

確認できた失敗経路は stderr への診断と非ゼロ終了です。値なし・引数不足・引数構文エラー、および native pack の組合せ条件違反は終了コード 2。shard 群を列挙できない場合や未対応 family もコード 2 です。後続の pack / tensor / head 読み込み失敗は、該当 loader のエラーを stderr に出し、通常はコード 1 で終了します（`engine/src/program/generate.cpp:3844-3846`, `4268-4273`, `5112-5158`, `5782-5793`, `6060-6065`, `8391-8400`）。

## 根拠

- `engine/src/program/generate.cpp:756-815` — `Options` の既定値と `native_preset`。
- `engine/src/program/generate.cpp:3804-3818` — GGUF architecture による Qwen3.6 parser への事前分岐。
- `engine/src/program/generate.cpp:3842-3847`, `3926` — root parser の値取得。
- `engine/include/strata/artifact/gguf_split.hpp:18-49` — split 名の判定、shard 列挙、欠損 shard エラー。
- `engine/src/program/generate.cpp:5112-5196` — shard 読み込み、PLE 自動選択、native 機能と入力 shard の設定。
- `engine/src/program/generate.cpp:5383-5390`, `5781-5800`, `6055-6067`, `8388-8400` — native pack 条件、embedding / projection / head のロード。
- `engine/src/qwen35/q36_engine.cu:5355` — Qwen3.6 専用 parser での `--model` / `--native` 受理（別 scope）。
