# `strata --batch-groups`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの root） |
| オプション | `--batch-groups` |
| 別名 | なし |
| 値 | 正の整数 `G` または `auto` |

## 役割

`--batch` で作る会話 slot を複数グループに分け、layer split の GPU stage 間でパイプライン実行するグループ数を指定する。各 stage が別グループを処理中にできるため、複数 GPU の layer split と batch の組み合わせで使う。`G=1` は全 slot を一つの window として stage ごとに順番に処理する。parser の説明と実行ループの条件は `engine/src/program/generate.cpp:1321`、`engine/src/program/generate.cpp:17423-17427` にある。

## 使い方

```sh
# 8 slot を4グループに分け、layer split の stage 間でパイプライン実行
strata --serve --batch 8 --layer-split 24 --batch-groups 4 --pack model.gguf

# 対応するグループ数を自動選択
strata --serve --batch 8 --layer-split 24 --batch-groups auto --pack model.gguf

# パイプラインを使わず、全 slot を一つのグループで処理
strata --serve --batch 8 --layer-split 24 --batch-groups 1 --pack model.gguf
```

## 値と既定値

- 値は必須。CUDA/HIP 系 parser は `auto` 以外を `std::atoi` で整数化し、SYCL parser も同様に整数化する。厳密な数値形式や正数の parser validation はないため、非数値文字列は `0` になる。省略値や無効値を含む境界値の扱いは backend により異なるため、整数 `1` 以上または `auto` を指定すること。parser は `engine/src/program/generate.cpp:4039-4044` と `engine/sycl/src/program/generate.cpp:2040-2043`。
- CUDA/HIP 系では、未指定かつ layer split があり `--batch >= 2` の場合、内部的に `auto` 相当を解決する。`auto` は slot 数を割り切り、GPU stage 数（先頭 GPU を含む）以下となる最大のグループ数を選び、条件に合う数がなければ `1`。計算は `engine/include/strata/program/batch_groups.hpp:113-119,126-137`。
- CUDA/HIP 系で `auto` を明示した場合も同じ最大 divisor を選ぶが、「明示した」値として扱われる。未指定時だけ適用される互換・相互作用による serial fallback は、明示 `auto` には適用しない（`engine/include/strata/program/batch_groups.hpp:127-137,141-145`）。
- SYCL では未指定時の基本値は `1`。ただし layer split が2枚の Intel Arc B-series GPU で、batch が8以上の偶数、かつ `STRATA_BATCH_GROUPS_AUTO=0` でない場合は既定で `2` にする。明示 `auto` は最大 divisor を選ぶ。`engine/sycl/src/program/generate.cpp:4402-4421`。

## 実行時の動作

CUDA/HIP 系では解決した値を `o.batch_groups` に設定する。`G > 1`、batch が有効、layer split があるとき、各 group は `--batch / G` slot を持ち、stage 間をパイプラインで進む。CUDA/HIP の適用判定は `engine/src/program/generate.cpp:7905-7928`、実行ループと group の slot 数は `engine/src/program/generate.cpp:17423-17427`。SYCL にも同じ `G > 1` の pipeline 判定がある（`engine/sycl/src/program/generate.cpp:10086-10095`）。

指定した `G > 1` が layer split なし、または batch slot 数を割り切らない場合は警告を stderr に出して `1` group に戻す（CUDA/HIP: `engine/src/program/generate.cpp:7923-7928`; SYCL: `engine/sycl/src/program/generate.cpp:4423-4427`）。GPU session が確保できる slot 数に変わった後も自動値を再解決し、最終 slot 数で割り切れない group 数は `1` に戻る（`engine/src/program/generate.cpp:7930-7935,8037-8042`）。

CUDA/HIP 系でこのオプションを省略したときの `auto` は、次の条件では `1` group に切り替わる。

- `--batch-mtp` が有効で、`STRATA_BATCH_MTP_SERIAL` が空でなく `0` 始まりでもない場合。
- `--adapt-async 1` が有効な場合。
- NVIDIA の2 GPU構成で `STRATA_BATCH_GROUPS_NV_SERIAL` が空でなく `0` 始まりでもない場合、または空・未設定で `STRATA_DEFAULTS=026` が有効な場合。

