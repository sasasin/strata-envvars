# `--prompt-cache-root`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--prompt-cache-root` |
| 別名 | なし |
| 値 | 先頭から保存する system prompt の最低 token 数。整数として読み取られ、負数は 0 に補正される |

## 役割

`--serve` の prompt cache で、同一クライアントの会話間に共有される system prompt の終端を root checkpoint として保存する最低長を指定します。初回の prompt 読み込みで最初の turn 境界がこの長さ以上なら、その境界にも checkpoint を作ります。既定値は 2048 token、`0` は root checkpoint を無効にします。

## 使い方

```sh
strata --serve --native /path/to/model.gguf --prompt-cache-root 4096
```

エンジン引数として `--serve` とモデル指定などと一緒に渡します。値は tokenizer の token 数であり、文字数や byte 数ではありません。

## 値と既定値

- 値を省略した場合は `2048`。
- 値は `std::atoll` で読み取られ、`std::max(0, 値)` により負数は `0` になります。従って `-1` はエラーではなく無効化と同じ値です。
- 数値でない文字列は `atoll` の変換結果 `0` となり、root checkpoint は無効になります。小数の小数部は整数変換で扱われます。
- parser は値の明示的な上限や形式エラーを設けていません。引数そのものがない場合は stderr に `--prompt-cache-root needs a value` を出し、終了コード `2` で終了します。
- 同じオプションを複数回指定したときは parser が順に代入するため、最後に処理された値が残ります。

## 実行時の動作

通常の会話 checkpoint は prompt 内の最後の turn token を境界に使います。これに加えて root checkpoint は、prompt cache が有効（`--prompt-cache` が 1 以上）、turn token が有効、root 閾値が 1 以上で、処理が token 0 から始まるか token 0 から再開した場合に限って探索されます。最後の turn 境界より前にある最初の turn token を調べ、その token index が閾値以上なら root の境界にします。したがって閾値 `N` は system prompt の token 数に対する下限であり、最初の turn token の index が `N` 以上である必要があります。

この境界は通常の turn boundary とともに prompt の分割点に追加され、読み込みがそこへ到達すると会話 checkpoint 保存処理を呼びます。後続の同じ共有 prefix を含む request は cache 内の prefix checkpoint から再開できます。root は cache の保持方針で pinned 扱いされますが、`--prompt-cache` の枠数が 2 未満では root を独立保持できず、従来どおり最古 checkpoint が eviction 対象になります。

この設定は cache 自体を有効化しません。`--prompt-cache 0` なら root の追加保存もありません。`--turn-token` が負数なら境界検出が無効です。`ckpt=0` の request でも root 境界の探索対象にはなりますが、通常の最終 turn checkpoint は抑止されます。

## 適用条件と副作用

- `--serve` の request prompt 経路で作用します。対話的な単発生成など、server の prompt checkpoint 処理を通らない利用では、この閾値による共有 root 保存は発生しません。
- 保存されるのは通常の conversation checkpoint（推論状態の snapshot）です。ファイルへの書き出しをこのオプションが直接行うわけではありません。
- root が保持できれば、その後の同じ system prompt を共有する会話で既存 prefix の再読込を避けられます。checkpoint は cache の容量を消費します。
- 画像を含む request では画像一致など既存の cache 再利用判定も適用されます。閾値条件だけで異なる prompt の checkpoint が再利用されるわけではありません。
- ソース上の説明には、小さい system prompt は再読込の方が安価という設計理由がありますが、実行時間はモデル・環境に依存し、ここでは性能を保証しません。

## 出力とエラー

値の不正を理由にした専用の parser validation はありません。prompt 処理中の checkpoint 保存に失敗すると stdout に `ERR saving a conversation checkpoint failed...` を出して終了コード `1` で戻ります。root checkpoint を追加できるケース自体に固有の警告出力は、確認した経路にはありません。

## 根拠

- `src/program/generate.cpp:751-753` — `--serve` 向け root checkpoint の説明と既定値 `2048`。
- `src/program/generate.cpp:2416-2420` — 値のない引数に対する共通 parser の stderr 診断と終了コード `2`。
- `src/program/generate.cpp:2663-2667` — parser 定義。`--prompt-cache-root` は整数変換後に 0 以上へ clamp。
- `src/program/generate.cpp:13976-14006` — turn boundary と root の探索条件、閾値比較、初回 token 0 読み込み条件。
- `src/program/generate.cpp:14037-14042,14123-14130` — root boundary を読み込み分割点へ加え、到達時に checkpoint を保存する処理と失敗出力。
- `include/strata/program/conv_cache.hpp:12-24,32-40` — root checkpoint の保持目的と、cache 容量 2 未満の場合の eviction 方針。
- `docs/cli/README.md:1128-1134,1263-1266` — 対象が Terminal CLI ではなく推論エンジンの root option scope であり、この option が索引に掲載されていること。

調査範囲は上記 commit のソースと作業ツリーにある CLI 索引です。同一 revision のビルド済み CLI help や Release 配布物は確認していません。parser と実使用箇所は `src/program/generate.cpp` で照合しました。
