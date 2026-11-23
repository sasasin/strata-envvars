# `strata-split-N --conversation-cache-mib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N = 2 / 3 / 4） |
| オプション | `--conversation-cache-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数。ホストメモリ上に保持する会話スナップショットとチェックポイントの予算 |

## 役割

`strata-split-N` のサーバーモードで、会話キャッシュが保持できるチェックポイントと退避済み会話のホストメモリ予算を指定する。予算内で別会話の状態を保持し、同じ会話の続きが来たときに状態を復元できる。これは同時実行スロット数を指定するものではない。

## 使い方

```sh
# strata-split-2 をサーバーモードで起動し、キャッシュ予算を 4096 MiB にする
strata-split-2 --serve --native MODEL.gguf --mtp RT_DIR --draft-vocab VOCAB.bin --conversation-cache-mib 4096
```

## 値と既定値

- 値は `std::stol` で `long` に変換される。省略時は `0`、すなわち予算なしである（`engine/src/split/tools/sfnx.cpp:65-70, 91`）。
- この引数専用の範囲検査、非負検査、MiB から byte への変換時の上限検査はない。変換時に `std::stol` が例外を出す形式・範囲外の値は起動引数エラーになる。変換後の値は `size_t` にキャストされてから 20 bit 左シフトされるため、負数は有効な「負の予算」として扱われず、意図しない大きな予算になり得る。負数を指定しないこと（`engine/src/split/tools/sfnx.cpp:91, 448-450`）。
- `std::stol` の戻り値だけを使い、変換済み文字列の末尾確認はしていない。そのため整数の後ろに数値でない文字がある場合も、先頭の数値部分が変換される（同 `:91`）。
- 同じオプションを複数回指定した場合は、引数を順に処理して同じフィールドへ代入するため最後の値が残る（同 `:76-92`）。

## 実行時の動作

起動時に `Args::cache_mib` を MiB から byte へ変換し、全セッションで共有する `fnx::ConvCache::budget` に設定する。サーバーは各セッションに同じキャッシュを渡す（`engine/src/split/tools/sfnx.cpp:448-468`）。予算の対象はホストメモリ上の退避済み会話状態とチェックポイントであり、現在実行中の会話の状態や GPU の K/V pool の容量を直接設定する値ではない（`engine/src/split/src/session.hpp:77-90, 109-115`）。

要求処理では予算が 0 より大きく、要求の `ckpt` ヒントが有効なときにチェックポイントを作成する。予算が 0、または要求側が `ckpt=0` の場合、新しい状態の保存・退避を抑止する（`engine/src/split/src/session.cpp:155-163, 192-194, 228-252`）。一方、キャッシュ上限を超えると、退避済み会話を最終使用時刻が古い順に破棄し、それでも超過する場合は現在の会話に属するチェックポイントを古いものから削る（同 `:351-362`）。保存予算が不足する会話の退避は行われず、予算値そのものに応じてメモリを起動時に一括確保する実装ではない（同 `:309-323`）。

`--batch` で複数スロットを使う場合もキャッシュは共有される。起動時に stdout の `INFO` 行へ `conversation_cache_mib=<値>` が含まれ、`--batch` が 1 より大きい場合はスロット数も同じ行に出る（`engine/src/split/tools/sfnx.cpp:448-468, 1155-1157`）。

## 適用条件と副作用

- 対象は索引上の `strata-split` ツール、すなわち `strata-split-N` の root parser である。`--serve` が必須で、モデルとドラフト関連引数も別途必要になる（`engine/src/split/tools/sfnx.cpp:4-5, 73-117`）。
- `strata-split` は opt-in のビルド対象で、CMake 設定では既定で無効、Linux の CUDA または HIP 向けとされる。実行可能性は当該 checkout のビルド条件に依存する（`engine/src/split/CMakeLists.txt:1-7`）。
- キャッシュの保持と復元はホストメモリのスナップショット保存を伴う。`0` では予算に基づく新規チェックポイント作成や会話退避を止める。`--batch` はスロット数、キャッシュ予算とは別の設定である。

## 出力とエラー

- 値が欠けると `--conversation-cache-mib needs a value` が stderr に出て、引数解析で終了コード `2` になる。`std::stol` が例外を出す入力も同じ引数解析の catch に入り、`sfnx: <例外内容>` を stderr に出して `2` を返す（`engine/src/split/tools/sfnx.cpp:76-81, 1107-1115`）。
- 値自体の負数・MiB 上限を拒否する専用エラー経路は確認できない。モデル読み込み後の処理で例外が発生した場合は別経路となり、`ERR <理由>` を stdout、`sfnx: failed: <理由>` を stderr に出して終了コード `1` で終了する（同 `:1094-1103, 1117-1136`）。
- 正常な初期化後は stdout の `INFO` 行に設定値が出る（同 `:1155-1157`）。

## 根拠

- `engine/src/split/tools/sfnx.cpp:65-70, 73-117` — 引数フィールド、parser、既定値、`--serve` 必須条件、引数エラー処理。
- `engine/src/split/tools/sfnx.cpp:448-468` — MiB から byte への変換、共有キャッシュ、全スロットへの適用。
- `engine/src/split/tools/sfnx.cpp:1094-1115, 1155-1157` — 実行時失敗経路、引数解析失敗時の終了、起動時 `INFO` 出力。
- `engine/src/split/src/session.hpp:77-90, 109-115` — キャッシュ構造と予算の対象。
- `engine/src/split/src/session.cpp:155-163, 192-194, 228-252` — 要求ごとのキャッシュ有効条件、会話再利用とチェックポイント作成。
- `engine/src/split/src/session.cpp:309-362` — 会話退避、予算超過時の LRU 破棄とチェックポイント削減。
- `engine/src/split/CMakeLists.txt:1-7` — split engine のビルド条件。

値の異常入力について、実際の CLI を用いた確認は行っていない。記述は parser と利用箇所の静的な追跡に基づく。
