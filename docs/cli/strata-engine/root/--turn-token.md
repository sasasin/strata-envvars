# `--turn-token`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`--serve` で常駐サーバーモード） |
| オプション | `--turn-token` |
| 別名 | なし |
| 値 | token ID を表す整数。値を1つ取る。 |

## 役割

`--serve` の会話 prompt を走査するとき、チャット turn の開始を表す token ID を指定する。エンジンはこの token の位置を会話 checkpoint の境界として認識し、後続リクエストで一致する履歴を再利用できるようにする。既定値 `248045` は `<|im_start|>` に対応する（`engine/src/program/generate.cpp:1131-1133,1335`）。

## 使い方

```sh
# 通常の ChatML token ID を使って serve を起動する（モデル指定などは環境に合わせる）
strata --serve --prompt-cache 6 --turn-token 248045
```

## 値と既定値

- 値は `std::atoll` で `int64_t` に変換され、既定値は `248045`。短縮別名はない（`engine/src/program/generate.cpp:1133,4115`）。SYCL 実装も同じ既定値・変換を使う（`engine/sycl/src/program/generate.cpp:750,2093`）。
- 値の範囲、完全な数値文字列であること、または tokenizer 語彙内の ID であることを検証する処理は、このオプションの parser にはない。`std::atoll` による変換後の値がそのまま保存される（`engine/src/program/generate.cpp:4115`）。
- 値が欠けている場合は parser の `next()` が `--turn-token needs a value` を stderr に出して終了コード 2 で終了する（`engine/src/program/generate.cpp:3844-3847`）。
- 負数も parser では拒否されないが、turn 境界探索の条件 `o.turn_token >= 0` を満たさなくなるため、checkpoint 境界として使われない（`engine/src/program/generate.cpp:21465-21467,21485-21489`）。

## 実行時の動作

効果があるのは `--serve` で、かつ `--prompt-cache` が 0 より大きい場合である。prompt の現在の再開位置 `resume` より後ろを末尾から検索し、最後に現れる指定 token の位置を `turn_at` とする。その位置までを会話履歴の checkpoint として区切り、同じ token 列・画像を持つ既存 checkpoint の再利用に使う。token が見つからない場合、または `--prompt-cache 0` の場合、この turn checkpoint は設定されない（`engine/src/program/generate.cpp:21460-21467,21483-21489`）。

token ID は prompt に含まれる token ID と比較されるだけで、文字列から token への変換や生成 token の制御はしない。`--tail-role-token` を指定すると、直前の turn がその role token で始まる場合に checkpoint 位置をさらに一つ前の turn に移す（`engine/src/program/generate.cpp:21468-21475`）。初回 prompt のシステム部分 checkpoint（`--prompt-cache-root`）および `STRATA_CACHE_MESSAGE_BOUNDARY` による追加 checkpoint も同じ turn token を境界判定に使う（`engine/src/program/generate.cpp:21477-21498`、`engine/include/strata/program/message_boundary.hpp:9-17`）。

## 適用条件と副作用

- checkpoint の探索・保持はサーバープロセス内の会話状態に対する処理であり、このオプション自体はファイルやネットワークへ書き込まない。checkpoint は `--prompt-cache` によるメモリ上の保持に属する（既定は6件、0で無効。`engine/src/program/generate.cpp:1086-1089,1293-1295`）。
- token ID は利用モデルと prompt 形式に合う必要がある。異なる ID を指定しても parser は警告せず、prompt 中の一致がなければ境界 checkpoint は見つからない。checkpoint を検索・再利用する処理に限定しており、誤った ID による生成内容への影響はソースから確認できない。
- terminal server の Python 実装は `TURN_ID = 248045` を独自に定義している（`terminal/serve/server.py:2494-2499`）。エンジンへ非既定値を渡す構成でこのサーバー側処理も使う場合、両者が同じ ID を使うかは別途確認が必要である。
- 通常実装と SYCL 実装の双方に parser と checkpoint 探索があるが、ここではソースを読み、実行による backend 差の確認はしていない（`engine/sycl/src/program/generate.cpp:750,2093,11600-11637`）。

## 出力とエラー

この値専用の数値 validation error や警告は確認できない。値を省略したときは上記の parser error となる。未知のオプションは `unknown argument` と usage を stderr に出し、終了コード 2 で終了するが、`--turn-token` 自体は現行 parser に登録されている（`engine/src/program/generate.cpp:4115,4268-4273`）。

## 根拠

- `engine/src/program/generate.cpp:1131-1133,1335` — 既定値と help 上の説明。
- `engine/src/program/generate.cpp:3844-3847,4115` — 必須値の取得、変換、保存。
- `engine/src/program/generate.cpp:21460-21498` — serve 内での最後の turn token 探索、prompt-cache 条件、root/message checkpoint との相互作用。
- `engine/include/strata/program/message_boundary.hpp:9-17` — 追加 message checkpoint の境界条件。
- `engine/src/program/generate.cpp:4268-4273` — 未知引数の失敗経路。
- `engine/sycl/src/program/generate.cpp:750,912,2093,11600-11637` — SYCL parser、help、checkpoint 探索。
- `terminal/serve/server.py:2494-2499` — terminal server が持つ既定 turn ID。

