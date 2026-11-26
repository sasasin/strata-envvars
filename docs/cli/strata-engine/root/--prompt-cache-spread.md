# `--prompt-cache-spread`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--prompt-cache-spread` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`--serve` の会話キャッシュが保持数上限を超えたとき、通常の最終使用時刻順の削除に代えて、会話末尾に近い checkpoint を密に、会話の先頭側ほど疎に残すよう削除対象を選びます。クライアントが末尾から少し前の履歴を書き換えたとき、先頭から全てを読み直すのを避けるための選択方式です。checkpoint の保持数を増やすオプションではありません。

## 使い方

```sh
# モデル pack を読み込み、serve モードで checkpoint を会話末尾から分散して保持する
strata --serve --pack /path/to/model-pack --prompt-cache-spread
```

## 値と既定値

値は不要です。parser はフラグを見つけると bool を `true` にし、未指定時は `false` です。同じフラグを複数回指定しても true のままです。値の範囲検証はありません。フラグの後ろに値を置く構文ではなく、その値が別の引数として処理されます。

## 実行時の動作

`--prompt-cache-spread` 自体はキャッシュ数や checkpoint 作成頻度を変えません。serve 中に checkpoint が追加され、保持数が `--prompt-cache` の上限を超えたときにだけ削除処理が走ります。既定の保持上限は 6 件です。オプションが有効なら、checkpoint の token 数と pin/tail 状態を使う `spread_victim` を呼び、無効なら使用時刻を使う `eviction_victim` を呼びます。

分散方式は、checkpoint が3件以上かつ上限が2件以上の場合、root（先頭）・最新・pinned を候補から除外し、残る候補のうち削除後の前後 checkpoint 間隔が、その候補から最新までの距離に対して最も小さいものを選びます。tail checkpoint が候補に含まれる場合は、通常候補の計算より先に tail を削除します。条件を満たさない場合や削除候補がない場合は LRU 方式へ戻ります。したがって、`--prompt-cache` が 0 のときや保持数が上限以下の間は、このフラグによる削除方式の差は現れません。

周期 checkpoint の生成間隔は `--prompt-cache-every` が決めます。near-tail checkpoint を使う `--prompt-cache-tail` と併用した場合、その tail は次の上限超過時に優先的な削除対象になります。checkpoint の数・保存形式は変更しません。

## 適用条件と副作用

このオプションの説明と利用箇所は `--serve` の会話 checkpoint 処理です。対話的な単発生成だけで checkpoint 保持・削除が起きない場合、分散選択は使われません。削除時に保持 checkpoint の内容が入れ替わり、後続リクエストで再利用可能な履歴位置が変わります。ソース上、このフラグによるファイルやネットワークへの直接副作用は確認できません。

## 出力とエラー

このフラグ固有の警告・エラーはありません。値を取らないため、フラグ自体に対する数値 validation もありません。無関係な未知引数は stderr に `unknown argument: ...` と usage を出して終了コード 2 になります。`STRATA_TRACE` が有効で checkpoint の削除が発生した場合、削除数と所要時間を stderr に trace 出力します。

## 根拠

- `engine/src/program/generate.cpp:1086-1090` — serve の会話 checkpoint 保持数の既定値は 6。
- `engine/src/program/generate.cpp:1124-1130` — periodic checkpoint 関連設定と `prompt_cache_spread` の既定値 false。
- `engine/src/program/generate.cpp:1332-1334` — help に記載された `--serve` 向けの説明。
- `engine/src/program/generate.cpp:4111-4114` — parser は値を消費せず spread フラグを true にする。
- `engine/src/program/generate.cpp:14595-14607` — checkpoint 保存関数は保持数 0 や token 数 0 以下では保存を行わず、同一位置の checkpoint は使用時刻を更新する。
- `engine/src/program/generate.cpp:14723-14753` — 上限超過時の victim 選択と checkpoint の削除。
- `engine/src/program/generate.cpp:14755-14759` — `STRATA_TRACE` 有効時の eviction 時間出力。
- `engine/src/program/generate.cpp:14820-14827` — periodic / near-tail checkpoint の生成条件。
- `engine/src/program/generate.cpp:4271-4274` — 未知引数の stderr、usage、終了コード 2。
- `engine/include/strata/program/conv_cache.hpp:115-135` — spread victim の候補・tail 優先・fallback 規則。
