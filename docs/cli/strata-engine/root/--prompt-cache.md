# `strata`（推論エンジン）`--prompt-cache`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`--serve` と併用） |
| オプション | `--prompt-cache` |
| 別名 | なし |
| 値 | 非負の checkpoint 数。0 は無効化 |

## 役割

`--serve` が複数の会話要求を受け付けるとき、prompt の途中や会話ターン境界で保存しておく状態 checkpoint の上限を指定します。後続要求の token prefix が保存済み checkpoint と一致すれば、その状態から prompt の残りを処理します。既定値は6で、ソースのヘルプは1 checkpoint あたり約118 MBのRAMと説明しています（実際の状態量はモデル構成に依存します）。

## 使い方

```sh
# 会話 checkpoint を最大6件保持して、serve 要求を stdin から受け付ける
strata --pack pack/full --serve --prompt-cache 6

# checkpoint を無効化し、各要求の prompt を先頭から読む
strata --pack pack/full --serve --prompt-cache 0
```

## 値と既定値

- 値は `atoi` で整数変換され、結果を `max(0, 値)` に通します。負数は0になります。未指定時は6です。parser は厳密な十進数形式・範囲検証をしておらず、不正形式を明示的な validation error として拒否しません。`--prompt-cache` の値を省略すると、共通の引数取得処理が `needs a value` を stderr に出して終了コード2で終了します。
- 同じオプションを複数回指定した場合、parser は出現ごとに値を代入するため、最後の指定値が残ります。
- 0では checkpoint を作らず、各 prompt を先頭から読み直します。通常生成（`--serve` なし）には checkpoint の処理経路がありません。

## 実行時の動作

`--serve` の checkpoint 管理処理では、prompt token prefix と対応するモデル状態を checkpoint として保存し、保持数が指定上限を超えると eviction policy で削除します。既定は最近使われた checkpoint を基準に選び、[`--prompt-cache-spread`](--prompt-cache-spread.md) を指定した場合は会話末尾から分散する選択に切り替わります。後続要求では live session と checkpoint のうち要求 prompt に一致する最長 prefix を選択して再利用します。ターン境界の checkpoint に加え、[`--prompt-cache-every`](--prompt-cache-every.md) が正なら再読込した prompt token 数に応じて途中にも保存します。

この値は、独立した会話状態をRAMに退避する `--conversation-cache-mib` と別の上限です。ただし `--prompt-cache 0` では `ConversationCache` の容量も0になり、独立会話の駐車も無効になります。`--conversation-cache-mib` が正の値なら、その組み合わせを警告します。また session file の保存・復元コマンドも `--prompt-cache > 0` を必要とします。

## 適用条件と副作用

- 主な効果は `--serve` の要求間で現れます。上限を増やすと複数の checkpoint 状態を保持できる一方、ホストRAMを使います。実際の保存はGPU状態の同期と状態コピーを伴います。
- `--prompt-cache-every` は途中 checkpoint の間隔、`--prompt-cache-tail` は単一GPUで既存 chunk 境界に追加する末尾 checkpoint を制御します。`--prompt-cache-tail` は本オプションと `--prompt-cache-every > 0` が必要です。
- session file の保存・復元は `--layer-split`、`--peer-device`、`--batch` と併用できず、`--prompt-cache` が0以下の場合も要求を拒否します。
- checkpoint の状態コピーに回復可能なメモリ不足が起きた場合、その checkpoint を飛ばして要求を続けます。GPU同期の失敗など回復不能な checkpoint 失敗は要求を失敗させます。

## 出力とエラー

- `--serve --conversation-cache-mib N`（N > 0）と `--prompt-cache 0` の組み合わせでは、stderr に会話 cache が無効である旨の warning が出ます。
- 回復可能な状態コピー失敗では、stderr に checkpoint を skip して要求を続ける旨を出します。回復不能な失敗では要求処理が `saving a conversation checkpoint failed` を返し、`--serve` のエラー経路へ進みます。
- session file の保存・復元時に0を指定していると、`session files need --prompt-cache > 0` の理由でその要求を拒否します。

## 根拠

- `engine/src/program/generate.cpp:1086-1089` — 既定値6と checkpoint 状態の説明。
- `engine/src/program/generate.cpp:1293-1295` — `--serve` 専用、既定値、概算RAM、0の意味を示すヘルプ。
- `engine/src/program/generate.cpp:3844-3847,4072` — 値取得、欠落時の終了コード、`atoi` と0未満の補正。
- `engine/src/program/generate.cpp:4761-4763,13881-13883` — 0指定時の会話 cache warning と容量0での初期化。
- `engine/src/program/generate.cpp:14595-14607,14723-14753` — checkpoint 保存と保持上限超過時の eviction。
- `engine/src/program/generate.cpp:14820-14852` — 周期・末尾 checkpoint の適用条件と失敗時の継続／失敗経路。
- `engine/src/program/generate.cpp:19281-19290,20086-20112` — prefix が一致する最長状態の選択と checkpoint 復元。
- `engine/src/program/generate.cpp:18613-18617` — session file 要求の適用制約と0指定の拒否。
- `engine/src/program/generate.cpp:4761-4763,14843-14850,18617` — warning、checkpoint save error、session file 拒否の出力経路。
