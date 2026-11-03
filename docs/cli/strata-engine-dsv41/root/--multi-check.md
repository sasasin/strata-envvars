# `--multi-check`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（root） |
| オプション | `--multi-check` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`--parallel` で確保した複数会話について、各会話を単独で処理した結果と、複数会話をまとめて処理した結果を比較する検査モードです。通常の推論やサーバー起動の代わりに、greedy token と logits の一致を確認します（`src/dsv41/ds4_main.cpp:2244-2248, 2668-2669`）。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --parallel 2 --ids 1,128803,42 --multi-check
```

`--pack` にモデル pack、`--ids` にテスト用 prompt の token ID を指定します。`--parallel` は `2` から `8` の範囲で必要です。必要なら `--n N` で各会話について比較する生成 token 数を指定します（関連: [`--parallel`](--parallel.md)、[`--ids`](--ids.md)、[`--n`](--n.md)）。

## 値と既定値

- フラグ自体は値を取りません。parser は現れたとき boolean を `true` にし、複数回指定しても同じ状態です（`src/dsv41/ds4_main.cpp:2506, 2590`）。
- `--parallel` がない場合の会話数は `1` です。`--multi-check` 使用時は `--parallel 2..8` が必要で、範囲外は `--parallel takes 1 to 8` を stderr に出して終了コード `2` になります（`src/dsv41/ds4_main.cpp:2583-2588, 2609-2611`; `src/dsv41/ds4_model.hpp:74-76`）。
- `--ids` は必須です。未指定または空文字列では `--multi-check needs --parallel 2..8 and --ids` を stderr に出して終了コード `2` になります（`src/dsv41/ds4_main.cpp:2574, 2609-2611`）。`--ids @FILE` 形式では `@` の後のファイルを読みます（`src/dsv41/ds4_main.cpp:2662-2668`）。
- `--n` の初期値は `0` ですが、検査呼び出し時に `max(2, n)` を使うため、省略時、`0`、負数はいずれも2 tokenになります。正の値はその数が使われます（`src/dsv41/ds4_main.cpp:2502, 2575, 2669`）。

## 実行時の動作

各会話 `i` に同じ `--ids` prompt を用意し、後続の会話ほど先頭から `5*i` 個の token を除いた prompt を使います（残りが少ない場合は元の prompt 長を使います）。まず各会話を個別に feed し、greedy sampling で `n` token を生成して token 列と各 step の logits を保存します。次に prompt を再度 feed し、全会話の次 token を `step_multi` / `sample_multi` で一括処理して比較します（`src/dsv41/ds4_main.cpp:2248-2265, 2271-2319`）。

logits は、その時点までの token 履歴が単独処理と一致する行だけを比較し、語彙全体の float 配列が bit-for-bit 一致したかを数えます。token 列の差異位置、logits の一致行数と最大絶対差、単独・一括それぞれの測定 token/s を stdout に出力します（`src/dsv41/ds4_main.cpp:2312-2337`）。

モデルに DSpark drafter があり `draft_block() > 0` の場合、追加で3通り（単独、会話単位で順に draft、一括 draft）を greedy で検査し、token の一致、round 数、draft 採用数、速度を stdout に出します（`src/dsv41/ds4_main.cpp:2338-2344, 2457-2475`）。

## 適用条件と副作用

- `--multi-check` は `--serve` と組み合わせる起動オプションではありません。通常の制御フローではモデル読み込み後に `serve_mode` を先に処理して戻るため、`--serve --multi-check` は前提条件を満たしていても検査関数へ進まずサーバーループに入ります。検査目的では `--serve` を付けないでください（`src/dsv41/ds4_main.cpp:2609-2625, 2627-2629, 2668-2669`）。
- 検査前に `--pack` のモデルを `m.load()` でロードします。ロード失敗は `maya-ds4: <理由>` を stderr に出して終了コード `1` です（`src/dsv41/ds4_main.cpp:2613-2625`）。そのためこのフラグはモデル実行環境を必要とします。
- `--expert-profile` を指定しない場合、main は profile の読込先を `<pack>/expert-profile.bin` に設定します（`src/dsv41/ds4_main.cpp:2617-2618`）。ただし `--multi-check` は検査結果を返した時点で main を抜け、通常の生成経路末尾にある `m.save_profile()` には到達しません（`src/dsv41/ds4_main.cpp:2668-2669, 2862-2864`）。profile 書込処理は一時ファイル `<profile>.tmp` を作って置換する実装です（`src/dsv41/ds4_model.cu:14802-14812`）。
- `--pack-info` が指定されていると、その処理が `--multi-check` の必須条件検査より先に終了する場合があります。検査には `--pack-info` を併用しないでください（`src/dsv41/ds4_main.cpp:2602-2612`）。
- 検査関数内ではモデル計算を複数回実行し、検査結果のファイル出力は行いません。モデルロード時の profile 読込以外の副作用や backend ごとの実行条件は、このフラグの経路だけからは特定できません。

## 出力とエラー

prompt feed、単独 step / logits 取得、一括 step / logits 取得、または drafter の各処理に失敗すると `multi check: <理由>` を stderr に出して終了コード `1` になります（`src/dsv41/ds4_main.cpp:2271-2284, 2290-2308, 2348-2378, 2409-2444`）。

比較結果が不一致の場合も summary を stdout に出した後、token 一致、drafter 検査結果、logits の比較行すべてが一致しなければ終了コード `1` です。一致すれば `0` です（`src/dsv41/ds4_main.cpp:2322-2337, 2457-2475`）。

## 根拠

- `src/dsv41/ds4_main.cpp:2500-2518, 2574-2590`: parser の状態、フラグ宣言、隣接オプションの値処理。
- `src/dsv41/ds4_main.cpp:2602-2629, 2662-2669`: 前提条件、モデルロード、`--serve` 分岐、実際の検査呼び出し。
- `src/dsv41/ds4_main.cpp:2244-2475`: 検査対象、比較、出力、エラーと終了コード。
- `src/dsv41/ds4_model.cu:14802-14812`: 明示的な expert profile 保存処理。
- `src/dsv41/ds4_model.hpp:74-76`: `--parallel` の既定会話数。
