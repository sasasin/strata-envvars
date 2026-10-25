# `--native-dense-gguf`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの root parser） |
| オプション | `--native-dense-gguf PATH` |
| 別名 | なし |
| 値 | native dense projection を含む GGUF ファイルのパス。複数回指定できる |

## 役割

GDN/QSA、attention、shared expert などの対応行列を GGUF から読み、pack の canonical 重みに native 行列として設定します。これは `--native` によるモデル GGUF の指定とは別に dense 重みの入力を明示するための引数です。`--native` と併用し、この引数を省略した場合は `--native` の全 model shard と PLE shard が候補になります。

## 使い方

```sh
strata --pack <pack-dir> --native <model.gguf> \
  --native-dense-gguf <dense-shard-1.gguf> \
  --native-dense-gguf <dense-shard-2.gguf> \
  --ple-gguf <ple-shard.gguf> --tokens 1,2,3
```

必要な shard を各1回指定します。NVFP4 pack で dense 重みを別 GGUF から読む利用例は、調査対象 checkout の `docs/NVFP4.md:34-38` にあります。

## 値と既定値

- parser は `PATH` を文字列として受け取り、指定のたびに vector へ追加します。引数の順序を保って処理します。alias はなく、単独指定の回数制限はありません（`src/program/generate.cpp:2503`、`src/program/generate.cpp:469`）。
- 値を省略すると parser は `--native-dense-gguf needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2420`）。空文字列は parser 側で拒否されませんが、有効な GGUF パスとしてロードできるかは後続処理に委ねられます。
- `--native` を指定し、この引数を一度も指定しなければ、`--native` が解決した全 shard が候補になり、PLE shard が `strata-ple` 専用でなければ PLE shard も候補に加わります。`--native-dense-gguf` を1つでも指定すると、この自動補完は行われず、明示したパスだけが使われます（`src/program/generate.cpp:3232-3237`、`src/program/generate.cpp:3269-3281`）。
- `--native` を使わない場合のパス既定値はありません。指定した GGUF 群からロード対象行列が1つも見つからなければロードエラーになります。

## 実行時の動作

対象名は `blk.` で始まるテンソルのうち、`.attn_qkv.weight`、`.attn_gate.weight`、`.ssm_out.weight`、attention q/k/v/output、shared expert gate/up/down の各 suffix に合うものです。さらに native MMVQ が対応する型で、2次元行列である必要があります。PLE key は別扱いで、`--native-ple-key` が有効な場合に対応する型（型コード 42、18、23、8）の `blk.1.ple_key.weight` も候補になります（`src/core/native_dense.cpp:154-165`、`src/core/native_dense.cpp:178-192`）。

engine は GGUF の shard を開き、対象行列の形状と canonical table の行列形状・量子化状態を照合し、デバイスメモリへコピーします。ロード成功後は `WeightRef` に native data/type と scratch を設定し、推論側の native 行列経路がこの値を使用します（`src/core/native_dense.cpp:265-273`、`src/core/native_dense.cpp:344-376`、`src/core/native_dense.cpp:483-503`、`src/core/layer.cpp:170-180`）。

既定では、対象 native 行列として認識された canonical tensor を pack からロードしないようにします。`--keep-canonical` が有効ならこの除外処理を行わず、canonical 側も保持します（`src/program/generate.cpp:3774-3785`）。`--native` 経路では native preset が `--native-ple-key` を有効にするため、対応形式の PLE key も対象になり得ます（`src/program/generate.cpp:3263-3268`）。

`--layer-split` の各 GPU stage でも同じ shard 群を読み込みます。自動 split の候補容量計算にもこの行列群の見積もりを加えます（`src/program/generate.cpp:4335-4338`、`src/program/generate.cpp:4525-4552`）。セッションの model file identity にも native dense 入力が含まれます（`src/program/generate.cpp:9402-9413`）。

## 適用条件と副作用

- 通常の native dense loader は少なくとも1つの GGUF shard を要求します。追加 shard は先頭 shard で architecture が検証済みであること、split metadata が一致すること、shard 番号が重複しないことを検証します（`src/core/native_dense.cpp:265-303`）。
- 対象テンソル名の重複、canonical table にないテンソル、既存 override、canonical 側が非量子化、shape 不一致、破損・重なり・範囲外 payload などは拒否されます（`src/core/native_dense.cpp:305-363`）。
- native 対応型でない行列は native override の対象外です。読めた全 shard を調べても native 対応 GDN/QSA 行列がなければ失敗します（`src/core/native_dense.cpp:344-356`、`src/core/native_dense.cpp:481`）。したがって、パスを渡しただけで GGUF 内の全テンソルが使用されるわけではありません。
- GGUF 読み込みと CUDA device memory の確保・転送が発生します。対象行列を native 側に置き、既定では対応する canonical weights を省くことで、pack 側の重みロード内容が変わります（`src/core/native_dense.cpp:367-372`、`src/program/generate.cpp:3774-3785`）。

## 出力とエラー

- 値がない場合は stderr に必要値を表示して終了コード 2（`src/program/generate.cpp:2418-2420`）。未知の引数も usage を stderr に出して終了コード 2 です（`src/program/generate.cpp:2787-2792`）。
- `--native` の shard 解決や PLE 条件の失敗は `strata generate:` 付きメッセージを stderr に出して終了コード 2 です（`src/program/generate.cpp:3232-3261`）。
- dense 行列の一覧検査失敗は stderr に理由を出して終了コード 1、通常ロード時は `strata generate: native dense projections: ...` として終了コード 1 です（`src/program/generate.cpp:3777-3782`、`src/program/generate.cpp:3912-3919`）。layer split 中の stage load 失敗もエラーを出し、その stage の初期化を失敗させます（`src/program/generate.cpp:4335-4339`）。
- 成功するとロードした native projection 行列数と重み量を stderr に表示します（`src/program/generate.cpp:3912-3919`）。

## 根拠

- 索引上の scope と配置: `docs/cli/README.md:1128-1144`、対象リンク `docs/cli/README.md:1212`。
- usage 表記: `src/program/generate.cpp:863`。
- parser、既定値の補完、preset との相互作用: `src/program/generate.cpp:2418-2420`、`src/program/generate.cpp:2500-2503`、`src/program/generate.cpp:3232-3281`。
- 選別条件、GGUF・形状検証、device load、override の登録: `src/core/native_dense.cpp:154-165`、`src/core/native_dense.cpp:178-192`、`src/core/native_dense.cpp:265-363`、`src/core/native_dense.cpp:367-376`、`src/core/native_dense.cpp:481-517`。
- canonical 重みの除外、通常・layer-split 経路でのロード: `src/program/generate.cpp:3774-3795`、`src/program/generate.cpp:3912-3919`、`src/program/generate.cpp:4335-4339`。

調査は指定 commit の checkout に含まれるソースを対象としました。Release 配布物や他 platform/backend での実行確認は行っていません。
