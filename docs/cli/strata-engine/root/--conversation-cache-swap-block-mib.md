# `strata`（エンジン引数）`--conversation-cache-swap-block-mib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`--serve` と併用） |
| オプション | `--conversation-cache-swap-block-mib` |
| 別名 | なし |
| 値 | 10進整数 `0`〜`256`。値は MiB 単位 |

## 役割

`--serve` で会話キャッシュから別の会話へ切り替えるとき、条件が合えば、復元対象の会話と現在の会話の host K/V バッファを指定サイズのブロックで交換します。交換時に復元対象のバッファを現在の会話用に再利用し、現在の会話をキャッシュへ退避します。`0`（既定値）ではこの交換経路を無効にし、従来の退避・復元経路を使います。

## 使い方

```sh
# serve モードで host K/V の交換ブロックを 17 MiB に設定する
strata --serve --conversation-cache-swap-block-mib 17 <モデルなどの通常引数>
```

## 値と既定値

- 値は空でない ASCII 十進数字のみです。`0`〜`256` の整数を受理し、`0` は無効化、`1`〜`256` は交換用ブロックの大きさ（MiB）です。既定値は `0` です（`engine/src/program/generate.cpp:1090`、`engine/include/strata/core/conversation_cache.hpp:277-285`）。
- `+1`、`-1`、小数、空文字、範囲外の値は拒否されます。オプションを重ねて指定すると parser は順に値を代入し、後の有効な指定が残ります（`engine/src/program/generate.cpp:3837-3842,4068-4077`）。
- 値を省略した場合、または次の引数が `-h` / `--...` の場合は値不足として終了コード `2` になります。形式・範囲が不正な場合もエラーメッセージを stderr に出して `2` で終了します（`engine/src/program/generate.cpp:3839-3841,4068-4076`）。

## 実行時の動作

parser は値を `Options::conversation_cache_swap_block_mib` に保存します。serve リクエスト処理では MiB をバイトへ変換し、0 より大きい場合にのみ会話交換を試みます（`engine/src/program/generate.cpp:1090,4068-4077,19649-19658`、`engine/include/strata/core/conversation_cache.hpp:288-290`）。この値を読む使用箇所は serve のリクエスト処理です。

交換を試すには、復元対象の会話が SSD 由来でなく、保存済み live state があり、トークン数がその live state と一致することに加え、borrow / keep-branch / reply-replaced の各条件に該当せず、現在の会話を退避でき、再利用可能な同一 K/V がなく、stage 分割・batch・KVG が無効である必要があります。条件を満たさなければ交換処理に入らず、通常の park / restore 経路へ進みます（`engine/src/program/generate.cpp:19651-19658,19752-19755,19882-19890`）。

交換前には snapshot と K/V の互換性を検査し、GPU 処理を同期してから、メモリ空き容量と会話キャッシュ容量を確認します。RAM 判定に通らなければ交換を見送り、通常経路に戻ります。交換が成立した場合は、復元対象の host K/V バッファをブロック単位で現在の K/V と入れ替え、device index を転送して residency を更新し、退避した会話をキャッシュに登録します（`engine/src/program/generate.cpp:19665-19699,19705-19719`、`engine/src/core/conversation_state.cpp:779-826,829-897`、`engine/src/core/conversation_snapshot.cpp:959-995`）。

## 適用条件と副作用

- helper は HIP、特定の HIP gfx906、Metal のビルドでは host mapping が未検証として交換を拒否します。また、非同期 park/checkpoint、snapshot verification/full capture、checkpoint reread の関連環境変数が設定されている場合、pending な画像や stage 分割画像、device-tag 付きの状態がある場合にも交換準備をしません（`engine/src/core/conversation_snapshot.cpp:833-860`、`engine/src/core/conversation_state.cpp:779-792`）。このときエラーで serve を止めるのではなく、通常経路へフォールバックします。
- RAM 不足時は idle pool の縮小や空き heap の解放を試みます。会話交換のためのメモリ確保ができない場合は交換を見送り、通常経路を続けます（`engine/src/program/generate.cpp:19675-19696`）。
- host K/V の転送・同期に失敗した場合は `ERR exchanging parked conversation: ...` を stdout に出し、serve を終了コード `1` で終えます。交換後に割り当てで失敗した場合も fatal error になります。一方、交換書き込み開始前の資源不足などは `unavailable` として通常経路へ戻ります（`engine/src/core/conversation_state.cpp:833-897`、`engine/src/program/generate.cpp:19670-19704,19722-19728`）。
- 成功時は stderr に `parked` または `skipped` と交換した token 数・キャッシュ状態を記録します。メモリ pool や heap の解放が試される場合があり、CUDA device 同期も行われます（`engine/src/program/generate.cpp:19669-19689,19705-19719`）。

## 根拠

- `engine/src/program/generate.cpp:1090,1295,4064-4077` — 既定値、help 表示、`--serve` およびオプション parser、入力エラー。
- `engine/src/program/generate.cpp:19649-19728,19752-19755,19882-19890` — 使用箇所、交換適用条件、RAM 判定、出力・エラーと通常 park / restore への経路。
- `engine/include/strata/core/conversation_cache.hpp:277-290` — 既定値、値の構文・範囲検証、MiB から byte への変換。
- `engine/src/core/conversation_state.cpp:779-897` — snapshot 準備、互換性確認、交換結果（成功・利用不可・転送失敗）の扱い。
- `engine/src/core/conversation_snapshot.cpp:833-897,959-995` — backend 条件、host K/V バッファ交換、device index 更新。
- `docs/DETAILS.md:836` — 利用者向け説明との照合。既存 retained K/V prefix が現在の会話と一致する場合は通常 park / restore を使う旨を確認。実装上の適用条件は上記ソースを根拠とした。
