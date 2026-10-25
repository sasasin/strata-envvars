# `--prompt-cache-tail`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン。Terminal CLI の wrapper ではない） |
| オプション | `--prompt-cache-tail` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。既定値は無効 |

## 役割

`--serve` 中、読み込んだ prompt の末尾近くに追加の会話 checkpoint を最大 1 個保存します。履歴の大部分を共有しつつ、最後の保存済み checkpoint より前で分岐する次の request が、読み直す prompt 範囲を短くできる場合があります。効果は分岐位置と request によります。速度向上を保証するオプションではありません。

## 使い方

モデル pack と token ID 入力を用意し、たとえば次のように指定します（`prompt.ids` は token ID を含むファイルです）。

```sh
strata --pack pack/full --tokens-file prompt.ids --serve --spec 8 --prefill 6144 \
  --prompt-cache 8 --prompt-cache-every 16384 --prompt-cache-tail
```

エンジンの usage では serve に `--spec T` と `--prefill CHUNK` が必要です。`--tokens-file` は `--tokens` の代替です（`src/program/generate.cpp:808-812, 8354-8359, 2432-2435`）。

## 値と既定値

- 引数値は不要です。指定すると parser が `prompt_cache_tail` を `true` にします。既定値は `false` です（`src/program/generate.cpp:749, 2663`）。
- 同じフラグを複数回指定しても真偽値を再度 `true` にするだけです。
- このフラグ自体に値の範囲検証はありません。機能が動く条件は実行時に判定され、条件を満たさない場合もこのフラグ単独の validation error は出ません。
- checkpoint 数 `--prompt-cache` の既定値は 6、定期保存間隔 `--prompt-cache-every` の既定値は 16384 です。`--prompt-cache-every 0` は定期保存を止めます。tail の保存にも両方の値が正であることが必要です（`src/program/generate.cpp:725-750, 922-925, 2640, 2663-2666`）。

## 実行時の動作

parser はフラグを受理して状態に記録しますが、tail checkpoint の候補判定は `--serve` の request prompt を batched path で読む処理にあります。次の全条件を満たすとき、その prompt で最初に該当した位置に checkpoint を保存します（`src/program/generate.cpp:9907-9932`）。

1. `--prompt-cache-tail` が指定され、`--prompt-cache > 0` かつ `--prompt-cache-every > 0`。
2. layer split ではない単一 GPU 実行（`!multi_gpu`）。
3. その prompt の tail checkpoint がまだ保存されていない。
4. batched chunk の後ろに残る token 数が `max(1, --short-read)` より大きく、かつ現在の chunk の実際の長さ以下。既定の `--short-read` は 64 です。

位置は既存の batched chunk 境界から選ばれます。prefill の chunk 分割や定期 checkpoint の間隔は変えません。`--prefill auto` では chunk ごとに実際の長さが異なるため、判定には設定値ではなく現在の chunk 長 `T` が使われます。短い末尾部分は `--short-read` の既存経路に残ります。

checkpoint は実行中 session の状態をコピーして保持します。保存前に GPU 同期が行われ、checkpoint cache の上限を超えた分は eviction されます（`src/program/generate.cpp:1731-1736, 9701-9712, 9782-9803, 9826-9857`）。cache が満杯の場合、tail checkpoint は根 checkpoint ではなく、tail 以外の checkpoint より先に eviction されます。ただし新しく保存した最も新しい checkpoint は eviction 対象として選ばれません。tail checkpoint は最大 1 個で、新しい tail を保存すると以前の tail は削除されます（`include/strata/program/conv_cache.hpp:43-55`, `src/program/generate.cpp:9813-9857`）。

`--prompt-cache 0`、`--prompt-cache-every 0`、layer split、または候補位置がない prompt では tail checkpoint は保存されません。周期 checkpoint が同じ位置にある場合は状態を重複保存せず、その checkpoint を通常の checkpoint として扱います（`src/program/generate.cpp:9701-9709, 9910-9928`）。これらの条件を満たさなくても、tail option 固有の警告やエラーは確認できません。

## 適用条件と副作用

- 対象は engine の `--serve` 経路です。非 serve 実行では、フラグは parser に受理されますが、ここで説明する tail checkpoint 処理には到達しません（`src/program/generate.cpp:8354, 9907-9932`）。
- 単一 GPU のみが対象です。layer split では `tail_checkpoint` 条件が偽になり、この機能による追加 checkpoint は保存されません。通常の periodic checkpoint 処理は別途あります（同 `src/program/generate.cpp:9910-9917`）。
- 追加 checkpoint は prompt cache の既存上限内に収まるため、別枠の無制限な履歴を追加しません。一方、該当時には checkpoint 保存の同期と状態コピーが発生し、host memory と request 処理時間を使います。容量や時間の固定値はソースから一律には定まりません。
- 環境変数や設定ファイルによるこのフラグの上書きは parser・利用箇所では確認できません。

## 出力とエラー

このフラグ指定や checkpoint 成功を知らせる専用メッセージは確認できません。serve の通常進捗出力（`PP ...` など）は継続します（`src/program/generate.cpp:9898-9905`）。

checkpoint 保存に失敗すると `read_part` がエラーを返し、serve は理由を stderr の `strata serve: ...` と stdout の `ERR ...` に出して request 処理から `return 1` します。GPU 同期失敗時は理由に GPU 停止応答を含めます（`src/program/generate.cpp:9693-9698, 9927-9930, 14107-14118`）。フラグ名が未知の場合は一般の parser エラーとして stderr に `unknown argument` と usage を出し、parser はコード 2 を返します（同 `src/program/generate.cpp:2787-2793`）。

## 根拠

- 索引上の scope と配置: `docs/cli/README.md:1128-1134, 1263-1268`（この文書は索引の `strata-engine/root` option）。
- option の既定値・parser・help 記述: `src/program/generate.cpp:725-750, 922-925, 2663-2666`。
- 候補位置、保存、eviction: `src/program/generate.cpp:9701-9712, 9813-9857, 9907-9932`。
- tail の eviction 優先規則: `include/strata/program/conv_cache.hpp:43-55`。
- checkpoint 保存・失敗の伝播: `src/program/generate.cpp:1731-1736, 9693-9698, 14107-14118`。
- engine executable の build 定義: `CMakeLists.txt:759-762`。
- 補助資料 `docs/PROMPT_CACHE_TAIL.md` はこの revision の説明として確認しました。ここでは実装上の条件と効果を上記ソース位置に基づいて記載しています。
