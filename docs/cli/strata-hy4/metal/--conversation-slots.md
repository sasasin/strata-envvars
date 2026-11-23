# `strata-hy4-metal --serve --conversation-slots`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-metal` |
| コマンド | `strata-hy4-metal --serve` |
| オプション | `--conversation-slots` |
| 別名 | `--conversation-cache-slots` |
| 値 | 整数。正の値が明示スロット数として採用される |

## 役割

`--session-reuse 1` で起動する Metal の HY4 serve モードにおいて、会話ごとの KV 状態を保持するスロット数の上限を指定する。リクエスト時には一致する先行会話の KV を再利用し、空きスロットがなければ最も長く使われていないスロットを再利用する。実際に確保される数は、会話 KV セットの大きさと `--conversation-cache-mib` の予算でも制限される（`engine/src/hy4flash/metal/hy4_metal_serve.h:260-268`、`engine/src/hy4flash/metal/hy4_metal_slots.h:35-67`）。

## 使い方

```sh
# 会話再利用を有効にし、最大 4 スロットを要求して Metal serve を起動する
strata-hy4-metal --model model.strata --serve --session-reuse 1 --conversation-slots 4
```

## 値と既定値

- 値は `atoi` で整数に変換される。別名 `--conversation-cache-slots` も同じ変数へ格納されるため、両表記の受理範囲と動作は同じ（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1592-1595`）。
- 引数を省略した場合の内部値は `-1`。`--serve` 設定を組み立てる際、値が `1` 以上ならその値を採用し、それ以外は `--session-reuse 1` のとき `4`、それ以外は `1` に置き換える（同 `:1494-1497`, `:1647-1650`）。したがって `0` や負数、`atoi` の結果が `0` になる入力は明示値として採用されず、この既定値に戻る。
- 実効スロット数は `--session-reuse` が有効な場合に限り、要求値と `--conversation-cache-mib` が許す数の小さい方となる。予算側は `conv_mib * 1,048,576 / KV セットのバイト数` を整数除算した値で、結果が 1 未満なら少なくとも 1 に補正される（`engine/src/hy4flash/metal/hy4_metal_serve.h:262-268`）。`--conversation-cache-mib` の既定値は 16,384 MiB（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1494-1496`）。
- 対象ソースでは、この値に対する明示的な範囲検証や上限エラーは確認できない。非数値の変換、整数の境界外入力、値引数の欠落に対する安全なエラー処理も実装箇所から確認できないため、正の整数を指定する。

## 実行時の動作

parser は値を `conv_slots_arg` に保存する。`--serve` の場合は `ServeOpts::conv_slots` に渡し、`--session-reuse` が有効なら実効数の上限として使う。複数スロットが使える場合、serve はリクエストと最も長い共通 prefix を持つ会話を再開対象に選び、該当しなければ空きスロット、まだ容量があれば新規スロット、満杯なら LRU スロットを選ぶ。スロット切替時は Runner とスロット間で KV バッファ等を交換する（`engine/src/hy4flash/metal/hy4_metal_slots.h:39-67`、`engine/src/hy4flash/metal/hy4_metal_serve.h:375-418`）。

`--session-reuse` を指定しない場合、指定値に関係なく実効数は 1 で、複数会話スロットとしては働かない。serve 以外の通常実行でも、この値はスロット設定へ渡されない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1650`, `engine/src/hy4flash/metal/hy4_metal_serve.h:262-268`）。

起動時の `INFO` 行には、予算適用後の `slots` と一スロット分の `slot_mib` が出力される（`engine/src/hy4flash/metal/hy4_metal_serve.h:302-304`）。cold-expert キャッシュが有効な場合は、複数スロットや SSD spill 用 KV セットの追加分を見込んでキャッシュ予算から差し引く。これは実効スロット数ではなく要求値 `plan_slots` と会話キャッシュ予算を用いた見積もりである（`engine/src/hy4flash/metal/hy4_metal_serve.h:227-232`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:645-652`）。

## 適用条件と副作用

- 対象は `strata-hy4-metal` の Metal backend にある `--serve` 経路。
- 会話スロットの選択・再利用を有効にするには `--session-reuse` が必要。画像を含むリクエストでは `no_reuse` として既存 KV の再開を行わない（`engine/src/hy4flash/metal/hy4_metal_serve.h:375-382`）。
- スロット数を増やすと追加の会話 KV セットを保持する可能性があり、Metal バッファとメモリ使用量に影響する。KV セットはスロットを必要とした時に確保される（`engine/src/hy4flash/metal/hy4_metal_serve.h:278-285`, `:397-405`）。cold-expert 使用時には追加 KV 分が expert cache 予算にも影響する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:645-659`）。
- `--conversation-spill-dir` 等の SSD spill 設定はスロット退避後の別階層に関わるが、このオプション単独では spill を有効にしない（`engine/src/hy4flash/metal/hy4_metal_serve.h:271-279`）。

## 出力とエラー

オプション固有の値検証エラーや警告は確認できない。要求数そのものではなく、キャッシュ予算適用後の実効スロット数が起動時 `INFO ... slots=N` に出力される（`engine/src/hy4flash/metal/hy4_metal_serve.h:302-304`）。未知の引数は `unknown flag` を標準出力、`unknown arg` を標準エラーへ出して終了コード 2 となるが、これはこのオプション固有ではない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1494-1497` — parser 変数と初期値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1592-1595` — `--session-reuse` と本オプションの parser、alias、`atoi` 変換。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1654` — `--serve` における既定値選択と `ServeOpts` への転送。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:227-232,262-268` — cold-expert 予算計画と会話キャッシュ予算による実効スロット数の算出。
- `engine/src/hy4flash/metal/hy4_metal_slots.h:35-67` — 一致会話、空き、新規、LRU の選択。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:278-285,302-304,375-418` — KV セット確保、実効数の起動時表示、要求ごとのスロット選択と切替。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:645-659` — cold-expert キャッシュ予算と追加 KV セット数の関係。
