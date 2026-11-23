# `--ab`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--ab` |
| 別名 | なし |
| 値 | 整数。A/B 比較の反復回数として `atoi` で読み取る |

## 役割

Metal 版 HY4 の speculative decoding が有効なオフライン生成で、通常生成と DFly2 speculative 生成を複数回実行して速度と生成 token の一致を比較します。引数値が正数のときだけ比較ループに入り、通常生成のあと speculative 生成を行います。

## 使い方

```sh
strata-hy4-metal --model ./model.strata --tokens ./prompt.ids --gen 64 --draft dfly2 --ab 3
```

モデルと token ID 入力を指定して最大 64 token を生成し、比較を 3 回実行する例です。実行時には Metal 対応の実行環境と有効なモデル・入力ファイルが必要です。

## 値と既定値

- 省略時は `ab_rounds` が `0` のままなので、A/B 比較ループを実行しません。
- 指定値は `atoi` で整数化されます。正数ならその回数だけ反復し、`0`、負数、または整数として読めない値は比較ループを有効にしません。
- parser に範囲検証や不正値エラーはありません。値が指定されるたびに `ab_rounds` を代入するため、同一引数列で複数回指定した場合は最後の値が使われます。

## 実行時の動作

- 比較ループに入るには speculative mode が成立している必要があります。speculative mode は、`--gen`、`--bench-m`、`--par-m` のいずれかが正数で、`--draft off` でなく、モデルに DFly2 drafter の重みがあり、Runner の chunk サイズ `Tc` が 16 以上で、`--all-logits` がなく、画像入力がない場合に有効です。
- ただし `--bench-m` と `--par-m` の正数指定では、A/B 分岐より前の各専用処理が実行後に return するため、`--ab` の比較ループには到達しません。通常の A/B 比較には `--gen` を指定します。`--draft` の既定値は `auto` です。
- `--ab` が正数なら Runner の `ring_slack` を `gen + 64` に設定し、KV ring の容量計算に使います。これは prefill の最終 chunk を再実行して状態を復元する間に decode が窓領域を壊さないための余裕です。`--ring-slack` は serve 用設定に渡される値で、オフライン Runner ではこの `--ab` による設定が使われます。
- 各反復で prefill 状態を復元して通常生成し、もう一度復元して DFly2 生成します。`HY4_AB_SKIP_PLAIN` 環境変数が設定されていると通常生成を省略します。その場合も speculative 側は実行されますが、通常生成との比較値は成立しません。
- 標準出力には各反復の速度、speedup、iteration 当たり token 数、accepted/verify-step、通常生成との共通 prefix 長を出力します。speculative decoder の詳細レポートは標準エラーに出力します。
- 最初の反復では `--out` で指定したディレクトリ（既定 `.`）に `gen_ids_plain.txt` と `gen_ids_spec.txt` を書き込みます。`std::ofstream` による作成のため、同名ファイルがあれば切り詰めて上書きします。ファイルを開けたかどうかは確認していません。

## 適用条件と副作用

`--ab` 自体は speculative mode を強制しません。条件を満たさない場合は比較処理に入らず、通常の生成・他の指定モード等の処理に進みます。`--draft dfly2` を指定していて `--gen > 0` なのに speculative mode が不成立の場合は、stderr に利用不能の理由を示すメッセージを出しますが、この警告箇所では終了せず、通常経路へ続きます。

正数の反復では通常生成と DFly2 生成の両方が走るため、その分の計算時間を使います。初回に前述の 2 ファイルを書き込み、既存ファイルを上書きします。空き容量、書き込み先の存在・権限、ファイル書き込み失敗時の終了動作は、この出力箇所では検査されません。

## 出力とエラー

speculative 実行が `finish == "error"` で終了した場合は `spec: <内容>` を stderr に出して終了コード 1 になります。通常生成の forward が失敗した場合も `forward: <内容>` を stderr に出して比較ループを中断し、終了コード 1 になります。`--ab` の値そのものに対するエラー経路はありません。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1504` — Metal CLI の `main`、`ab_rounds` の既定値 0。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1572` — `--ab` の parser。`atoi` で値を取り、範囲検証はしない。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:614` — `ring_slack` を KV ring 容量計算に使用。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1648` — `--ring-slack` の値は serve options に設定される。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1734` — `ab_rounds > 0` のとき offline Runner の `ring_slack` を `gen + 64` に設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1769` — DFly2 重みの有無、speculative mode の適用条件と初期化失敗経路。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1819-1840` — 通常生成ループと forward 失敗時のエラー。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1898-1927` — A/B 反復、`HY4_AB_SKIP_PLAIN`、比較結果、初回の ID ファイル出力。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1929-1944` — A/B が無効なときの通常 speculative 生成と出力経路。
