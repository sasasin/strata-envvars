# `strata-split-N --lookup`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の作業ツリーは `main...origin/main` で clean。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N は 2 / 3 / 4 のカード数） |
| オプション | `--lookup` |
| 別名 | なし |
| 値 | 整数。0〜15 |

## 役割

会話コンテキスト内の過去の 3-token 並びを探し、続きの token を speculative draft として使う n-gram lookup の最大長を指定します。これは draft layer の MTP chain 長 (`--spec`) とは別の設定です。

## 使い方

```sh
strata-split-2 --serve --native MODEL.gguf --mtp DRAFT_DIR --draft-vocab VOCAB.bin --lookup 8
```

`strata-split-N` は server/front end の line protocol で起動される engine です。通常は `strata launch --split-engine ...` が起動を選択します。上の例は engine の引数構文を示すもので、モデル等のパスは実際のファイルに置き換えてください。

## 値と既定値

省略時は `15` です。parser は次の argv 要素を `std::stoi` で整数化し、値が無い場合は `--lookup needs a value` を送出します。`Session` と `BatchDecoder` の検証範囲は `0..MAXT-1`、`MAXT` は 16 なので受理範囲は `0..15` です。`0` は lookup draft を無効にします。負数および 16 以上は範囲エラーです。

## 実行時の動作

各 session に `--lookup` の値が渡され、生成中に speculative decoding が有効な場合、直近のコンテキスト末尾 3 token と一致する最も新しい過去の出現箇所を後方検索します。その出現箇所の次 token が draft layer の最初の予測 `d1` と一致する場合に限り、続く token 列を lookup drafts として採用します。続きがある場合は一致が続く長さに応じて最大指定値まで取り出し、画像 token 以降は候補から除きます。候補が無い場合は通常の MTP chain へ進みます。したがって値は上限であり、各 round で常にその個数が使われるわけではありません。

複数 slot の batch decoder も同じ値を受け取ります。ただし batch decoding の有効化は `FNX_BATCH_DRAFTS` によって別に制御されます。`--lookup` 自体は batch mode を有効化しません。

## 適用条件と副作用

lookup は `--lookup 0`、コンテキスト長が 3 以下、過去に一致する 3-token 並びがない場合、または一致箇所の続きが現在の draft layer の `d1` と合わない場合には draft を返しません。生成要求が speculative decoding を使わない場合も lookup は行われません。設定変更による外部ファイルの書き込みや環境変数の変更はありません。

## 出力とエラー

起動成功時、stderr の `sfnx: loaded ... lookup <値> ...` 行に採用値が表示されます。lookup が使われた round 数は生成終了時の stderr 統計に `(<数> with lookup drafts)` として出ます。

値の欠落や `std::stoi` で整数化できない値は parser の例外経路で `sfnx: <理由>` を stderr に出し、終了コード 2 になります。範囲外の整数は session / batch decoder 初期化時に範囲エラーになります。モデル等のロード後に初期化エラーとなった場合は `ERR <理由>` を stdout、`sfnx: failed: <理由>` を stderr に出して終了コード 1 です。

## 根拠

- parser、既定値、必須値・範囲外 parser 例外の入口: `src/split/tools/sfnx.cpp:65-104`
- parse 失敗の stderr と終了コード 2: `src/split/tools/sfnx.cpp:1040-1048`
- Session への値の伝達と batch decoder 生成条件: `src/split/tools/sfnx.cpp:435-445`
- `MAXT=16` と `0..15` の validation: `src/split/src/model.hpp:43`, `src/split/src/session.cpp:140-145`, `src/split/src/batch.cpp:64-69`
- lookup 一致条件、続きの長さ、画像 token の除外: `src/split/src/session.cpp:16-17,373-394`; session decode からの呼び出しと MTP fallback: `src/split/src/session.cpp:562-579`
- batch decoder の lookup 利用: `src/split/src/batch.cpp:259-280,338-365`
- 起動時の値表示、エラー経路、lookup round の統計: `src/split/tools/sfnx.cpp:848-852,1027-1035,1065-1083`
- tool の build 条件と実行ファイル名: `src/split/CMakeLists.txt:20-30,92-97`
