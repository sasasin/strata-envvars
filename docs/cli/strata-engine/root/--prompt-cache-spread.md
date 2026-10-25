# `--prompt-cache-spread`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root） |
| オプション | `--prompt-cache-spread` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

`--serve` の会話チェックポイントが上限に達したとき、単純な最終使用時刻順ではなく、会話末尾からの距離に応じてチェックポイントを間引く保持方針を選びます。履歴の少し前を編集したリクエストでも、より近いチェックポイントから再開しやすくするための指定です。

## 使い方

```sh
strata --model ./model.gguf --serve --prompt-cache-spread
```

このオプション自体に値は付けません。`--serve` を指定しない通常の生成経路では、チェックポイントの保持処理が使われないため効果はありません。

## 値と既定値

- オプションを付けると parser が真偽値を `true` にします。既定値は `false` です。
- 値の範囲、空値、数値変換の検証はありません。重複指定は同じ真偽値を再度設定するだけです。
- 保持できる個数は別オプション `--prompt-cache N` が決めます（既定値 6）。このフラグ自体は個数や RAM 予算を変更しません。

## 実行時の動作

新しいチェックポイントを加え、`--prompt-cache` の個数を超えた場合に、通常方針なら最終使用時刻に基づく選択を行います。このフラグを有効にすると、チェックポイントのトークン長を使う `spread_victim` に切り替わります。チェックポイント列の先頭（root）、末尾（最新）、および pin された項目を候補から外し、削除後の間隔を末尾までの距離で割った比率が最小の中間項目を削除します。候補がない場合や、個数上限が1未満相当など間引き計算ができない場合は通常方針に戻ります。

`--prompt-cache-tail` と併用して、最新項目ではない tail checkpoint があれば spread 計算より先にそれを削除します。pin された checkpoint は spread の候補から除外されます。チェックポイントは要求プロンプトの正確な prefix として再利用されるため、近似一致や部分状態の再利用を有効にする指定ではありません。

## 適用条件と副作用

- 効果があるのは通常の `generate.cpp` エンジン経路で、`--serve` 中にチェックポイント個数が上限を超えて削除対象を選ぶときです。チェックポイント作成自体は `--prompt-cache <= 0` または長さ `L < 1` なら行われません。
- 削除・保持方針だけを変え、チェックポイント数の上限は維持します。別途チェックポイントを増やすメモリ負担はありませんが、どの履歴が再利用可能かは変わります。
- Qwen3.6-35B-A3B は family switch により `src/qwen35` の別実装へ渡されます。この実装の parser に当該フラグはなく、serve モードで受け取った未知の `--` オプションは警告して無視します。したがってこのモデル経路では spread の効果はありません（`--serve` より前に未知フラグとして渡す場合は usage error になります）。
- GPU/メモリ上のチェックポイント保存に失敗した場合の処理は通常の checkpoint 経路に従います。このフラグ固有の外部ファイル生成・ネットワーク処理は確認できません。

## 出力とエラー

フラグを受け取ったことだけを示す専用メッセージはありません。通常経路で引数名が未知の場合は stderr に `unknown argument: ...` と usage を出して終了コード 2 になりますが、このフラグは parser に登録済みです。値を要求しないため、値不足エラーもありません。Qwen3.6 の serve 経路でこのオプションを無視する場合は stderr に `strata-q36: ignoring --prompt-cache-spread (not an option of this engine)` 相当の警告を出します。

## 根拠

- `src/program/generate.cpp:750` — フラグの既定値 `false`。
- `src/program/generate.cpp:925-927` — help に記載された serve 向けの説明。
- `src/program/generate.cpp:2663-2665` — parser 登録。値を読まず `true` に設定。
- `src/program/generate.cpp:2787-2792` — 未知引数の stderr、usage、終了コード 2。
- `src/program/generate.cpp:9701-9704` — checkpoint 作成が無効化される条件。
- `src/program/generate.cpp:9829-9856` — 上限超過時の削除選択と checkpoint の破棄。
- `include/strata/program/conv_cache.hpp:80-100` — spread の候補、tail/pin の扱い、通常方針への fallback。
- `src/program/generate.cpp:2393-2407` — Qwen3.6 family switch による別実装への委譲。
- `src/qwen35/q36_engine.cu:3742-3747,3782-3794` — Qwen3.6 parser の未知オプション処理と serve 前後の差。
- `docs/DETAILS.md:1152-1158` — 利用者向け説明。保持方針・例・測定値はこの資料の記載であり、本調査では再測定していません。

調査範囲は上記 checkout のソースとリポジトリ内資料です。同一 revision の既存 CLI `--help`、Release 配布バイナリでの挙動は別途実行・照合していません。ビルド、テスト、GPU 実行、性能測定は行っていません。
