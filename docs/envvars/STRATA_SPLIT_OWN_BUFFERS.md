# `STRATA_SPLIT_OWN_BUFFERS`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

複数 GPU の layer split で、各 GPU に prompt 用バッファを確保できる空き VRAM があるとき、expert cache の末尾を prompt 用に貸し出す代わりに、そのバッファを GPU 自身の空き領域に置けるようにします。主に `--serve` の split prompt 経路に効きます。値が無効でも、cache から貸せる slot がないなどの理由で通常の探索が loan なしを選ぶ場合は、prompt が自前のバッファを使うことがあります。この変数は、そのような全経路で loan を禁止するスイッチではありません。

## 値と判定

実装は文字列を数値変換せず、設定値の先頭文字だけを確認します。

| 値 | `own_ok` | 判定 |
|---|---:|---|
| unset | true | 空き VRAM による own-buffer 判定を許可 |
| 空文字 | true | 先頭文字は `\0` であり、`'0'` ではない |
| 先頭文字が `0` | false | 例: `0`, `0abc`。VRAM が十分でも、この変数による loan 回避はしない |
| その他の文字列 | true | 例: `1`, `true`, `false`, `abc`。先頭文字が `0` でないため許可 |

大文字小文字、空白、文字列全体、数値としての妥当性は検査されません。値が有効でも、下記の空き VRAM 条件を満たさなければ own-buffer には切り替わりません。

## 有効になる条件

- resident RAM モードで lend region を準備する箇所では、`--serve`、複数 GPU、stage の存在に加え、`pf_borrow`、resident source (`d_res != nullptr`)、正の prefill chunk が必要です。条件を満たす場合も、GPU ごとの expert cache に slot があり、対象 layer 範囲が空でないときにだけ判定します。
- 通常の split serve の prompt chunk 設定では、複数の `PfPart` がある場合に判定します。各 GPU について、空き VRAM が prompt バッファ必要量に 1.5 GiB を加えた量以上なら loan を取り消します。
- VRAM 情報取得に失敗したときは、own-buffer 優先の判定を適用しません。resident RAM 側は lend region の計算へ進み、通常 serve 側は既に設定された loan を維持します。
- これらの判定は layer split の各 part ごとに行われます。単一 GPU の loan の扱いを変更しないことは、通常 serve の実装コメントにも明記されています。

## 実行時の詳細

環境変数は `src/program/generate.cpp` 内の2箇所で、別々の関数ローカル `static const bool` として評価されます。各箇所は初めて到達した時点で値を読み、その後は再評価しません。したがって、プロセス稼働中に環境を書き換えても、既に初期化された判定には反映されません。2箇所の初回到達時点が異なる場合、それぞれ別に初期化されます。

resident RAM モードでは、条件を満たし `cudaMemGetInfo` が成功して空き VRAM が必要量以上なら、その part の lend region を作りません。必要量は `Prefill::bytes_needed(...)` と 1.5 GiB の合計です。通常 serve では、同じ余裕条件を満たす part の `first` と `first_now` を `-1` にし、その part の cache slot を借りないようにします。ログは `CUDA%d keeps its own prompt buffers (... free): no loan` です。環境変数を `0` で始める値にすると、この2つの任意の loan 回避判定が無効になります。

`docs/MULTI_GPU.md` の「Short prompts on a split」は、空き VRAM がある card が自前 prompt buffer を維持する仕組みと測定値を説明しています。ただし同節の `STRATA_SPLIT_OWN` は全 card の buffer 選択を行う別変数であり、この文書の `STRATA_SPLIT_OWN_BUFFERS` と同一ではありません。測定値はこの環境変数単独の効果として扱っていません。

## 根拠

- `src/program/generate.cpp:6752-6790` — resident RAM モードにおける値の判定、part ごとの空き VRAM 条件、lend region 作成。
- `src/program/generate.cpp:7180-7205` — 通常の split serve における値の判定、1.5 GiB の余裕条件、loan の取り消し、ログ。
- `src/program/generate.cpp:7226-7257` — loan が残る場合の表示と、loan がない場合の表示。
- `docs/MULTI_GPU.md:76-83` — split prompt の own-buffer 方針と、別変数 `STRATA_SPLIT_OWN` の説明・測定条件。
