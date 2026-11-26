# `STRATA_METAL_DRAFT_VOCAB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal backend が MTP または DFlash2 の draft head に使う token subset ファイルを指定する。ファイルには 4 byte の `int32_t` token ID を並べる。Metal の MTP 読み込みではこの変数が設定されていれば、モデル横の `rt/draft_vocab.bin` と build 同梱 `data/draft_vocab.bin` より優先される。値が正確に `full` のときは subset ファイルを開かず全 vocabulary を使う（`engine/metal/src/engine/window.cpp:2569-2582`）。

`--draft dflash2 --draft-fallback none` の Metal 起動では、別途この変数を DFlash2 用 subset の候補としても解決する。subset が使われると DFlash2 の head は対象行だけを gather し、その行数で logits/head を作る。subset が空なら全 head rows を使う（`engine/src/program/generate.cpp:6505-6527`; `engine/metal/src/engine/dflash2.inc:297-327,377-380`）。これは setup 用 `--draft-vocab` とは別の実行時変数である。

## 値と判定

| 経路 | unset | 設定時に有効になる値 | 無効・空の値 |
|---|---|---|---|
| Metal MTP load | GGUF の隣の `rt/draft_vocab.bin` が開ければそれ、そうでなければ build の `data/draft_vocab.bin` | `full`（大文字小文字を区別する完全一致）で全 vocabulary。その他の値はそのままファイルパスとして `fopen(..., "rb")` に渡す | 明示的な空文字も「設定あり」と判定され、`vp` は空のまま。`fopen("")` は失敗し、既定ファイルへは戻らない。パスが開けない場合も静かに空 subset となる |
| DFlash2 solo の Metal 解決 | `--mtp DIR/draft_vocab.bin`、次に Metal の packaged default を確認 | `full` は whole-head を許すフラグ。その他は `draft_vocab_default()` が返す packaged default のパスを候補にする | `draft_vocab_default()` は未設定・空・`full` のいずれでも packaged default パスを返す。したがって `full` でも `df2_vocab_resolve` は先に既存の MTP 側ファイル、続いて既存 packaged default を採用し、どちらも存在しない場合にのみ whole-head へ進む |
| DFlash2 bind 時の追加 fallback | packaged `data/draft_vocab.bin` | 空でない値かつ `full` 以外なら、その値をファイル名として読む | 未設定時は packaged default。空文字は `fopen` 失敗。`full` のときは追加ファイル読込をせず全 head にする |

どの経路も数値変換、trim、空白除去、大小文字変換はしない。パスは文字列全体を使う。subset ファイルからは 4 byte 読める間 ID を読み、`0 <= id < n_vocab_` の要素だけ採用する。末尾の 4 byte 未満は読まれず、無効 ID は捨てる。値 `0`、`1`、`true`、`false` は特別な真偽値ではなくファイル名であり、`full` 以外は上記のファイル読み込み経路になる（`engine/metal/src/engine/window.cpp:2574-2582,2863-2865,3595-3603`; `engine/metal/src/engine/dflash2.inc:299-315`）。

## 有効になる条件

- 実際に Metal backend を組み込んだ実行ファイルであること。DFlash2 solo の packaged-default / whole-head 解決呼び出しは `STRATA_GPU_METAL` build macro の内側にある。CUDA/HIP/SYCL にはこの Metal getter 経路がなく、この名前を使った Strata-side resolution は確認できない（`engine/src/program/generate.cpp:199-208,6510-6521`）。
- MTP の subset 選択は `Window::mtp_load` が呼ばれる経路で行われる。`mtp_load_pending` は登録済み MTP path が空でない場合にこのロードを実行する（`engine/metal/src/engine/window.cpp:3704-3729`）。
- DFlash2 solo の事前検証は `--draft dflash2`、`--draft-fallback` が `mtp` 以外、`--spec >= 2`、`--draft-model` があり、かつ MTP dir または `--mtp-draft-vocab` が指定された場合に限る。`--draft-fallback mtp` ではこの solo 解決を通らず、MTP 側の読込規則が適用される（`engine/src/program/generate.cpp:6494-6529`）。
- solo の事前検証は `Dflash2Drafter::head_native()` が false の場合だけ行われる。true の場合は解決を省略し、Metal bind 側で subset を消して native whole-head にする（`engine/src/program/generate.cpp:6510-6527`; `engine/metal/src/engine/dflash2.inc:317-323`）。
- `df2_vocab_resolve` は明示 `--mtp-draft-vocab` / `--mtp DIR/draft_vocab.bin` の既存ファイルを packaged default より先に採用する。`full` は存在する明示ファイルを上書きしない。優先順位は resolver の存在確認順による（`engine/include/strata/spec/draft_vocab.hpp:23-32`）。
- MTP 通常経路では CLI の `--mtp-draft-vocab` が `MtpDrafter::set_draft_vocab` に渡るが、Metal build の `MtpDrafter::bind` は `STRATA_GPU_METAL` で早期 return する。Metal window の subset 読み込みは独立して環境変数を選ぶため、この経路では CLI の値を window 読み込みへ渡す処理を確認できない（`engine/src/program/generate.cpp:8248-8253`; `engine/include/strata/core/mtp.hpp:77-79`; `engine/src/core/mtp.cpp:908-914`; `engine/metal/src/engine/window.cpp:2569-2577`）。DFlash2 solo では CLI path が resolver の最初の候補で、環境変数由来の packaged path はその後に検討される。