これらの判定は「未指定時の既定 auto」に限る（`engine/src/program/generate.cpp:7732-7749`; `engine/include/strata/program/batch_groups.hpp:126-137`）。`--batch-mtp` と明示した `--batch-groups G > 1` の通常経路では、pipeline は per-slot MTP draft を実行しないため、起動時に警告する。`STRATA_PIPED_MTP` が有効で条件を満たす場合は pipeline 内で draft を行う経路がある（`engine/src/program/generate.cpp:7804-7809,17435-17441`; `engine/include/strata/program/batch_groups.hpp:139-145`）。同様に pipeline は `--adapt-async 1` の batch adaptive tier と組み合わないため、省略時の自動選択は serial に切り替える（`engine/src/program/generate.cpp:7728-7731`; `engine/include/strata/program/batch_groups.hpp:131-135`）。

## 適用条件と副作用

- Pipeline になるのは batch が有効で `G > 1` かつ複数 stage の layer split がある場合だけ。単一 GPU や `G=1` では stage 間 pipeline は作られない（`engine/src/program/generate.cpp:17423-17427`; SYCL: `engine/sycl/src/program/generate.cpp:10086-10095`）。
- `--batch` 自体は `--serve` を必要とする。未指定時または値が2未満、あるいは split の複数 stage が同一 GPU にある場合、batch を警告付きで無効化するため、このオプションの pipeline 効果も生じない（`engine/src/program/generate.cpp:7885-7897`）。
- 各 batch slot は各 stage 上に追加 session state を確保する。CUDA/HIP 系は確保に失敗すると利用可能 slot 数を減らし、2 slot 未満しか確保できない場合 batch を無効にする（`engine/src/program/generate.cpp:7929-7935,7990-8035`）。この option 自体がファイルやネットワークを操作する処理は確認できない。
- 自動 group 選択に関係する環境変数は `STRATA_BATCH_MTP_SERIAL`、`STRATA_BATCH_GROUPS_NV_SERIAL`、`STRATA_DEFAULTS`、`STRATA_PIPED_MTP`（CUDA/HIP 系）、および `STRATA_BATCH_GROUPS_AUTO`（SYCL の Arc B-series 既定）である。設定値の完全な仕様は各環境変数文書を参照。

## 出力とエラー

- `--batch-groups` の値が欠けると `--batch-groups needs a value` を stderr に出し、終了コード `2` で終了する（CUDA/HIP: `engine/src/program/generate.cpp:3837-3842`; SYCL: `engine/sycl/src/program/generate.cpp:1882-1887`）。
- グループ数が layer split に適用できないときは警告を stderr に出して1 groupへ補正する（上記「実行時の動作」参照）。明示した `auto` や既定 auto が使われると、選択した group 数や serial にした理由を `strata generate:` から stderr に表示する（`engine/src/program/generate.cpp:7905-7921`）。
- 非数値や0・負数を正数エラーとして拒否する検証は parser では確認できない。これらの値の backend 間で一貫した動作は確認できないため、利用例では扱わない。

## 根拠

- `engine/src/program/generate.cpp:1020-1025,4039-4044` — option state と CUDA/HIP 系 parser。
- `engine/src/program/generate.cpp:1317-1321` — CLI usage に記載された役割と関連条件。
- `engine/include/strata/program/batch_groups.hpp:113-145` — 自動 divisor 選択、既定時の serial fallback、MTP 相互作用。
- `engine/src/program/generate.cpp:7732-7749,7900-7928` — backend・環境変数を含む解決、ログ、無効値の警告と補正。
- `engine/src/program/generate.cpp:17423-17441` — CUDA/HIP 系 pipeline 実行の判定と MTP 警告。
- `engine/sycl/src/program/generate.cpp:2040-2043,4402-4427,10086-10095` — SYCL parser、既定、validation と pipeline 判定。
