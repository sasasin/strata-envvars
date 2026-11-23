# `strata-hy4-metal --prof`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（HY4-Flash の Metal runner） |
| オプション | `--prof` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

prefill と通常の逐次 decode で、モデル処理の主要区間ごとの GPU 実行時間を集計して stderr に表示します。区間ごとに dispatch 群を実行・集計するため、単に既存処理の時計を読むだけではなく実行の分割方法も変わります。

## 使い方

```sh
strata-hy4-metal --model ./model.strata --tokens ./prompt.ids --gen 16 --prof
```

`--tokens` は整数 token ID を並べたファイルです。通常の offline 推論で指定し、`--gen` を付けると prefill に加えて逐次 decode の区間集計も出力します。

## 値と既定値

- 引数 parser は `--prof` を見つけると `prof = true` にするだけで、値を読みません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1522`）。既定値は `false` です（同 `:1490-1491`）。
- 同じ指定を繰り返しても真偽値を再設定するだけです。直後に値らしい別引数を置くと、その引数は別 option として処理され、未知ならエラーになります（同 `:1504-1522`, `:1603-1608`）。
- このフラグ自体に数値範囲や追加 validation はありません。通常の offline 経路にはモデルが必要で、token ファイルが空または読めない場合は token 数 0 として `no tokens` で終了します（同 `:1611-1614`, `:1676-1704`）。

## 実行時の動作

- runner に `prof` が渡され、各 `forward_chunk` の開始時に `seg_mode = prof || seg_force` となります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1291-1296`, `:1720-1728`）。segmented mode では `part()` が保留中の dispatch 群を `cx.run_graph` で実行し、その時間を `gpu_total` と区間別 accumulator `pacc` に加えます（同 `:446-455`）。
- 区間は attention の `attn_swa(30)` / `attn_sparse(12)`、MLP の `mlp_dense(1)` / `moe(41)`、Engram の `engram(4)`、出力 head などです（同 `:1128-1129`, `:1142-1144`, `:1240-1246`, `:1318-1320`, `:1347-1349`）。レポートは区間の累積時間、step あたり時間、呼び出し数と合計を stderr に出し、出力後に accumulator を消去します（同 `:1371-1383`）。
- prefill 後に `[gpu prefill]` 集計を出します。`--gen` による通常 decode では、終了時に `[gpu decode]` 集計も出します（同 `:1812-1817`, `:1944-1974`）。
- `--prof2` を使うと parser が `prof` と `prof2` の両方を有効にし、`op()` に置かれた細分区間でも dispatch 群を分割します（同 `:1521-1522`, `:456-456`）。`--seg` も区間実行を有効にしますが、`prof` を有効にしない限りこの集計レポートは出ません（同 `:1524`, `:1295`, `:1815`, `:1971`）。`--prof3` は別の kernel 単位計測経路です（同 `:1529`, `:1961-1964`）。

## 適用条件と副作用

- この集計は offline 推論経路で使われます。`--load-only` は runner 初期化前に終了し、`--serve` は serve handler に移るため、どちらもこの runner の `--prof` 集計箇所には到達しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1675`, `:1715-1728`）。
- `--prof` は `seg_mode` を有効にし、prefill の通常バッチ実行（7 層ごとのまとめ実行）を抑止します。また Engram の先読みを GPU 処理と重ねる条件からも外れます（同 `:1304-1314`, `:1326-1328`）。したがって計測結果は profiling 有効時の区間分割経路の値です。
- このオプション自体はファイルを書き出しません。通常の推論に伴う出力ファイルは別処理で、生成時の `gen_ids.txt` や最後の `top5.txt` は `--out` のディレクトリに書かれます（同 `:1975-1980`）。

## 出力とエラー

- 集計行は `fprintf(stderr, ...)` による stderr 出力です。prefill の各 chunk 進捗・総時間も stderr に出て、生成 ID は stdout に出ます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1371-1382`, `:1812-1817`, `:1970-1974`）。
- 未知の option は `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出し、終了コード 2 です（同 `:1603-1608`）。モデル読み込み等、後続処理の失敗は `--prof` 固有ではなく、該当処理のエラー経路に従います。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1529` — option parser、初期値、`--prof2` / `--prof3` / `--seg` との区別。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:446-479`, `:1291-1328` — 区間実行・時間 accumulator と segmented mode の適用。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1371-1383`, `:1812-1817`, `:1944-1974` — 集計内容、prefill / decode の出力箇所。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1704` — `--load-only` / `--serve` の分岐と token 入力条件。
- `docs/cli/README.md:1358-1424` — 対象コマンド階層と `strata-hy4/metal/--prof.md` の索引登録。
