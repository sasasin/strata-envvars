# `strata generate --native-dense-gguf`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--native-dense-gguf` |
| 別名 | なし |
| 値 | GGUF ファイルのパス。モデルが分割されている場合は shard ごとに指定する。 |

## 役割

通常の pack から読む重みに加えて、指定した GGUF shard から対象の dense projection 行列を読み、エンジンの native 行列経路に登録する。対象になるのは `blk.*` の attention/GDN/QSA/shared expert projection 名など、loader が認識し、native MMVQ が対応するテンソルである。単なるモデルファイルの選択肢ではなく、pack に含まれる対応テンソルを GGUF 側の値で実行するための入力指定である。parser は値を `native_dense_gguf` のリストへ追加するだけで、ファイル検査は読み込み段階で行う（`engine/src/program/generate.cpp:807,3929`; `engine/src/core/native_dense.cpp:180-191,345-357`）。

## 使い方

```sh
# pack の重みを使いつつ、分割 GGUF の dense projection shard を指定する
strata generate --pack /models/pack --tokens "1,2,3" \
  --native-dense-gguf /models/model-00001-of-00002.gguf \
  --native-dense-gguf /models/model-00002-of-00002.gguf
```

各 `--native-dense-gguf` の直後に 1 パスを指定し、必要な shard を繰り返して渡す。`--native` を同時指定し、かつこのオプションを省略した場合は、`--native` から見つかったモデル shard 群と必要な PLE shard が dense 入力に補われる。明示的にこのオプションを指定した場合、そのリストは自動補完されない（`engine/src/program/generate.cpp:5166-5190`）。

## 値と既定値

- 値は `next("--native-dense-gguf")` で取得し、複数指定を順に vector へ追加する。別名・既定パス・指定回数の上限は parser に定義されていない（`engine/src/program/generate.cpp:807,3929`）。
- 引数値が欠けると `--native-dense-gguf needs a value` を stderr に出して終了コード 2 で終了する。空文字列やパスの存在・形式は parser では検証されず、GGUF 読み込み時に扱われる（`engine/src/program/generate.cpp:3842-3847,3929`）。
- 明示指定がなく `--native` もない場合、dense GGUF の追加読み込みは行わない。`--native` がある場合だけ、未指定リストを `--native` の全 shard に置き換え、PLE 専用テーブルでない PLE shard が既に含まれていなければ追加する（`engine/src/program/generate.cpp:5166-5190`）。

## 実行時の動作

loader は各ファイルの GGUF shard 情報とテンソル一覧を読み、重複 shard 番号、重複テンソル、payload の範囲・重なり、テンソル形状、pack の canonical table との対応を検査する。対象名は `blk.*` で、PLE key は `--native-ple-key` も有効な場合に限られる。その他は `.attn_qkv.weight`、`.attn_gate.weight`、`.ssm_out.weight`、`.attn_q.weight`、`.attn_k.weight`、`.attn_v.weight`、`.attn_output.weight`、`.ffn_{gate,up,down}_shexp.weight` のいずれかで終わるテンソルである。さらに native MMVQ が型をサポートし、行列が pack 内の対応テンソルと寸法一致するものが登録対象となる（`engine/src/core/native_dense.cpp:180-191,345-438,459-468`）。

対応テンソルは device memory に確保・転送され、対応する `WeightRef` に native data/type/byte 数が設定される（`engine/src/core/native_dense.cpp:467-490,623-649`）。既定では native 側で提供される名前を canonical pack の読み込み対象から外すため、同じ重みを二重に保持しない。`--keep-canonical` を指定するとこの除外をしないため、canonical 版も読み込まれる（`engine/src/program/generate.cpp:5804-5815`）。複数 GPU の layer split では段ごとに dense 重みを読み、分割判定用にも GGUF dense 重みの容量を計算する（`engine/src/program/generate.cpp:6074-6084,6660-6664,6877-6884`）。

`--native` は `--native-dense-gguf` とは別の一括 native preset であり、同時指定時は native フラグ群や PLE key も有効化する。dense list 自体は上記のとおり、明示リストがあればそれを維持する（`engine/src/program/generate.cpp:5112-5125,5160-5190`）。`--native-ple-key` を単独で有効にする場合は、dense リストが空でなく、`--no-ple` が無効でなければならない（`engine/src/program/generate.cpp:5318-5320`）。

## 適用条件と副作用

- 少なくとも一つの GGUF パスが必要で、対応する native GDN/QSA projection 行列が一つも見つからない場合は loader が失敗する（`engine/src/core/native_dense.cpp:356-358,622`）。
- shard を複数渡す場合、先頭 shard の architecture と split metadata を基準に後続 shard の metadata が検証される。渡した shard 番号の重複や不一致は拒否される（`engine/src/core/native_dense.cpp:367-388`）。
- native の対象として認識されないテンソルは native 行列として登録されない。`--keep-canonical` も指定していない場合、canonical 側の除外対象は native MMVQ 対応型などの条件を満たした `served_names` の結果で決まる（`engine/src/core/native_dense.cpp:214-228`; `engine/src/program/generate.cpp:5807-5815`）。
- loader は GPU device memory を確保し、行列データを host-to-device 転送する。割当・転送に失敗すると読み込みは中断する（`engine/src/core/native_dense.cpp:445-449,472-487,623-626`）。
- CUDA parser と対になる SYCL 実装にも同じ引数登録と dense loader 呼び出しがあるが、GPU/backend ごとの kernel 対応範囲や割当挙動の同一性まではこの文書では比較していない（`engine/sycl/src/program/generate.cpp:1968,3210`）。

## 出力とエラー

- 読み込み成功時は native projection matrix 数、重みサイズ、所要時間を stderr に出す（`engine/src/program/generate.cpp:6060-6067`）。
- `served_names` の GGUF 読み込み失敗はエラーを stderr に出して終了コード 1。dense loader の失敗も `native dense projections: ...` を stderr に出して終了コード 1 となる（`engine/src/program/generate.cpp:5808-5812,6061-6065`）。
- 不正な shard metadata、重複テンソル、canonical table にないテンソル、寸法不一致、payload 不正、GPU 割当・転送失敗などの詳細な理由は loader がエラー文字列に設定する（`engine/src/core/native_dense.cpp:381-423,432-465,485-487`）。

## 根拠

- `engine/src/program/generate.cpp:807,3929` — 値を保持する field と root parser 登録。
- `engine/src/program/generate.cpp:3842-3847` — 値欠落時のエラーと終了コード。
- `engine/src/program/generate.cpp:5166-5190` — `--native` 使用時の dense shard 自動補完。
- `engine/src/core/native_dense.cpp:180-191,345-468` — テンソル名・型・寸法・shard の選別と検証。
- `engine/src/core/native_dense.cpp:445-490,623-649` — device memory への登録と native reference の設定。
- `engine/src/program/generate.cpp:5804-5815,6060-6067` — canonical 重みの除外条件、読み込みと出力。
- `docs/cli/README.md:1036-1042,1128-1139` — `strata-engine` の root scope と索引リンク。
