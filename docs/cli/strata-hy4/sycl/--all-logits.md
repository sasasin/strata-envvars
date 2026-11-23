# `--all-logits`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--all-logits` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

通常の token-file 実行で、入力 token の最終 chunk について、最後の token だけでなく複数 token 位置の logits を計算して top-5 表示の対象にします。`--dump` も指定すると、同じ行の logits を `logits.npy` に保存します。名称にかかわらず、複数 chunk に分割された入力全体の logits を一度に保存する動作ではありません。

## 使い方

```sh
# 入力が1 chunk に収まる通常実行。--dump を付けて logits.npy も保存する
strata-hy4-sycl --model model.strata --engram Engram.strata --tokens ids.txt --all-logits --dump --out ./run
```

この例は `--out` で指定したディレクトリに `logits.npy` と `top5.txt` を出力します。出力先に同名ファイルがある場合は書き換えられます。

## 値と既定値

- `--all-logits` は値を取らず、指定すると内部フラグ `all_logits` が `true` になります。省略時は `false` です。parser は重複指定も受理し、同じ `true` のままです（`engine/src/hy4flash/sycl/sy_main.cpp:99,169`）。
- 値の形式や数値範囲の validation はありません。値を続けて書く構文ではなく、続く文字列は通常の引数として解析されます。未知の引数は `unknown arg` を stderr に出し、終了コード `2` で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:190-197`）。
- logits バッファの行数は `max(8, all_logits ? min(Tc, max(T0, 1)) : 8)` で決まり、`Tc` は `--chunk` の正値または GPU メモリに応じた既定値、`T0` は入力 token 数です（`engine/src/hy4flash/sycl/sy_main.cpp:276-283`）。

## 実行時の動作

token-file 実行では各入力 chunk の forward を行いますが、head の計算と logits の host copy は最終 chunk だけに行います。`--all-logits` が有効で speculative mode でない場合、最終 chunk 内の先頭位置から logits を計算します。省略時、または speculative mode の場合は最終 token 位置だけを計算します（`engine/src/hy4flash/sycl/sy_main.cpp:344-365`）。`Runner::head` は指定された `[first, T)` の各位置について LM head を実行します（`engine/src/hy4flash/sycl/sy_graph.h:1435-1469`）。

したがって、入力全体が一 chunk に収まると全入力位置が対象になります。入力が複数 chunk に分かれると、それ以前の chunk は head を計算せず、最終 chunk の位置だけが対象です。`--gen` を併用しても、このフラグが生成中の各 token の logits をファイルへ追記することはありません。prefill 後の生成では最後の prefill logits 行から次 token を選び、decode は各回1行で進みます（`engine/src/hy4flash/sycl/sy_main.cpp:527-551`）。

選択された各行から top-5 が作られ、標準出力へ表示されるほか、正常終了時に `--out`（既定 `.`）の `top5.txt` に書かれます。`--dump` を指定した場合は、`logits.npy` に shape `(n, vocab)`、little-endian float32、C 順で保存します。ここで `n` は最終 chunk から選ばれた行数です（`engine/src/hy4flash/sycl/sy_main.cpp:93,155,355-363,603-606`; NPY writer: `engine/src/hy4flash/sycl/sy_graph.h:52-71`）。

## 適用条件と副作用

- `--serve` 経路ではフラグ自体は parser に認識されますが、server 用 `ServeOpts` には渡されず、そこでの効果は確認できません。server 側のオプション設定・返答への logits 露出をこのフラグが変更する根拠はありません（`engine/src/hy4flash/sycl/sy_main.cpp:215-249`）。
- `--draft dfly2` かつ `--gen` が正の場合は `spec_mode` となり、prefill では最終 token のみを head 計算します。speculative decode 中も `--all-logits` による複数行出力はありません（`engine/src/hy4flash/sycl/sy_main.cpp:279,353-357,379-387`）。
- `--dump` なしでは `logits.npy` は書きません。`--dump` ありでは `out_dir + "/logits.npy"` を `fopen(..., "wb")` で開くため、既存ファイルを切り詰めて上書きします。保存関数はファイルを開けない場合に黙って戻り、書き込み戻り値も検査しません。ディレクトリ作成は確認できません（`engine/src/hy4flash/sycl/sy_main.cpp:363`; `engine/src/hy4flash/sycl/sy_graph.h:52-71`）。
- 指定した行数分の logits 用 GPU バッファを確保するため、行数が大きい場合は追加メモリを使います。確保失敗時の具体的な診断・終了経路はこのオプション固有には定義されていません。

## 出力とエラー

- `--model` がなく通常経路へ進んだ場合は usage を stderr に出し、終了コード `2` になります。通常実行で token file の読込結果が空の場合は `no tokens` を stderr に出し、`2` で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:250-254,266-274`）。
- モデル読込、初期化、expert setup、forward の失敗はそれぞれ `load:`, `init:`, `experts:`, `forward:` を stderr に出し、`1` で終了します。SYCL exception は `SYCL exception:` と stderr に出し、`4` で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:261-265,294-307,348-351,612-615`）。
- `--dump` の NPY 出力先を開けない・書き込みに失敗する場合、writer はエラーを報告せず処理を続けます。保存成功は終了コードから判定できません（`engine/src/hy4flash/sycl/sy_graph.h:60-71`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:99,169` — フラグの初期値と parser 登録。
- `engine/src/hy4flash/sycl/sy_main.cpp:276-283,528` — 入力長と chunk に基づく logits 行数、GPU バッファ確保。
- `engine/src/hy4flash/sycl/sy_main.cpp:344-365` — 最終 chunk の head 計算、選択行の copy、top-5 と `logits.npy` 出力。
- `engine/src/hy4flash/sycl/sy_graph.h:1435-1469` — head が `[first, T)` を logits に計算する実装。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-249,279,379-387,527-551,603-616` — serve/speculative 条件、生成経路、`top5.txt` と終了経路。
- `engine/src/hy4flash/sycl/sy_graph.h:52-71` — NPY 形式とファイル open/write の扱い。
