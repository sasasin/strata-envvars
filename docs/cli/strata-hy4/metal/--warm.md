# `strata-hy4-metal --warm`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal 実装） |
| オプション | `--warm` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

モデルをロードした後、推論を始める前にモデルのページをメモリへ読み込ませます。実装コメントでは、初回 dispatch 時に cold page の読み込み待ちが起きるのを避ける目的とされています。Metal runner のモデルを先にロードして終了する場合にも、`--load-only` と併用してページを warm できます。

## 使い方

```sh
# モデルをロードし、ページを warm して終了する
strata-hy4-metal --model ./model.strata --warm --load-only
```

`--warm` 自体に引数はありません。コマンドには `--model` でモデルファイルを指定します。

## 値と既定値

`--warm` はフラグで、指定すると内部の `warm` が `true` になります。省略時は `false` のままで、warm 処理は呼び出されません。値の範囲や値の validation はありません。同じフラグを複数回指定しても真偽値を設定するだけで、挙動は変わりません（parser は各 argv 要素を順に処理します）。

## 実行時の動作

モデルの `load` が成功した後、`--warm` が指定されていると `g.warm(8)` を呼び、処理時間を stderr に `[load] paged in ... s` と出力します。`warm` は trunk と、cold-expert モードでない場合の expert section に対し `madvise(..., MADV_WILLNEED)` を呼び、16 KiB ごとにページ先頭を8スレッドで読みます。これは読み込みを促す処理で、モデルファイルを書き換えるコードはありません。

`--cold-experts` が有効な場合は `cold_experts` が真になり、warm は trunk のみを対象にして expert section を触りません。cold-expert モードは `--cold-experts` の指定、モデル長が Metal の最大 buffer を超える場合、またはファイルサイズが推奨 working set の 88% を超える場合に選ばれます。

warm 処理は `--load-only` の終了判定より前にあり、`--serve` の分岐よりも前です。そのため、いずれの実行経路でも `--warm` が指定されモデルロードが成功すれば先に warm します。省略時にモデルページを明示的に走査する処理はありません。

## 適用条件と副作用

- Metal runner のモデルロードが成功した場合に実行されます。モデルロードに失敗すると warm には到達せず、エラーを stderr に出して終了コード 1 になります。
- `--cold-experts` または自動判定による cold-expert モードでは expert section は warm されず、trunk のみが対象です。
- warm 中はページ読み込みを促し、最大8個の worker thread を作成してページを読みます。処理時間やメモリ常駐量はモデルと実行環境に依存します。`madvise` の戻り値は検査されておらず、ページが実際に常駐したことを保証する成功判定はありません。

## 出力とエラー

warm の完了後は経過秒数を stderr に出します。warm 自体に専用の validation error や失敗コードは実装されていません。モデル指定がなく、かつ `--model` が空の場合は usage を stderr に出して終了コード 2 です。不明な引数も stdout と stderr に診断を出して終了コード 2 になります。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1506` — `main` の argv 処理とフラグ初期値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1523` — `--warm` を引数なしフラグとして受理。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:237-254` — ファイル長・Metal buffer・working set に基づく通常/cold-expert モード判定と mmap。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:276-298` — `warm` の目的、`madvise`、16 KiB ごとのページ読み込み、cold-expert 時の expert section 除外。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1613` — 不明引数とモデル未指定時の出力・終了コード。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1617-1635` — モデルロード失敗時の終了コード、および warm が `--load-only` より前に実行される順序。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1637` — warm 後に `--serve` の処理へ進む分岐。
