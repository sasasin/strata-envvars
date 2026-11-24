# `strata-inkling --ring-check`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--ring-check` |
| 別名 | なし |
| 値 | 必須の整数 `STRIDE`。正数のとき比較を実行する |

## 役割

同じ prompt token 列を一括 forward と 1 token ごとの forward で処理し、指定位置の logits を比較する診断モードです。SWA K/V ring に関係する batch logits の差を調べる用途として実装されています（`engine/src/inkling2/ink_main.cpp:369-374,376-441`）。

## 使い方

```sh
strata-inkling --native model.strata --prompt-ids 1,2,3,4 --ring-check 128
```

`--prompt-ids` はカンマ区切りの token ID 列、または `@ファイルパス` で指定します。token ID をファイルから読む場合の例:

```sh
strata-inkling --native model.strata --prompt-ids @prompt-ids.txt --ring-check 128
```

`--native`（別名 `--model`）でモデルを指定し、`--prompt-ids` と正の stride を渡してください。モデル指定の形式は `.strata`、HF ディレクトリ、`.gguf` を受け付ける共通 CLI のエラー表示に記されています（`engine/src/inkling2/ink_main.cpp:870-871,1073-1075`）。

## 値と既定値

- 値は次の引数を `std::atoi` で整数変換します。省略すると parser の共通処理が `missing value after --ring-check` を stderr に出して終了コード 2 で終了します（`engine/src/inkling2/ink_main.cpp:845-849,968-969`）。
- 初期値は 0 です。変換結果が正数の場合にのみ ring-check の処理へ入ります。0、負数、整数として読めない値（`atoi` が 0 を返す場合）は比較を起動せず、他のモードにも該当しなければ通常の生成経路へ進みます。明示的な範囲エラーはありません（`engine/src/inkling2/ink_main.cpp:842,968-969,1044-1052`）。
- 内部では stride を 1 以上に補正しますが、呼び出し条件が正数なので、通常この補正は値を変えません（`engine/src/inkling2/ink_main.cpp:387,1044`）。

## 実行時の動作

1. parser は指定値を `ring_check_stride` に保存します（`engine/src/inkling2/ink_main.cpp:968-969`）。
2. 先行する `--info`、`--export-tokenizer`、`--selfcheck`、`--kld-eval`、`--dump-ref` の各モードが選ばれていない場合、正の stride で ring-check 分岐に入ります（`engine/src/inkling2/ink_main.cpp:1039-1052`）。
3. `--prompt-ids` がない、空、または ID リストとして解釈できない場合はエラーを出して終了コード 2 になります。ID リストは `strtol` で10進整数を順に読み、各値の後のカンマは読み飛ばします（`strtol` により空白も区切りとして通ります）。`@file` の場合は parser がそのファイルをバイナリ読み込みし、読めなければ `cannot read <path>` を stderr に出してコード 2 で終了します（`engine/src/inkling2/ink_main.cpp:957-963,1045-1049`; `engine/src/inkling2/ink_serve.h:290-305`）。
4. モデルを開き、選択 backend を初期化して slot 0 を確保します。通常の backend 選択に使う `--cpu`、GPU/backend 設定、KV dtype なども共通 parser の設定として渡されます（`engine/src/inkling2/ink_main.cpp:376-381,882-952`）。
5. 全 token を既定 4096 個ずつ（`INK_RING_CHECK_BATCH` 環境変数が正数ならその値）に分けて `forward_batch` し、stride ごとの位置と末尾最大 8 位置の logits を保存します。その後 slot 0 を reset して、同じ token 列を1 tokenずつ `forward_batch` し、同じ行を保存します（`engine/src/inkling2/ink_main.cpp:382-408`）。
6. 各比較行について、1-token 側を参照分布として batch 側との KL divergence と top-1 一致を計算します。全比較行の統計に加え、モデルの `swa_win` 以上の位置だけの統計も出力します（`engine/src/inkling2/ink_main.cpp:409-438`）。

## 適用条件と副作用

- `--ring-check` 自体はモデルを指定しませんが、実行時に `InkModelFile::open` へモデルパスが渡されます。モデルパスを指定しない場合も open を試み、失敗すると `open: ...` を stderr に出してコード 1 になります（`engine/src/inkling2/ink_main.cpp:376-381,870-871`）。
- モードは共通 CLI の既存モード分岐に従います。先行するモード指定が有効な場合は ring-check は実行されません。後続の `--batch-check`、`--spec-check`、通常生成とは分岐上排他的です（`engine/src/inkling2/ink_main.cpp:1039-1071`）。
- この処理はモデルをロードして backend の slot と logits 用メモリを確保し、prompt 全体を2通りで推論します。診断のための GPU または CPU 計算を行います。ring-check 関数内にファイルへの書き込みはありません（`engine/src/inkling2/ink_main.cpp:376-408,435-441`）。
- `INK_RING_CHECK_BATCH` は正数の場合に一括 forward の piece size を変更します。未設定、0、負数、または `atoi` の結果が正数でない場合は 4096 が使われます（`engine/src/inkling2/ink_main.cpp:385-386`）。
- stride の受理範囲、token ID がモデルの語彙内かの事前検証、prompt 長と context 上限の明示的な検証は、このオプション周辺の parser/dispatch では確認できません。後段の backend/model 層での制約や追加エラー内容は、この範囲では断定しません（`engine/src/inkling2/ink_main.cpp:376-408`; `engine/src/inkling2/ink_serve.h:290-305`）。

## 出力とエラー

- 比較完了時は stdout に token 数、piece size、比較行数、stride、`swa_win`、backend 名、全行および window 以降の KL median/max と top-1 一致率、`RESULT` を出します（`engine/src/inkling2/ink_main.cpp:435-440`）。
- window 以降の比較行がない場合は成功扱いです。それ以外は window 以降の KL median が `0.02` 未満かつ top-1 一致率が `90%` を超える場合に `ok`・終了コード 0、それ以外は差異メッセージ・終了コード 1 です（`engine/src/inkling2/ink_main.cpp:439-441`）。
- モデル open 失敗は `open: ...`、backend 初期化または slot 確保失敗は `init: ...`、batch forward 失敗は `forward: ...`、1-token forward 失敗は `step: ...` を stderr に出し、いずれもコード 1 です（`engine/src/inkling2/ink_main.cpp:379-381,397,406`）。
- ring-check 用の `--prompt-ids` 欠落または解析失敗は `--ring-check needs --prompt-ids ...` を stderr に出しコード 2 です（`engine/src/inkling2/ink_main.cpp:1045-1049`）。`--prompt-ids @file` の読込失敗は上記の parser 側エラーになります（`engine/src/inkling2/ink_main.cpp:959-962`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:842,845-849,968-969` — 値の初期値、必須引数処理、option parser。
- `engine/src/inkling2/ink_main.cpp:957-963` — `--prompt-ids` の文字列/`@file` 読込。
- `engine/src/inkling2/ink_serve.h:290-305` — token ID リスト解析。
- `engine/src/inkling2/ink_main.cpp:1039-1052` — モード優先順、正数判定、prompt 必須判定、ring-check 呼び出し。
- `engine/src/inkling2/ink_main.cpp:376-441` — モデル/ backend 初期化、一括・逐次 forward、比較指標、標準出力、終了コード。
- `engine/src/inkling2/ink_main.cpp:385-386` — 比較用 batch size と `INK_RING_CHECK_BATCH`。
