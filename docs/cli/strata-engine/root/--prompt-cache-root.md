# `--prompt-cache-root`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンのトップレベル引数） |
| オプション | `--prompt-cache-root` |
| 別名 | なし |
| 値 | 非負の token 数。system prompt の root checkpoint を作る最小境界位置 |

## 役割

`--serve` で会話 prompt を処理するとき、system prompt の末尾にあたる最初の turn 境界を、token 0 から読み始めた prompt の追加 checkpoint として保存するための閾値です。既定値は 2048 token で、境界位置がこの値以上の場合に root checkpoint を作ります。複数の会話で共有される system prompt を再利用する用途です（`engine/src/program/generate.cpp:1128-1133, 21477-21489`）。

## 使い方

```sh
strata --pack <tag> --serve --prompt-cache-root 4096
```

`<tag>` は起動する pack のタグに置き換えます。値は token 数で指定します。

## 値と既定値

- 未指定時は `2048` です（`engine/src/program/generate.cpp:1130`）。
- parser は `std::atoll` で値を変換し、`std::max(0LL, ...)` で負の値を 0 にします。0 は root checkpoint を無効にします（`engine/src/program/generate.cpp:4114`）。
- この分岐では数値全体の厳密な形式検査や上限検査をしていません。数値でない入力も専用の validation error にはならず、変換結果に対して 0 以上への補正が行われます（同上）。
- 値を省略して argv の末尾にこのオプションだけを置くと、`--prompt-cache-root needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3842-3846`）。

## 実行時の動作

request 処理では、通常の prompt cache が有効（`--prompt-cache > 0`）で、turn token が有効（`--turn-token >= 0`）であり、今回の prompt が token 0 から始まるか token 0 からの中断読み込みを再開した場合にだけ root 境界を探します。最後の turn 境界より前にある最初の turn token を調べ、その位置が閾値以上なら `root_at` に設定します。読み取りの区切り一覧にこの位置が加わり、そこまで読んだ時点で他の会話 checkpoint と同様に実行状態を保存します（`engine/src/program/generate.cpp:21460-21489, 21522, 21610-21617`）。

root checkpoint はファイルではなく、会話 cache 内の実行状態 snapshot です。保持枠は `--prompt-cache` が決めます。保持枠が 2 以上なら root は eviction policy で保護され、それ以外の checkpoint が LRU 等で入れ替わります。保持枠が 1 未満では通常の cache 自体が無効、1 では root と新しい checkpoint の両方を保持できず root 保護も無効です（`engine/include/strata/program/conv_cache.hpp:12-24, 32-40`; 呼び出し側 `engine/src/program/generate.cpp:14725-14753`）。

request 内の `ckpt=0` は通常の turn checkpoint を止めますが、root 境界はその前に記録した `last_turn` を使って探索されるため、閾値を満たす root checkpoint は引き続き対象です（`engine/src/program/generate.cpp:18841-18845, 21482-21489`）。

## 適用条件と副作用

- この値が実際に使われるのは会話 request の prompt-cache 処理経路です。`--prompt-cache 0`、`--turn-token` が負、0 から始まる prompt でない場合は root checkpoint を作りません（`engine/src/program/generate.cpp:21484-21490`）。
- root の turn token が見つからない、またはその位置が閾値未満なら追加 checkpoint はありません。閾値は token 数を制御し、既存の読み取り chunk サイズは変更しません（同上、区切り処理 `21522-21527`）。
- 通常の `generate.cpp` parser を通るエンジン経路が対象です。Qwen3.6 family は parser の前に専用実装へ振り分けられる経路があり、このオプションを同じ仕様で受け付けることは確認できません（`engine/src/program/generate.cpp:3804-3818`）。SYCL 側にも同じ既定値・parser・root 境界処理があります（`engine/sycl/src/program/generate.cpp:747, 2092, 11613-11625`）。
- checkpoint 保存に失敗した場合は、継続可能な失敗なら stderr に checkpoint を skip した旨を出して request を続行し、継続不能なら stdout に `ERR saving a conversation checkpoint failed...` を出して終了コード 1 を返します。この経路は root 専用ではなく turn 等の checkpoint と共通です（`engine/src/program/generate.cpp:21610-21617`）。

## 根拠

- `engine/src/program/generate.cpp:1128-1133` — 既定値 2048 と turn token の既定値。
- `engine/src/program/generate.cpp:4111-4117` — parser の値変換と非負への補正。
- `engine/src/program/generate.cpp:21460-21489` — turn 境界の探索、適用条件、閾値判定。
- `engine/src/program/generate.cpp:21522, 21610-21617` — root 境界での checkpoint 保存と失敗時の出力。
- `engine/include/strata/program/conv_cache.hpp:12-24, 32-40` — root の保持方針と cache 枠が 2 未満の場合。
- `engine/sycl/src/program/generate.cpp:747, 2092, 11613-11625` — SYCL 実装の既定値・parser・root 判定。
