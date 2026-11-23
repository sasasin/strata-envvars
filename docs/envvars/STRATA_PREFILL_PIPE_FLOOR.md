# `STRATA_PREFILL_PIPE_FLOOR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

レイヤー分割時の prefill pipeline が、`STRATA_PREFILL_PIPE`（または CLI / request の `pipe` 設定）から正の `b/a` 比を使ってチャンク候補を探索するとき、その候補チャンクの下限を 256-token 単位で指定する。既定の下限は 512 token、最終的な下限は 256..4096 token に制限される。パイプラインの有効化、`b/a` 比、または既存の buffer chunk 上限はこの変数では設定しない。実装は `engine/src/prefill/prefill.cpp` の `pipe_floor()` と `Prefill::pipeline_chunk()`（同ファイル:3627-3635, 3647-3676）。

## 値と判定

`pipe_floor()` は `std::getenv` で取得し、未設定または空文字なら 512 を使う。それ以外は `std::atoll` で文字列先頭の符号付き十進数部分を変換し、`(x + 255) / 256 * 256` で 256 の倍数へ切り上げてから 256..4096 に clamp する。文字列全体の数値妥当性検査、空白除去、無効値のエラーや警告はない（`engine/src/prefill/prefill.cpp:3627-3634`）。

| 条件 | unset / 空文字 | 設定時に有効になる値 | 設定時に無効・境界になる値 |
|---|---|---|---|
| `pipe_floor()` が呼ばれる build / 経路 | 512 token | 先頭に数値がある値。例: `256`→256、`257`→512、`512tail`→512、`+768`→768 | `0`、負値、`true`、空白だけ、数値に変換できない文字列は 256 に clamp。4096 を超える値は 4096 に clamp。空文字は unset と同じ 512 |

`atoll` は末尾の文字を検査しないため、`512tail` は 512 として扱う。先頭空白や `+` / `-` は変換対象となり、`true` のように数字のない文字列は変換結果 0 から下限 256 になる。256 の倍数でない正数は次の倍数へ丸める（例: 257→512）。この関数には値の parse 失敗を通知する処理がない。`std::clamp` 前の極端な値に対する整数オーバーフローの扱いは、このコードから安全な入力規則として確定できないため記載しない（同ファイル:3629-3633）。

## 有効になる条件

- `Prefill::plan_chunk()` が呼ばれ、パイプライン設定値が 0 より大きく、hand-off 中ではなく、stage が 2 つ以上あること。単一 stage、`pipe <= 0`、または `hand_in_ != nullptr` では chunk planner を使わない（`engine/src/prefill/prefill.cpp:3683-3687`）。
- `pipe_floor()` が使われるのは設定値が 1 より大きい場合。`pipe <= 1` は `pipeline_chunk()` に ratio 0 を渡し、現在の chunk 数を均等化する別ルールへ進むため、この床値を参照しない（同ファイル:3650-3658, 3683-3687）。
- `STRATA_PREFILL_PIPE` は未設定なら 0 で、空文字も 0。CLI の `--prefill-pipe` が指定されると `Prefill::set_pipe()` を通じて環境値より優先され、サーバーの各 request に `pipe=` があれば request 値がさらに優先される。これらは pipeline の利用可否・ratio を選ぶ設定であり、`STRATA_PREFILL_PIPE_FLOOR` の値を上書きしない（同ファイル:3618-3625, 3637-3639; `engine/src/program/generate.cpp:4028, 6802, 18758-18759, 18818-18820, 18837`）。
- 最適化が下限値を使っても、その chunk が採用されるとは限らない。候補は buffer cap 以下に制限され、最良候補が従来の chunk より小さく、かつ推定コストが従来より 3% を超えて改善したときだけ採用される。そうでなければ従来の cap に戻る（`engine/src/prefill/prefill.cpp:3660-3676`）。
- OS / GPU backend を分ける環境変数判定や `#if` 分岐は、この値の読み取り・変換箇所にはない（同ファイル:3627-3635）。この値だけで layer split や pipeline を成立させるわけではない。

## 実行時の詳細

下限値の読み取りは `pipe_floor()` 内の関数 `static` 初期化で行われる。初めて `pipe_floor()` が必要な正の ratio の候補探索に入った時点の環境値を一度だけ読み、そのプロセス中の後続呼び出しは cache された値を使う。起動後に環境を変更しても再読込されない。`pipe <= 1` の均等化ルールでは `pipe_floor()` 自体が呼ばれない（`engine/src/prefill/prefill.cpp:3627-3635, 3647-3672`）。

ratio が 1 より大きい場合、planner は従来の cap から必要な chunk 数を求め、床値から探索上限を計算し、各候補を 256-token grid に揃える。候補は `min(cap, max(floor, rounded_chunk))` となるため、cap が床値より小さい場合は cap が優先される。候補コストを比較し、3% 超の改善条件を満たした場合にだけ選んだ chunk を返す（同ファイル:3660-3676）。通常の prefill はこの計画 chunk を読み取りサイズに使い、選ばれなければ buffer の chunk を使う（同ファイル:4286-4302）。

サーバーの `read_part` 経路では segment 全体で計画した chunk を記録し、その segment の各 read に強制適用する。再開時は保存された plan の条件が合えば再利用し、合わなければ計画し直す。強制 chunk で実行する各 read では `plan_chunk()` を再度呼ばない（`engine/src/program/generate.cpp:20664-20696`; `engine/src/prefill/prefill.cpp:4290-4297`）。この環境変数を子プロセスへ転送・上書きする Strata 側の処理は候補名の全参照からは確認できない。

## ログと測定値

この変数の parse、clamp、fallback を知らせる専用ログはない。計画 chunk が選ばれ、従来の buffer cap より小さい場合には stderr に次の形式で計画が出る。値そのものや床値はログに含まれない（`engine/src/prefill/prefill.cpp:3694-3700, 4295-4298`; サーバーの計画ログは `engine/src/program/generate.cpp:20683-20694`）。

```text
strata prefill: <tokens> tokens in <chunk>-token chunks over <stages> stages (--prefill-pipe <ratio>: b/a)
```

`pipe <= 1` の経路では末尾が `1: today's chunk count, evened out` となる。改善条件を満たさず従来 chunk に戻る場合や、計画が buffer cap より小さくならない場合、この計画ログは出ない。無効な床値に対する Strata の警告や終了経路は実装されていない（同ファイル:3629-3633, 3671-3676, 4295-4298）。

## 根拠

- `engine/src/prefill/prefill.cpp:3627-3635` — 環境からの読み取り、既定値、丸めと clamp、static cache。
- `engine/src/prefill/prefill.cpp:3647-3676` — ratio 0 の別ルール、床値を使う候補探索、改善条件。
- `engine/src/prefill/prefill.cpp:3683-3700, 4283-4302` — planner 適用条件、chunk の選択とログ。
- `engine/src/program/generate.cpp:4028, 6802, 18758-18820, 18837, 20664-20696` — CLI / request の pipe 値と優先順位、サーバーでの plan 再利用。
- `docs/MULTI_GPU.md:151` — `--prefill-pipe` / `STRATA_PREFILL_PIPE` の概要。床値の挙動を説明する資料ではなく、測定値は記載しない。