## 実行時の詳細

Metal MTP では `Window::mtp_load` の初期化時に一度環境を読み、選んだファイルをその場で開いて `dvocab_` に保持する。起動後に環境を書き換えても、既に読み込んだ subset は再評価されない。unset 時は `rt/draft_vocab.bin` の存在確認を `fopen` で行い、無ければ packaged default を使う。設定時はファイルの存在確認をせず、`full` 以外の値をそのまま開く。失敗・全件無効・空ファイルなら `dvocab_` は空のままで、MTP head の subset copy も作られず、計算側では `dvocab_` が空のとき `n_vocab_` 行すべてを使う（`engine/metal/src/engine/window.cpp:2569-2594,2863-2865`）。

DFlash2 solo では generate 起動時に `draft_vocab_default()` と `draft_vocab_whole_head()` がそれぞれ環境を読み、filesystem existence check を行って subset の path / whole-head 許可を決める。bind 時には必要に応じて `df2_bind` が環境を再読するため、これらの読み取り間で環境を変更すれば結果が一致しない可能性がある（`engine/metal/src/engine/window.cpp:3593-3603`; `engine/src/program/generate.cpp:6510-6527`; `engine/metal/src/engine/dflash2.inc:284-315`）。

`df2_bind` はまず呼び出し元から渡された vocab file を読み、空なら MTP の `dvocab_`、それも空なら環境指定または packaged default のファイルを試す。`vocab_file == "full"` の場合はこの fallback を行わない。subset を得た場合は、`mhead_` と `use_map` を使って対象 rows を gather する。空 subset では `d.nd = n_vocab_`、`use_map = false` となり全 head を使う。`STRATA_DF2_HEAD=native` はこの値選びとは別に、DFlash2 の Q8_0 head copy を止めて vocab map を消す（`engine/metal/src/engine/dflash2.inc:297-327,362-380`）。

ファイルを開けないこと自体は MTP load のエラーにせず空 subset として進む。一方 DFlash2 solo の事前検証では必要なファイルが存在せず whole-head も許可されなければ、stderr に resolver の理由を出して終了コード `2` で戻る。DFlash2 bind は空 subsetでも進み得るが、head 行数が top-k の上限を超える場合は `dflash2: the head has too many rows for the top-k` を返して bind に失敗する（`engine/src/program/generate.cpp:6518-6528`; `engine/include/strata/spec/draft_vocab.hpp:26-32`; `engine/metal/src/engine/dflash2.inc:381`）。

## ログと測定値

MTP の vocab path 選択やファイル open 失敗専用のログはない。DFlash2 solo が packaged default を resolver で選ぶと `strata generate: --draft dflash2: no draft vocabulary in the MTP folder: using the packaged default subset %s` を stderr に出す。bind 成功時は `strata metal: DFlash2 drafter ready (..., %lld-token draft head %s), in ... ms` を stderr に出し、使われた draft head の token 数と `as Q8_0` / `as Q8_0, the whole head` / `native` を示す（`engine/src/program/generate.cpp:6523-6527`; `engine/metal/src/engine/dflash2.inc:412-413`）。

`docs/DETAILS.md:382-386` の `--draft-vocab` は setup が subset を作る説明であり、この実行時環境変数の判定・優先順位・ログを説明する資料ではないため、環境変数の効果や測定値の根拠にはしていない。

## 根拠

- `engine/metal/src/engine/window.cpp:2569-2594,2863-2865` — Metal MTP の env 読み取り、既定 path、file parse、subset copy と全 head fallback。
- `engine/metal/src/engine/window.cpp:3593-3603` — DFlash2 solo 用 getter の未設定・空・`full` 判定。
- `engine/src/program/generate.cpp:6505-6529` — DFlash2 solo の適用条件、resolver 呼び出し、終了・fallback ログ。
- `engine/include/strata/spec/draft_vocab.hpp:23-32` — subset path と whole-head の優先順位、missing-file error。
- `engine/metal/src/engine/dflash2.inc:284-327,362-381,412-413` — bind fallback、head rows、失敗・成功ログ。
