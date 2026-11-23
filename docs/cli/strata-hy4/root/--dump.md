# `--dump`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root、CUDA/HIP） |
| オプション | `--dump` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

offline の Hy4 推論実行で、中間 tensor のデバッグ出力を有効にします。層ごとの Engram（該当層のみ）・attention・MLP 後の residual stream と、prefill 最終位置（または `--all-logits` 指定時は最終 chunk の全位置）の logits を NumPy float32 `.npy` として `--out` のディレクトリへ保存します。Metal と SYCL の同名オプションは別スコープであり、この文書の対象ではありません。

## 使い方

```sh
# 事前に空の出力ディレクトリを用意して、入力 token 列の中間 tensor と logits を保存
strata-hy4 --model model.strata --engram engram.strata --tokens ids.txt --out /tmp/hy4-dump --dump
```

`--out` のディレクトリは先に作成してください。通常の offline 経路では、このオプションがディレクトリを作成する処理は確認できません。

## 値と既定値

- 値を取りません。parser は `--dump` を見つけると `dump = true` にし、オプションがなければ初期値 `false` のままです。
- 複数回指定しても同じ boolean を `true` にするだけです。数値などの validation はありません。
- 値を付けて書く構文はありません。直後の引数は通常の次の CLI 引数として処理されます。

## 実行時の動作

- parser の boolean は `Runner::dump` に渡り、`Runner::dump_dir` には `--out` の値（省略時 `.`）が設定されます。層処理では dump が有効なとき `x_L<層番号>_engram.npy`（Engram が有効な該当層のみ）、`x_L<層番号>_attn.npy`、`x_L<層番号>_mlp.npy` を出力します。形状は `[T, 4, HID]` です。
- prefill の最終 chunk では logits の `[n, V]` 配列も `logits.npy` に保存します。`n` は通常 1、`--all-logits` により全位置を処理する場合は最終 chunk の全位置です。`--save-logits` も独立に同ファイルを保存する条件です。
- 出力名は固定で、NPY writer は `fopen(..., "wb")` で開くため、同じ出力先に既存ファイルがあれば上書きします。保存関数は開けなかった場合に何もせず戻り、書き込み結果も検査しません。そのためディレクトリがない、または書き込みに失敗した場合でも、dump 保存そのものについて明示的なエラーや失敗終了は確認できません。
- `--serve` 経路は `Runner` を構築する offline 処理に進まず `hy4_serve_main` を呼ぶため、この `--dump` は runner の dump 設定には反映されません。
- `--trace-m` が有効な別の診断経路では `Runner::dump` が強制的に有効になり、`--out/seqN` と `--out/win` に出力します。この経路はディレクトリを作成し、`--dump-layer` が指定されていればその層の attention 内部 buffer も追加出力します。`--dump-layer` 単独では通常の `--dump` の出力層を限定しません。

## 適用条件と副作用

- 対象は索引が `strata-hy4` root として登録する CUDA/HIP の `engine/src/hy4flash/run/hy4_main.hip.cpp` です。Metal (`hy4_metal_main.cpp`) と SYCL (`sy_main.cpp`) は別の parser・別文書です。
- offline の推論処理で GPU から host へ tensor をコピーしてファイル化するため、追加の host memory・I/O が発生します。dump 用の同期と device-to-host copy は各出力箇所で行われます。
- `--dump` が有効な場合、speculative decode の graph 利用条件の一部が無効になります（runner が dump 中でないことを graph 使用条件としている箇所）。
- 中間ファイルや `logits.npy` は固定名で作られ、既存ファイルを保護する仕組みはありません。既存データを残す必要がある場合は新しい出力先を使ってください。

## 出力とエラー

- NPY writer は float32 little-endian・C order の NPY v1 header とデータを書きます。
- `--dump` 自体の値不足エラーはありません。未知の引数は stderr に `unknown arg ...` を出して終了コード 2 になります。
- dump ファイルの `fopen` 失敗は writer 内で黙って無視されます。個々の `fwrite` の成否も確認されません。したがってファイル出力失敗が CLI の終了コードや標準エラーへどう反映されるかは、これらの箇所からは保証できません。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:347-352` — `dump` の初期値と `--out` 既定値。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-384, 485-501` — 引数値の不足処理、`--dump` parser、未知引数の失敗。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-612` — `--serve` 時に server 処理へ分岐し offline runner を経由しない。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:687-698` — `Runner` へ dump flag と出力先を設定。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:770-777` — prefill 最終 logits の保存条件と `--all-logits` による位置数決定。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1934-1942, 3431-3442` — 中間 tensor の保存条件、ファイル名、形状。
- `engine/src/hy4flash/run/hy4_graph.hip.h:77-97` — NPY writer の形式、`wb` による上書き、open/write エラー処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:795-816`、`engine/src/hy4flash/run/hy4_graph.hip.h:207-217, 2170-2183` — trace 経路での dump 強制、出力先、layer 指定時の attention 内部 dump。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:601, 856, 1049` — speculative decode の graph 使用条件で dump flag を除外。
- `docs/cli/000_cli_tools.md:11`、`docs/cli/README.md:1295` — `strata-hy4` の root scope と parser 所在、および索引の `--dump` リンク。

調査制約: 実行ファイルの `--help` は実行していません。挙動は対象 revision の parser と呼び出し箇所を追って確認しました。
