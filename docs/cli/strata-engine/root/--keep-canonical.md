# `strata` `--keep-canonical`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root scope） |
| オプション | `--keep-canonical` |
| 別名 | なし |
| 値 | 値を取らない boolean フラグ |

## 役割

`--native`、`--native-dense-gguf`、`--native-head-gguf` などで native 形式から提供するテンソルについて、canonical pack 側のコピーもロード対象に残します。native 側と canonical 側の両方を保持するため、native 版だけを使う通常経路より VRAM を多く使います。A/B 比較用として案内されているフラグです。

## 使い方

```sh
# 通常の pack に加え、native GGUF と PLE テーブルを指定した起動例
strata --pack /path/to/pack --tokens 1 \
  --native /path/to/model-00001-of-0000N.gguf \
  --ple-gguf /path/to/ple.gguf --keep-canonical
```

`--native` を使う場合、ソース上は PLE テーブルを `--ple-gguf` で指定する必要があります。上記は構文例であり、パスは実際の pack と GGUF に置き換えます。

## 値と既定値

値は不要です。`Options::keep_canonical` の初期値は `false` で、指定すると `true` になります。数値や文字列を続けて値として渡す形式ではなく、同じフラグを複数回指定した場合も同じ `true` の代入が繰り返されます。独立した範囲 validation はありません。

## 実行時の動作

CUDA/HIP 系と SYCL 系の parser は、どちらもこの引数を `o.keep_canonical = true` に設定します（`engine/src/program/generate.cpp:953,4261`、`engine/sycl/src/program/generate.cpp:619,2207`）。

native pack 用の条件分岐を通過した後、フラグが false のときだけ `skip` 集合を native dense の提供テンソル名や native head の `output.weight` で作ります。true のときはこの集合への追加処理全体を通らず、その集合を使って pack の `WeightTable` を読み込みます。`WeightTable::load` は skip 対象の行を arena に配置せず、対象外の行を詰めて配置するため、このフラグは native 版と重複する canonical テンソルを pack からもロードさせます（CUDA/HIP: `engine/src/program/generate.cpp:5804-5826,6044-6057`、SYCL: `engine/sycl/src/program/generate.cpp:3067-3085,3198-3205`、共通実装: `engine/src/core/weights.cpp:224-239`）。native dense のロード処理はその後も実行されるため、両方のコピーが存在します（CUDA/HIP: `engine/src/program/generate.cpp:6060-6067`、SYCL: `engine/sycl/src/program/generate.cpp:3208-3215`）。

フラグがない場合、native dense の提供テンソル名の取得に失敗するとエラーを stderr に出して終了コード 1 で戻ります。フラグがある場合はその `served_names` 呼び出し自体を行いません。pack の読み込みに失敗した場合は、フラグの有無にかかわらずエラーを stderr に出して終了コード 1 です（`engine/src/program/generate.cpp:5807-5812,6044-6047`、SYCL: `engine/sycl/src/program/generate.cpp:3070-3075,3198-3201`）。

## 適用条件と副作用

- 主な効果があるのは、native dense/head 経路など、native 提供テンソルがある起動です。該当する native 指定がなければ、このフラグによる native 重複コピーの抑制解除は実質的にありません。
- 追加ロード分の VRAM を消費します。help 表示も「more VRAM」と案内し、起動時には pack から読み込んだ容量と「canonical tensors skipped」の件数を stderr に出します（`engine/src/program/generate.cpp:1291,6055-6057`、SYCL: `engine/sycl/src/program/generate.cpp:879,3203-3205`）。他の機能が skip 集合を追加する場合もあるので、件数が必ず 0 になるとは限りません。
- native IQ pack の実行では `o.keep_canonical` が validation 条件に含まれ、該当すると終了コード 2 で拒否されます。表示されるエラー文は `--native`、`--spec`、`--prefill` の要件を列挙しますが、このフラグが条件に含まれることまでは説明しません（CUDA/HIP: `engine/src/program/generate.cpp:5781-5787`、SYCL: `engine/sycl/src/program/generate.cpp:3046-3052`）。
- layer split など、このフラグとは別の処理も `skip` 集合を使うため、`--keep-canonical` が全ての理由による canonical 重みの除外を無効にするわけではありません（CUDA/HIP: `engine/src/program/generate.cpp:5827-5831,5979`、SYCL: `engine/sycl/src/program/generate.cpp:3086-3090`）。

## 出力とエラー

フラグ専用の成功メッセージや警告は確認できません。pack 読み込み後の stderr ログは、ロード容量と canonical tensors の skip 件数を出力します。native pack との組み合わせは終了コード 2、pack または native dense のロード失敗は終了コード 1 になります（上記「実行時の動作」「適用条件と副作用」参照）。

## 根拠

- `engine/src/program/generate.cpp:953,4261` — CUDA/HIP 系 `Options` の既定値と parser 登録。
- `engine/sycl/src/program/generate.cpp:619,2207` — SYCL 系 `Options` の既定値と parser 登録。
- `engine/src/program/generate.cpp:1291`、`engine/sycl/src/program/generate.cpp:879` — help にある A/B 用途と追加 VRAM の説明。
- `engine/src/program/generate.cpp:5804-5826,6044-6067`、`engine/sycl/src/program/generate.cpp:3067-3085,3198-3215` — skip 集合の作成条件、canonical pack のロードと native dense ロード。
- `engine/src/core/weights.cpp:224-239` — skip 対象を除いて重み arena に配置する処理。
- `engine/src/program/generate.cpp:5781-5787`、`engine/sycl/src/program/generate.cpp:3046-3052` — native pack とフラグの併用を拒否する条件。
- `engine/src/program/generate.cpp:5807-5812,6044-6047`、`engine/sycl/src/program/generate.cpp:3070-3075,3198-3205` — skip 名取得・pack 読み込みの失敗経路と起動ログ。

調査範囲は上記 revision の Strata 所有ソースに限ります。`--help` は実行せず、同じ revision のソース内 help 文字列を parser 定義と照合しました。
