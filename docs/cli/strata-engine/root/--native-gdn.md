# `--native-gdn`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数。トップレベル parser） |
| オプション | `--native-gdn` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

GDN 層の正規化・ゲート・再帰などで、通常の実装の代わりに experimental な pinned CUDA native kernel 群を選びます。GDN 層を含むモデルの推論時に作用し、GDN 以外の層にはこのフラグによる分岐はありません。既定値は無効です。`--native` プリセットを使うと、このフラグを個別に指定しなくても有効になります。

## 使い方

```sh
# DIR の pack を使い、token ID の入力で生成する。CUDA native GDN 経路を選択する。
strata --pack DIR --tokens "1,2,3" --native-gdn
```

## 値と既定値

- 値を取らず、parser は `o.native_gdn = true` に設定します。`Options` の初期値は `false` です。別名や `--no-native-gdn` は定義されていません（`engine/src/program/generate.cpp:784,3918`）。
- 数値などの値検証はありません。フラグを複数回指定しても、同じ真偽値を再設定するだけです。
- `--native` は他の native 経路とともに `native_gdn` も有効にします（`engine/src/program/generate.cpp:5160-5164`）。

## 実行時の動作

起動処理で `o.native_gdn` が `native_gdn_set_enabled` に渡され、GDN 層が native kernel を選ぶ状態になります（`engine/src/program/generate.cpp:6110-6119`）。GDN 層では、畳み込みと SiLU、Q/K の L2 正規化、beta sigmoid と gate、再帰 step、出力正規化の各段階で native 関数を呼び分けます。無効時は対応する通常の GDN 関数へ進みます（`engine/src/core/layer.cpp:282-312,337-369`）。

`--no-fused-gdn` は native 経路全体を無効にするものではありません。これは fused GDN 経路を止める設定であり、その場合も `--native-gdn` が有効なら個別の native 前処理・step・出力正規化が選ばれます。融合前処理にはさらに native BF16 projection、畳み込み tap 数 4、state size 128 の条件があり、fused step / 出力正規化には state size 128 の条件があります（`engine/src/program/generate.cpp:6110,6114`; `engine/src/core/layer.cpp:282-288,349-368`）。

## 適用条件と副作用

- ヘルプ記述はこの機能を「experimental pinned CUDA GDN norms/gates/recurrence」としています（`engine/src/program/generate.cpp:1250`）。CUDA 実装の再帰 kernel は state size 128 に固定され、正の head 数、head 数の割り切れ、stream、アラインメントと入出力領域の非重複を検証します。違反時は例外になります（`engine/src/kernels/cuda/native_gdn.cu:98-122`）。
- native 畳み込み前処理は tap 数 4 を要求し、正規化関数も geometry や stream を検査します。kernel 起動後の CUDA エラーも例外として返します（`engine/src/kernels/cuda/native_gdn_preprocess.cu:142-164,166-197`）。
- 対象の CUDA 実装は GDN 層の状態・中間値・出力を GPU 上で更新します。CLI parser 自体はファイルやネットワークの副作用を追加しません。
- `engine/sycl/src/program/generate.cpp` にも同じフラグの parser と `native_gdn_set_enabled` への設定があり、SYCL 側の layer 実装にも同じ分岐があります（`engine/sycl/src/program/generate.cpp:468,1957,3234`; `engine/sycl/src/core/layer.cpp:276-360`）。ただし本調査では実行可能バイナリや GPU での backend ごとの動作確認をしていません。

## 出力とエラー

オプション単体に値の validation error はありません。誤記など未認識の引数は `unknown argument` を stderr に出し、usage を表示して status 2 で終了します（`engine/src/program/generate.cpp:4268-4273`）。実行中に native kernel の入力条件や起動が失敗すると kernel 関数が例外を投げ、GDN layer 側がエラー文字列を設定して失敗を返します（`engine/src/kernels/cuda/native_gdn.cu:101-122`; `engine/src/core/layer.cpp:287-307,337-369`）。

## 根拠

- `engine/src/program/generate.cpp:784,1250,3918` — 既定値、ヘルプ表記、parser 登録。
- `engine/src/program/generate.cpp:5160-5164,6110-6119` — `--native` からの含意と実行時設定。
- `engine/src/core/layer.cpp:282-312,337-369` — GDN 層での native/通常 kernel の選択と融合条件。
- `engine/src/kernels/cuda/native_gdn.cu:98-122`、`engine/src/kernels/cuda/native_gdn_preprocess.cu:142-197` — CUDA kernel の入力条件、更新、起動エラー経路。
- `engine/sycl/src/program/generate.cpp:468,838,1957,3234`、`engine/sycl/src/core/layer.cpp:276-360` — SYCL 側にある同等の parser・設定・呼び出し分岐。
