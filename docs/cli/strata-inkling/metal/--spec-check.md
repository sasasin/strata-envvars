# `strata-inkling-metal --spec-check`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal`（Metal backend） |
| オプション | `--spec-check` |
| 別名 | なし |
| 値 | 値なしのフラグ |

## 役割

同じモデルとプロンプトで通常の greedy decode と DSpark を使う decode を順に実行し、生成 token の一致数と各経路の時間・DSpark の受理統計を表示します。Metal runner の speculative decode が通常 decode と一致するかを確認するための診断モードです。

## 使い方

```sh
# 既定のテスト prompt で比較する（モデルファイルは読み込み、Metal 上で2回 decode する）
strata-inkling-metal --model ./model.strata --spec-check

# 指定した prompt token と生成上限で比較する
strata-inkling-metal --model ./model.strata --ids 200001,200004,15496 --gen 64 --spec-check

# DSpark の tree draft 経路を指定して比較する
strata-inkling-metal --model ./model.strata --draft tree16 --spec-check
```

## 値と既定値

`--spec-check` 自体は値を取らず、指定すると `do_spec_check` を true にします。既定値は false で、同じ引数を複数回指定しても true のままです。別名やこのフラグ専用の値 validation はありません。未知の引数は `unknown arg` を stderr に出して終了コード 2 になります（`engine/src/inkling2/metal/ink_metal_main.cpp:425-426,432-467`）。

比較に使う prompt は `--ids` で指定できます。空の token 列なら既定の8 token `{200001, 200004, 15496, 11, 1268, 527, 499, 30}` が使われます。生成数は `--gen` の値を使い、省略時は32です。`--gen` は `atoi` で変換され、範囲検証はありません。0以下の場合は decode 関数が生成せず正常終了します（`engine/src/inkling2/metal/ink_metal_main.cpp:423,451,460-463,511-515`; `engine/src/inkling2/metal/ink_metal_main.cpp:138-163`）。

## 実行時の動作

モデル読み込みと runner 初期化の後、`--spec-check` は同一 prompt に対して `run_greedy_decode` を2回呼びます。最初は `use_spec=false` の通常 decode、次は `use_spec=true` の decode です。2回目では runner が DSpark を利用可能な場合に draft / verify 経路が使われ、生成 token の共通 prefix を比較して `[SPEC-CHECK ...]` 行に一致数、`BITWISE-EXACT` または `DIFF`、速度、accept/offered 数を表示します。先頭の相違位置がある場合は追加行も出します（`engine/src/inkling2/metal/ink_metal_main.cpp:560-586`; `engine/src/inkling2/metal/ink_metal_main.cpp:138-188`）。

`--draft` は比較モードの方式に影響します。既定 `auto` および tree budget に対応する値では runner の DSpark 利用を要求し、`tree` / `beam` は動的 tree、`tree6`・`tree8`・`tree10`・`tree12`・`tree16`・`tree24`・`tree32` は指定 budget の tree として処理します。マッピングされない値は parser で拒否されず、tree budget 0 の線形 draft 扱いです。`--draft off` では runner の DSpark が無効になりますが、spec-check 自体は引き続き2回実行され、2回目も通常 decode になります（`engine/src/inkling2/metal/ink_metal_main.cpp:419,453,489-492,550-558,564-570`; `engine/src/inkling2/metal/ink_metal_runner.h:230-240`; `engine/src/inkling2/metal/ink_metal_main.cpp:118-120`）。

## 適用条件と副作用

この option は Metal 版 `strata-inkling-metal` に属します。`--model` が必須で、モデルを読み込んだ後に Metal runner を初期化します。runner はモデル manifest に DSpark がある場合に限り DSpark を有効にします。通常は起動時 warm-up も行われます（`--no-warm` 指定時を除く）。このモードは GPU/Metal 上で2回の推論を行い、実行時間を消費します。該当ソース経路には `--spec-check` によるファイル書き込みやネットワーク処理はありません（`engine/src/inkling2/metal/ink_metal_main.cpp:470-493,560-570`; `engine/src/inkling2/metal/ink_metal_runner.h:230-242`）。

他のモードフラグも同時指定できます。その場合、通常の処理順で selfcheck / logits dump が先、spec-check が続き、bench や parallel sweep が後に実行されます（`engine/src/inkling2/metal/ink_metal_main.cpp:517-548,560-614`）。

## 出力とエラー

比較結果は stdout に出ます。生成 token が一致しなくても `DIFF` を表示するだけで、ここでは不一致を終了エラーにしません。decode 呼び出しが失敗した場合は `[ERROR] plain decode: ...` または `[ERROR] spec decode: ...` を stderr に出し、終了コード1で終了します。モデル未指定時は usage を stderr に出し、終了コード2です（`engine/src/inkling2/metal/ink_metal_main.cpp:560-586,470-473`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-467` — parser、既定値、引数エラー処理。
- `engine/src/inkling2/metal/ink_metal_main.cpp:470-515` — モデル必須条件、runner 初期化、既定 prompt。
- `engine/src/inkling2/metal/ink_metal_main.cpp:118-188` — greedy decode の prompt 処理、生成上限、DSpark 分岐。
- `engine/src/inkling2/metal/ink_metal_main.cpp:550-586` — draft budget、2つの decode、比較と出力。
- `engine/src/inkling2/metal/ink_metal_runner.h:230-242` — context 制限値の補正と manifest に基づく DSpark 有効化。
