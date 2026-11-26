# `strata --no-spec-split`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--no-spec-split` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

推測デコードの verifier が複数 token の検証窓を二群に分ける設定を無効にします。エンジン設定の既定値も無効なので、主に `--spec-split` を指定した同じ引数列で後から無効へ戻す用途です。推測デコード自体や候補 token 数を無効化するフラグではありません。

## 使い方

```sh
# --spec-split を先に指定していても、後続の --no-spec-split で無効にする
strata --model MODEL.gguf --tokens 1,2,3 --spec 4 --spec-split --no-spec-split --max-new 16
```

## 値と既定値

値を取りません。設定構造体の `spec_split` は初期値 `false` で、parser はこのフラグを読むと `false` を代入します（`engine/src/program/generate.cpp:1069,4196`）。同じ parser は `--spec-split` で `true` を代入するため、両方を指定した場合は後に現れた方が有効です（同 `:4064,4196`）。範囲検証や数値変換はありません。

## 実行時の動作

CUDA/HIP 系の通常エンジンでは、設定値を verifier の `set_split` に渡します。`engine/include/strata/core/verify.hpp:424-426,770` では、この設定は検証窓を二つの token 群に分け、一方の CPU expert 処理と他方の GPU 処理を重ねるためのものとされています。`engine/src/core/verify.cpp:1484-1486` では、設定が有効で `T >= 2`、かつ batch-recording 中でない場合に窓を 2 群 (`G = 2`) にし、それ以外は 1 群にします。`T > kVerifyMaxT` の窓はこのフラグが無効でも 2 群に分割されます。

通常の生成経路は verifier に設定値を渡し（`engine/src/program/generate.cpp:24538-24547`）、serve の multi-GPU stage と pipelined verifier にも同じ値を設定します（同 `:13682-13707`）。したがってこのフラグは複数 GPU の layer split 自体を無効にするものではなく、その verifier の窓分割設定を無効にします。SYCL parser にも同じ代入があり（`engine/sycl/src/program/generate.cpp:706,2057,2160`）、値の初期値・代入が確認できます。

## 適用条件と副作用

このフラグ単独ではファイル、ネットワーク、子プロセスを操作せず、GPU 呼び出しも直接行いません。効果は parser が設定した値を verifier が使う場合に限られます。上記の通り、長さが `kVerifyMaxT` を超える窓や batch-recording 経路では、`--no-spec-split` だけで必ず一群になるとは限りません。

`strata-engine` の通常 parser とは別に、`--model` または `--native` の GGUF family を判定して Qwen3.6-35B 用 `engine/src/qwen35` parser に振り分ける経路があります（`engine/src/program/generate.cpp:3804-3818`）。その専用 parser では `--no-spec-split` の定義・使用箇所を確認できなかったため、そのモデル経路での受理動作はここでは断定できません。

## 出力とエラー

通常 parser ではこのフラグ専用の出力や validation error はありません。通常 parser に認識されない引数は `unknown argument: <引数>` を stderr に出し、usage を表示して終了コード `2` を返します（`engine/src/program/generate.cpp:4268-4273`）。Qwen3.6-35B 専用 parser については上記のとおり未確認です。

## 根拠

- `engine/src/program/generate.cpp:1069,4196` — `spec_split` の初期値と `--no-spec-split` parser。
- `engine/src/program/generate.cpp:4064` — 対になる `--spec-split` の設定。parser は引数を順に処理する。
- `engine/include/strata/core/verify.hpp:424-426,770` — verifier の二群分割設定の説明と保存先。
- `engine/src/core/verify.cpp:1484-1486` — `T`、`split_`、batch-recording に応じた群数。
- `engine/src/program/generate.cpp:13682-13707,24538-24547` — serve の stage/pipeline および通常生成経路で verifier に値を渡す箇所。
- `engine/sycl/src/program/generate.cpp:706,2057,2160` — SYCL 側の既定値、対向フラグ、無効化 parser。
- `engine/src/program/generate.cpp:3804-3818,4268-4273` — Qwen3.6-35B parser への振り分けと通常 parser の未知引数エラー。
