# `--check-logits`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--check-logits` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

`--stream-token` 使用時に、各トークン位置で語彙全体の logits を GPU からホストへコピーし、非有限値（NaN または ±Inf）がないか検査します。通常の token-by-token decode で logits の異常を検出する診断用オプションです。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --stream-token --check-logits
```

トークン ID 列は例です。`strata generate` の基本構文は `src/program/generate.cpp:806-812` にあります。

## 値と既定値

- 値・別名はなく、指定すると内部フラグ `check_logits` を `true` にします。既定値は `false` です（`src/program/generate.cpp:438-439,2484-2485`）。
- parser にこのフラグ固有の値検証はありません。同じフラグを複数回指定しても `true` を再設定するだけです。値を続けて書くと、その値は次の引数として処理され、未知引数エラーになります（`src/program/generate.cpp:2416-2424,2484-2485,2787-2792`）。

## 実行時の動作

- 1 トークンずつ処理する decode ループでは、`--stream-token` がない場合は `read_logits` が常に真で、logits 全体の読み戻しと有限値検査がすでに行われます。そのためこの条件で `--check-logits` を付けても検査範囲は変わりません（`src/program/generate.cpp:15994-16008`）。
- `--stream-token` がある場合、通常は logits を読み戻しません。このオプションを指定すると `read_logits` が真になり、各位置の `n_vocab` 個の float（`n_vocab * 4` bytes）を device-to-host コピーし、stream を同期してから全要素を `std::isfinite` で検査します（`src/program/generate.cpp:15996-16008`）。
- `--native` はこの parser の経路で `stream_token` を有効にするため、通常の token-by-token decode では `--check-logits` が読み戻し・検査を有効にします（`src/program/generate.cpp:3232-3267`）。
- `--dump-logits` と併用すると、出力対象に選ばれた位置では `emit_logits` によって `read_logits` が真になり、フラグなしでもその位置の logits が読み戻されます。dump 選択位置以外も毎回検査するには `--check-logits` が必要です（`src/program/generate.cpp:15994-16008`）。

## 適用条件と副作用

- `--stream-token` と組み合わせると、毎位置で語彙全体をホストへ転送して同期し、全 logits を走査します。出力・失敗経路以外に、転送量や同期コストの定量値はこのソースからは分かりません。
- ネイティブ pack の speculative verify 経路は通常ループから抜けた後に別処理へ進みます。`check_logits` の参照は通常ループ内に限られるため、verify window の logits 検査をこのオプションが行うとは確認できません（`src/program/generate.cpp:15874-15878,15994-16008,16097-16129`）。
- Qwen3.5 系モデルは、モデル family 判定後に `strata::qwen35::run` へ分岐し、このファイルの通常 parser を通りません（`src/program/generate.cpp:2393-2407`）。この別経路での同オプションの扱いは、本オプションの parser・利用箇所からは確認できません。

## 出力とエラー

- 読み戻しまたは stream 同期に失敗すると、stderr に `strata generate: reading the logits back failed` を出して終了コード `1` で戻ります（`src/program/generate.cpp:15996-16002`）。
- 非有限値が1つ以上あると、stderr に非有限 logits 数、語彙数、位置を出して終了コード `1` で戻ります（`src/program/generate.cpp:16003-16008`）。すべて有限なら、このオプション固有の成功メッセージはありません。
- 未知引数（フラグの後ろに余計な値を置いた場合を含む）は stderr に `unknown argument` と usage を出し、終了コード `2` になります（`src/program/generate.cpp:2787-2792`）。

## 根拠

- `src/program/generate.cpp:438-439` — `stream_token` と `check_logits` の初期値。
- `src/program/generate.cpp:806-841` — `strata generate` の usage と `--check-logits` の説明。
- `src/program/generate.cpp:2416-2424,2484-2485` — 引数 parser。
- `src/program/generate.cpp:3232-3267` — `--native` による `stream_token` の有効化。
- `src/program/generate.cpp:15874-15878,15994-16008` — 通常 decode と logits 読み戻し・有限値検査。
- `src/program/generate.cpp:16097-16129` — 通常ループ後の speculative verify 経路。
- `src/program/generate.cpp:2393-2407` — Qwen3.5 系の別実装への分岐。
- `src/program/generate.cpp:2787-2792` — 未知引数の失敗経路。
