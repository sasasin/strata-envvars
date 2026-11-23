# `strata-split-N --native`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N = 2/3/4） |
| オプション | `--native` |
| 別名 | なし |
| 値 | 必須。モデル GGUF の先頭 shard のパス |

## 役割

推論対象の GGUF モデルを指定する。値は `Args.gguf` に入り、起動時に `fnx::Model` へ渡される。モデル reader は指定された GGUF を読み取り、ファイル名が `-00001-of-000NN.gguf` 形式なら shard 1 から NN までを順に開く。単一ファイル名または shard 命名規則に一致しない名前は、そのファイルだけを開く。どちらも読取専用でマップされる。受け付けるモデル構造はビルド種別で異なり、通常の split build は Flash-Next、`FNX_27B` build は Qwen3.8-27B のメタデータ形状を要求する。`--native` 自体はモデルを変換・書き換えないが、reader は対応外の小型テンソルをロード時にメモリ内で変換する場合がある。  
根拠: `engine/src/split/tools/sfnx.cpp:65-71,82-84,1123-1125`; `engine/src/split/src/gguf.cpp:119-133,212-247`; `engine/src/split/src/model.cpp:1295-1328`。

## 使い方

```bash
# 3 GPU 用ビルドで shard 1 をモデルとして起動する例（パスは環境に合わせる）
strata-split-3 --serve --native /models/model-00001-of-00003.gguf --mtp /models/mtp
```

`--serve` が必須で、既定の draft 方式 `mtp` では `--mtp DIR` も必要。`dflash2` 方式では `--draft dflash2 --draft-model PACK` と `--draft-vocab FILE`（または `--mtp DIR` 内の `draft_vocab.bin`）が必要となる。  
根拠: `engine/src/split/tools/sfnx.cpp:67-70,82-90,107-115`。

## 値と既定値

- `--native` は直後の argv 文字列を1つ値として取得する。コマンド末尾などで argv が尽きた場合は `--native needs a value` 例外になる。次の文字列が別オプションに見えても値として消費する。値のファイル名・存在・形式検証は parser ではなくモデル読込時に行われる（`engine/src/split/tools/sfnx.cpp:76-84,1107-1115`）。
- 既定値はない。通常の `mtp` draft モードでは値が空の場合も `--native and --mtp are required` で起動を拒否する。`dflash2` でも空の値は必須項目チェックで拒否される（`engine/src/split/tools/sfnx.cpp:107-115`）。
- 同じオプションを複数回指定した場合、parser はその都度 `a.gguf` に代入するため最後の値が残る（`engine/src/split/tools/sfnx.cpp:76-84`）。
- shard 自動探索は、値の末尾が `-` + 5桁番号 + `-of-` + 5桁総数 + `.gguf` のときだけ行われ、番号1から総数までのファイル名を組み立てて読み込む。形式に合わない名前から不足 shard を探索する動作はない（`engine/src/split/src/gguf.cpp:119-132`）。

## 実行時の動作

1. `--native` の値を `Args.gguf` に保存し、parse 完了後に `m.emplace(a.gguf.c_str())` でモデルを構築する（`engine/src/split/tools/sfnx.cpp:65-84,1107-1125`）。
2. GGUF reader は指定ファイル（および認識した分割 shard）を開き、読取専用マッピングを作ってテンソルを索引する（`engine/src/split/src/gguf.cpp:119-133,212-250`）。
3. `Model` は可視 GPU 数・カード構成と対応する routed expert の型を確認し、ビルドに応じたモデル形状とメタデータを検査する。値が正しいパスでも、これらの条件を満たさなければモデル生成が失敗する（`engine/src/split/src/model.cpp:1284-1348`）。
4. 読み込んだモデルは選択した draft 実装と engine に渡される（`engine/src/split/tools/sfnx.cpp:1123-1133`）。

## 適用条件と副作用

- `strata-split-N` の `N` はビルド時のカード数に対応する。モデル構築では実際の可視 GPU 数が `NCARD` と一致することも確認されるため、`--native` のパスだけでは起動可否は決まらない（`engine/src/split/src/model.cpp:1295-1308`）。
- 分割 GGUF は先頭 shard を指定する。reader はファイル名に一致する shard 名を組み立てて順番に開くが、各 shard の存在、GGUF magic、テンソル内容などに問題があればエラーになる（`engine/src/split/src/gguf.cpp:119-132,212-250`）。
- GGUF は `O_RDONLY` と `PROT_READ` でマップされる（Windows では `GENERIC_READ` / `PAGE_READONLY`）。reader が対象ファイルへ書き込む処理は確認できない（`engine/src/split/src/gguf.hpp:1-3`; `engine/src/split/src/gguf.cpp:212-247`）。
- ある種の IQ / Q2_0 routed expert を含む場合、対応しない小型テンソルをメモリ内で Q8_0 / F32 に変換し、routed expert のデータ型は維持する。変換が発生すると stderr に変換件数を出力する（`engine/src/split/src/gguf.cpp:135-147,154-165,194-197`）。
- routed expert の型が split engine の対応リスト外なら `the all-cards split engine does not read this model's routed experts ...; use the normal layer split` で拒否される（`engine/src/split/src/model.cpp:1284-1292`）。

## 出力とエラー

- parser の必須値不足、`--serve` 不足、必須のモデル / draft 設定不足、未知の引数などは `sfnx: <理由>` を stderr に出し、終了コード `2` で終了する（`engine/src/split/tools/sfnx.cpp:76-80,105-115,1107-1115`）。
- ファイルを開けない場合は `gguf: cannot open <path>`、マップ失敗は `gguf: mmap failed for <path>`（Windows は対応する Win32 API 名を含むエラー）となる。モデル構築中の例外は stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出して `_Exit(1)` する（`engine/src/split/src/gguf.cpp:212-250`; `engine/src/split/tools/sfnx.cpp:1094-1102,1123-1135`）。
- `--native` 固有の通常時 stdout/stderr メッセージや、パス文字列自体への独立した validation は確認できなかった。実際の起動ではモデルの読込・構造検査のログが出る。

## 根拠

- `engine/src/split/tools/sfnx.cpp:65-84` — `Args.gguf`、値取得関数、および `--native` parser。
- `engine/src/split/tools/sfnx.cpp:107-117` — `--serve`・モデル・draft 要件と parse 時の失敗経路。
- `engine/src/split/tools/sfnx.cpp:1094-1115,1117-1135` — parse エラー時の終了コード、モデルへの受け渡し、ロード例外の出力。
- `engine/src/split/src/gguf.hpp:1-3,48-51` — reader の読取専用マッピング方針と split shard の入口。
- `engine/src/split/src/gguf.cpp:119-133,212-250` — shard 名の認識、ファイルの read-only open/map、GGUF 検査。
- `engine/src/split/src/gguf.cpp:135-197` — ロード時のメモリ内変換と通知。
- `engine/src/split/src/model.cpp:1284-1348` — routed expert 型・カード数・モデル形状・メタデータの検証。
