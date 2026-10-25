# `--batch`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの root 引数） |
| オプション | `--batch` |
| 別名 | `--slots` |
| 値 | 整数 `N`。同時に保持する生成 slot 数。既定値 `0`（無効） |

## 役割

`--serve` モードで複数の会話を batch slot に保持し、各 batch window で各 slot の token をまとめて decode します。設定数の slot session を GPU ごとに作成するため、slot 数と各 session の大きさに応じて VRAM を使い、通常は expert cache に使える VRAM が減ります。コマンドは要求された数を無条件に確保するのではなく、実行可能数に調整するか、batch を無効にして通常の逐次 serve を続けます（`src/program/generate.cpp:5272-5277`, `5386-5440`）。

## 使い方

```sh
strata --pack /path/to/model.strata --serve --batch 4
```

`--pack` にはこの engine が扱えるモデル pack を指定します。`--batch` には `--serve` が必要です。serve クライアントは engine の行指向プロトコルを使い、batch admission には `BGEN <slot> <max_new> ...`、slot からの token 出力には `BT <slot> <id>`、終了には `BDONE ...` が使われます（`src/program/generate.cpp:2637`, `12000-12015`, `11643-11650`; `docs/BATCHING.md:551-561`）。

## 値と既定値

- `--batch N` と `--slots N` は同じ `o.batch` に代入されます。既定値は `0` で、batch slot を作りません（`src/program/generate.cpp:658-661`, `2609-2610`）。
- parser は次の引数を `std::atoi` で整数化します。引数自体が欠けている場合は stderr に `<option> needs a value` を出して終了コード `2` で終了します。数値形式・範囲の独自 validation は parser にありません（`src/program/generate.cpp:2416-2421`, `2609-2610`）。
- 両方の表記を複数回指定したときは parser が同じフィールドへ順番に代入するため、後の指定値が残ります（`src/program/generate.cpp:2416-2421`, `2609-2610`）。
- 有効化には `N >= 2` が必要です。`N < 2`（負数を含む）や `--serve` なし、同じ GPU に重なる layer split (`split_same`) では warning を stderr に出し、batch を `0` に戻して続行します（`src/program/generate.cpp:5341-5347`）。
- window が処理できる row 数または GPU memory に収まらない場合、slot 数を縮小します。GPU ごとの session 確保数が 2 未満なら batch を無効にします。従って指定値が実際の slot 数になるとは限りません（`src/program/generate.cpp:5323-5338`, `5348-5354`, `5386-5440`）。

## 実行時の動作

有効な場合、各 GPU/stage に model context と layer 範囲に応じた session state を slot 分確保して初期化します。これらの確保は expert cache の sizing より前に行われるため、`--expert-cache auto` は slot session を差し引いた後の余地を使います。起動時に実際の slot 数、各 session の容量、CUDA device ごとの空き VRAM を stderr に出します（`src/program/generate.cpp:5272-5275`, `5386-5418`, `5437-5440`）。

`--batch-groups` を layer split と併用すると slot 群を stage 間で pipeline できます。指定がない場合の group 数は layer split、`--batch-mtp`、`--adapt-async`、build 条件などで解決され、`--batch-groups G` が slot 数を割り切れない場合や layer split がない場合は 1 group に戻ります。window の上限を超える要求数も group/window 条件に応じて縮小されます（`src/program/generate.cpp:5280-5297`, `5323-5338`, `5357-5384`）。

`--batch-mtp` または `STRATA_BATCH_MTP` を組み合わせると、条件が整う場合に各 slot が MTP proposal を検証しますが、この機能は batch 自体とは別の opt-in です。`--serve`、2 slot 以上、`--mtp`、`--spec` 2 以上などの条件が満たされない場合は警告して MTP だけを無効にします。pipeline group など他の条件との相互作用もあります（`src/program/generate.cpp:5299-5321`, `11739-11748`）。

## 適用条件と副作用

- `--serve` 以外の実行モードでは使われず、warning を出して逐次実行に戻ります。1 slot の指定も無効化されます（`src/program/generate.cpp:5341-5347`）。
- GPU ごとに `session_bytes(...)` 相当の容量を確保し、初期化時に CUDA allocation が失敗した場合は stderr に失敗 device、slot、必要量、空き量を出して、その device で確保できた数に縮小します。2 slot 確保できなければ全 slot state を捨てて無効にします（`src/program/generate.cpp:5386-5425`）。
- slot は各会話の状態を持ち、追加要求は空き slot を使います。空き slot がない、slot 番号が範囲外、slot が使用中、または `max_new` が不正な `BGEN` は stdout に `ERR BGEN: ...` を出して要求を受け付けず、serve loop は継続します（`src/program/generate.cpp:11345-11346`, `12000-12014`）。
- session file の save/restore は batch と併用できず、要求時に拒否されます。また request ごとの `logit_bias` は continuous batching 中はサポートされず、`ERR logit_bias: continuous batching is not supported` を stdout に出してその request をスキップします（`src/program/generate.cpp:12094-12100`, `12369-12375`）。

## 出力とエラー

- startup 時に slot session の確保数や VRAM 消費を stderr に出します。row/window 上限、serve 条件、slot 確保不足など、batch を調整する条件は原則 warning を出して engine 自体の逐次 serve を継続します（`src/program/generate.cpp:5341-5354`, `5400-5440`）。
- engine の stdout `INFO` 行には `batch_slots=N` が含まれ、`N` は調整後の slot 数です（`src/program/generate.cpp:11078-11104`）。batch protocol は stdout に `BT <slot> <id>` と `BDONE <slot> ...` を出力します（`src/program/generate.cpp:11643-11650`, `11823-11833`）。
- 実行中の batch window launch が失敗した場合は stdout に `ERR <内容>` を出し、serve 処理は失敗として戻ります。slot admission の session copy が失敗した場合は stderr に `strata serve: batch admission failed: ...` を出し、その slot の cache を破棄して継続しない形にします（`src/program/generate.cpp:11890-11903`, `15390-15398`）。

## 根拠

- 索引と scope: `docs/cli/README.md:1128-1143`。`strata-engine` root の文書であり、`--slots` alias を同じ文書にまとめる。
- parser と alias: `src/program/generate.cpp:2416-2421`, `2609-2610`。
- 既定値、serve 条件、縮小・VRAM session 確保: `src/program/generate.cpp:658-661`, `5272-5275`, `5323-5354`, `5386-5440`。
- batch protocol、request validation と出力: `src/program/generate.cpp:11345-11350`, `11643-11650`, `11890-11903`, `12000-12015`, `15390-15419`。
- 関連する利用者向け説明: `docs/BATCHING.md:1-13`, `88-108`, `551-561`。この調査ではソース parser と実装を主根拠にし、性能測定値は記載していない。
- GPU/backend ごとの実際の容量、全 build 条件での最大 slot 数、Release 配布バイナリとの一致はこの調査では実行確認していない。上限・実効値は上記の実行時条件に依存する。
