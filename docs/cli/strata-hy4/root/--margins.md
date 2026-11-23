# `strata-hy4 --margins`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP runner） |
| オプション | `--margins` |
| 別名 | なし |
| 値 | 取らない真偽フラグ |

## 役割

オフライン生成中に各 token 選択に関係する logits 行を調べ、最大 logit と 2 番目の logit の差（top-1 − top-2）を `margins.txt` に記録します。同時に各 logits 行の値から計算した FNV-1a hash も `hashes.txt` に保存します。CUDA/HIP runner の通常 decode と DFly2 speculative decode の解析用です（`engine/src/hy4flash/run/hy4_main.hip.cpp:430, 992-1017, 1034-1049`、`engine/src/hy4flash/run/hy4_spec.hip.h:146-168`）。

## 使い方

出力先ディレクトリをあらかじめ用意し、通常の token 入力による生成で指定します。

```sh
strata-hy4 --model MODEL.strata --tokens prompt.ids --gen 8 --margins --out ./results
```

## 値と既定値

値を取りません。parser は `--margins` を読むと内部フラグ `want_margins` を `true` にします。初期値は `false` なので、省略時は margin と hash の採取・出力を行いません。値の validation はなく、複数回指定しても同じフラグを `true` にするだけです（`engine/src/hy4flash/run/hy4_main.hip.cpp:372, 430`）。

## 実行時の動作

- 通常 decode（`--draft` の既定値 `auto` はコメント上、CLI run では DFly2 を無効にする設定）では、prompt 末尾の logits 行と、生成の各 step で token 選択に使う logits 行から margin と hash を計算します。margin は logits の最大値から 2 番目の値を引いた値です。生成 step ごとの採取では logits の行を GPU から host にコピーします（`engine/src/hy4flash/run/hy4_main.hip.cpp:363, 1034-1049, 1050-1069`）。
- `--draft dfly2` で `--gen` が正数、かつ `--dfly-alloc-only` ではない場合は speculative mode になります。この場合 `Spec` に採取フラグを渡し、`Spec` は処理した logits 行から同じ margin と hash を記録します（`engine/src/hy4flash/run/hy4_main.hip.cpp:701, 992-1000`、`engine/src/hy4flash/run/hy4_spec.hip.h:149-168, 472-473`）。
- 上記の生成経路で、`--out` の出力先に `margins.txt` と `hashes.txt` を作成し、値を1行ずつ書きます。`margins.txt` は浮動小数点値、`hashes.txt` は16進表記の整数です。出力先は既定で `.` です（`engine/src/hy4flash/run/hy4_main.hip.cpp:347, 485, 1010-1016, 1097-1104`）。同じ名前のファイルがある場合、通常の `std::ofstream` の書き込み開始により内容は置き換えられます。

## 適用条件と副作用

この文書の scope は索引に記載された CUDA/HIP 実装 `engine/src/hy4flash/run/hy4_main.hip.cpp` です。Metal と SYCL は別 parser であり、このフラグが共通に適用されるとは確認していません（`docs/cli/README.md:1277-1282, 1315`、`docs/cli/000_cli_tools.md:11`）。

`--gen` が正数でなく、通常生成または speculative generation の分岐に入らない場合は margin/hash 出力処理に到達しません。`--serve` は server 処理へ移り、`--dump-dfly-batch` は batch 処理から return し、`--ab` の比較分岐も別経路で生成を行うため、このフラグによる `margins.txt` / `hashes.txt` の出力はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:611, 701, 707-708, 914, 992, 1018, 1099`）。

出力先ディレクトリはこの処理で作成されません。出力 stream の open/write 状態もコードで検査していないため、ディレクトリが存在しない場合や書き込みできない場合のエラー表示・終了コードは確認できません（`engine/src/hy4flash/run/hy4_main.hip.cpp:1010-1016, 1097-1104`）。speculative 経路では採取時に logits の device-to-host copy を追加します（`engine/src/hy4flash/run/hy4_spec.hip.h:150-153`）。

## 出力とエラー

生成処理で `finish == "error"` になると `spec: <内容>` を stderr に出して終了コード 1 で戻ります。通常 decode 中の `forward_chunk` 失敗は `forward: <内容>` を stderr に出して終了コード 1 です。これらの失敗経路では生成後の margin/hash ファイル出力まで到達しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:1000-1005, 1056-1059`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:372, 430` — フラグの初期値と parser 定義。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:701, 992-1017` — speculative mode の条件、margin 採取の有効化、出力。
- `engine/src/hy4flash/run/hy4_spec.hip.h:146-168, 472-473` — speculative 経路の top-1/top-2 差と logits hash の計算・記録。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:1034-1104` — 通常 decode の採取とファイル出力。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:611, 707-708, 914-1018` — serve、batch、比較、生成の分岐。
