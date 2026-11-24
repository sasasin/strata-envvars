# `strata-inkling --batch-check`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--batch-check` |
| 別名 | なし |
| 値 | 整数 `N`。`atoi` で変換し、`N > 0` の場合に検査モードを実行する |

## 役割

同じ token ID の prompt を単独 slot と複数 slot の batch で処理し、slot 0 の各ステップについて logits の KL divergence、top-1 token の一致、単独実行時の top-1/top-2 の差を比較する診断モードです。単独実行で得た greedy token を batch 側の slot 0 に teacher-force するため、両経路で比較する位置を揃えます。判定値は処理を切り替える設定ではなく、batch logits の差を表示し、KL が閾値を超えた場合に非ゼロ終了するための診断結果です（`engine/src/inkling2/ink_main.cpp:445-449, 471-493, 496-580`）。

## 使い方

```sh
# token ID のカンマ区切りを使い、4 slot で 8 token 分を検査
strata-inkling --native ./model.strata --prompt-ids 200002,200004,100 --parallel 4 --batch-check 8

# token ID をテキストファイルから読み込む
strata-inkling --native ./model.strata --prompt-ids @./prompt-ids.txt --parallel 4 --chunk 256 --batch-check 8
```

`--prompt-ids` は必須です。`--native` にはモデルのパスを指定してください。`--prompt-ids @file` はファイル全体を読み込み、同じ ID リスト解析へ渡します（`engine/src/inkling2/ink_main.cpp:870-871, 957-963, 1053-1060`）。

## 値と既定値

- `N` に別名はなく、値は `std::atoi` で整数化されます。値が省略されると parser の `next()` が `missing value after --batch-check` を stderr に出して終了コード 2 で終了します。数値として読めない値は `atoi` により 0 となり、`N <= 0` ではこのモードに入りません。正の値に上限検証はありません（`engine/src/inkling2/ink_main.cpp:845-849, 964-966, 1053`）。
- `N` の省略時は内部値 0 で、検査を起動しません。`N > 0` のとき、prompt 後の logits 1 件と、その後 `N` 回の decode logits を比較するため、結果のステップ数は `N + 1` です（`engine/src/inkling2/ink_main.cpp:842, 484-492, 558-579`）。
- `--prompt-ids` はカンマ区切りの整数 token ID、または `@` で始まるファイル指定を受け取ります。ID リストは空でない必要がありますが、parser は token ID の語彙範囲や `int32_t` への収まりを検証しません（`engine/src/inkling2/ink_main.cpp:957-963, 1053-1058`; `engine/src/inkling2/ink_serve.h:290-305`）。
- 同時 batch slot 数は `--parallel` で指定し、既定値は 1、parser は 1 から `kMaxParallelSlots` の範囲に clamp します。`--chunk` は既定 512 token で、1 以上に clamp されます。これらは比較条件を変えます（`engine/src/inkling2/ink_backend.h:17-21`; `engine/src/inkling2/ink_main.cpp:877-881, 457, 466`）。

## 実行時の動作

起動時に `--batch-check N` が指定され、かつ `N > 0` なら `--prompt-ids` の値を解析し、モデルを開いて backend を初期化し、`--parallel` 分の slot を割り当てます。必要なら `max_ctx` を `prompt 長 + N + 64` まで引き上げます。比較時は dspark を無効化します（`engine/src/inkling2/ink_main.cpp:450-464`）。

まず slot 0 だけで prompt を chunk 単位に prefill し、greedy argmax token を `N` 回生成して logits と token 列を保存します。その後全 slot を reset し、slot 0 と他 slot に同じ長さの prompt を与えます。他 slot の ID は元の列を位置 `(i + slot * 997) % prompt長` で回転したものです。各 batch step では decode を先に処理し、残る chunk budget を prefill 中の slot に均等分配します。slot 0 は先に保存した greedy token 列を teacher-force します（`engine/src/inkling2/ink_main.cpp:471-553`）。

`--chunk` は単独・batch 両方の chunk 予算に使われます。環境変数 `INK_BC_SOLO_CHUNK` に正数を指定すると単独側の chunk だけを上書きでき、未設定または正数でない場合は `--chunk` の値を使います（`engine/src/inkling2/ink_main.cpp:466-468, 477-482, 512`）。`--parallel` が 1 の場合も比較処理自体は実行されますが、batch 側に他 slot はありません。

各ステップの KL は solo logits を基準分布、batch logits を比較対象として計算します。KL が 1.0 を超えたステップがあれば終了コード 1 にし、最後に平均・最大 KL と top-1 flips 等を stdout に出します。通常は最初の4ステップ、top-1 が異なるステップ、または KL が 0.01 を超えたステップの詳細を出します（`engine/src/inkling2/ink_main.cpp:558-580`）。

## 適用条件と副作用

- `--prompt-ids` がない、または空・不正な ID リストの場合は stderr に `--batch-check needs --prompt-ids (a list or @file)` を出し、終了コード 2 です。`@file` を開けない場合は parser 中に `cannot read <path>` を出して終了コード 2 です（`engine/src/inkling2/ink_main.cpp:957-963, 1053-1059`）。
- モデル読込、backend 初期化、slot 割当、forward の失敗はそれぞれ `open:`, `init:`, `alloc_slot:`, `solo prefill:`, `solo decode:`, `batched:` を stderr に出し、終了コード 1 です。scheduler が所定の logits を集められない場合も終了コード 1 です（`engine/src/inkling2/ink_main.cpp:454, 460, 463, 481, 490, 538, 553`）。
- このモードはモデル推論を単独・batch の2経路で実行し、GPU または選択した backend の slot と計算資源を使用します。ソース上、結果ファイルへの書き出しはありません（`engine/src/inkling2/ink_main.cpp:450-580`）。
- 複数のモード指定がある場合、`--info`、`--export-tokenizer`、`--selfcheck`、`--kld-eval`、`--dump-ref`、正の `--ring-check` が `--batch-check` より先に選ばれます。`--batch-check` は `--spec-check` と `--bench` より先に評価されます（`engine/src/inkling2/ink_main.cpp:1039-1071`）。
- 同ファイルの `--help` 出力には `--batch-check` の構文が掲載されていません。parser と実装には存在するため、ここでは索引とソースを根拠に記述しています（`engine/src/inkling2/ink_main.cpp:964-966, 974-984`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:845-849, 964-966` — 引数 parser、整数変換、値省略時の終了経路。
- `engine/src/inkling2/ink_main.cpp:957-963, 1053-1060` — prompt ID の受け取り・ファイル読込・必須条件とモード選択。
- `engine/src/inkling2/ink_serve.h:290-305` — ID リストの解析と空入力・不正 token の扱い。
- `engine/src/inkling2/ink_main.cpp:445-580` — 検査の比較対象、推論・scheduler、出力、終了判定。
- `engine/src/inkling2/ink_backend.h:17-21`; `engine/src/inkling2/ink_main.cpp:457-468, 512-538` — slot/chunk の既定値と比較条件への反映。
