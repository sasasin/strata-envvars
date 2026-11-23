# `strata-hy4-metal --all-logits`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--all-logits` |
| 別名 | なし |
| 値 | なしのフラグ |

## 役割

オフラインの token 入力を処理するとき、通常は最後の prefill chunk の最終 token にだけ計算する logits を、その chunk 内の全 token 位置について計算します。計算した各行は top-5 出力に使われ、`--dump` または `--save-logits` も指定されていれば `logits.npy` に保存されます。このフラグ単独ではファイル保存を有効にしません。

## 使い方

```sh
strata-hy4-metal --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --all-logits
```

最後の prefill chunk 内の各 token 位置の logits を処理します。既定では `top5.txt` を出力ディレクトリに書き、logits の NPY 保存も必要なら `--dump` または `--save-logits` を併用します。

## 値と既定値

- 値を取りません。引数解析で `--all-logits` が現れると `all_logits` を `true` にします。既定値は `false` で、同じフラグを複数回指定しても同じ状態です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1504-1518`）。
- このフラグ固有の範囲検証はありません。
- 対象位置は最終 chunk の長さ `T` です。`--chunk` が正ならその値、そうでなければ通常は 4096（cold-experts モードでは 2048）を使い、入力長に合わせて実際の chunk 容量を決めます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1713-1715`）。

## 実行時の動作

オフライン実行では各 chunk を forward し、最後の chunk で `all_logits` が真なら head の開始位置を `0`、偽なら `T - 1` にします。従ってこのオプションが計算・列挙するのは**入力全体ではなく、最後の prefill chunk 内の全 token 位置**です。chunk が入力全体より短い場合、それ以前の chunk の logits 行はこの出力対象に含まれません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1790-1810`）。

計算した `n = T - first` 行は `hl` にコピーされ、各行について入力内の位置番号 `done - n + i` と上位 5 token の ID・logit が `top_out` に追加されます。オフライン処理終了時に `top_out` は標準出力と `<out>/top5.txt` に出力されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1389-1396,1802-1808,1816,1978-1981`）。

`--dump` または `--save-logits` も有効な場合、同じ `n` 行を shape `(n, vocab)` の float32 NPY として `<out>/logits.npy` に書きます。既定の `--out` は `.` です。ファイルは `fopen(..., "wb")` で作成・上書きされます。保存関数は開けない場合に黙って戻り、書き込み結果も確認しないため、保存失敗が明示的な CLI エラーになる実装ではありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:41-60,1490,1808`）。

## 適用条件と副作用

- `--serve` が指定されると、token-file によるオフライン処理より前に server 経路へ分岐します。server 設定への値の転送はなく、この経路では `--all-logits` は使用されません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1675`）。
- speculative decode の有効条件に `!all_logits` が含まれるため、このフラグを付けると DFly2 speculative mode は無効になります。`--draft dfly2` と `--gen` を併用して条件を満たせない場合、stderr に利用不可の理由として `--all-logits` が表示されます。`--draft auto` では条件から外れて plain decode になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762`）。
- logits buffer は `logit_rows × vocab × 4` byte で確保され、`--all-logits` 有効時には `logit_rows` に chunk 容量 `r.Tc` を渡します。既定動作の 1 行分より大きな buffer を使い、chunk 容量・語彙数に応じて必要メモリが増えます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:523-524,609,1713-1715,1760-1763`）。
- `--all-logits` 自体によるファイル書き込みはありません。`logits.npy` 保存は `--dump` または `--save-logits` との併用時だけです。なお `--dump` は logits 以外の中間データ出力も有効にします（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1720-1722,1808`）。

## 出力とエラー

このフラグ専用の validation error や終了コード分岐は確認できません。必要なモデルなどの読み込み・runner 初期化・forward が失敗した場合は各経路のエラーを stderr に出して終了しますが、`--all-logits` 固有の失敗条件ではありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1618-1627,1762-1764,1794-1796`）。不明な引数は stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して status 2 で終了します（同 `:1604-1609`）。

## 根拠

- parser と既定値: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1504-1518`
- chunk 容量の決定: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1713-1715`
- speculative mode との相互作用、buffer 初期化: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1763`
- 最終 chunk の行選択、top-5 集計、条件付き NPY 保存: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1790-1810`
- top-5 の行形式と最終出力: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1389-1396,1816,1978-1981`
- NPY 書き込みと open failure の扱い: `engine/src/hy4flash/metal/hy4_metal_main.cpp:41-60`
- server 分岐: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1675`
