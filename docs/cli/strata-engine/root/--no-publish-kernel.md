# `--no-publish-kernel`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--no-publish-kernel` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

doorbell の handoff と QSA step-state の転送に使う publish/copy kernel を無効にし、該当データを CUDA/HIP の非同期メモリコピー経路で転送します。doorbell による CPU expert pool への通知そのものを無効にするオプションではありません。既定では有効です（`Options::no_publish_kernel` の初期値は `false`、その否定値を setter に渡します）。

## 使い方

通常の engine parser では値なしで指定します。

```sh
strata --pack pack/full --tokens "1,2,3" --no-publish-kernel
```

`--pack` と `--tokens` は実行に必要な引数の例です。エンジンの使用形式は `src/program/generate.cpp` の usage に記載されています。

## 値と既定値

値は不要です。指定すると parser が `no_publish_kernel` を `true` にします。未指定時は `false` で、publish kernel 経路が有効です。同じフラグを複数回指定しても同じ boolean を再設定するだけです。値の検証や範囲指定はありません。値を付ける形式は定義されていません。

## 実行時の動作

- `generate.cpp` は `layer_set_publish_kernel(!o.no_publish_kernel)` を呼び、layer 実装の共有フラグを設定します。
- MoE routing で doorbell がある場合、既定経路は `doorbell_publish(...)` で入力・expert ID・weight を通知先に publish します。このフラグを指定した経路は、それら3領域を `cudaMemcpyAsync(..., cudaMemcpyDeviceToDevice, ...)` でコピーした後、共通の `doorbell_ring(...)` を呼びます。したがって doorbell の ring と通知プロトコルは残ります。
- QSA layer の step と position state は、既定経路では mapped host memory への device pointer 取得に成功すれば `copy_i32_from_mapped(...)` を使います。このフラグを指定するとその条件が偽になるため、`cudaMemcpyAsync(..., cudaMemcpyHostToDevice, ...)` 経路に進みます。
- `doorbell_init` による mapped pinned host memory の確保はこのフラグに関係なく実行されます。フラグはその確保を省略しません。

## 適用条件と副作用

この説明は `src/program/generate.cpp` の通常 engine parser が選ばれる場合のものです。`STRATA_HAVE_QWEN35` を含む build では、`--model` または `--native` の GGUF が Qwen3.5 系と判定されると `src/qwen35/q36_engine.cu` の別 parser へ振り分けられます。そちらの parser に `--no-publish-kernel` はありません。serve モード以外では未知引数として usage を出して終了し、serve モードでは未対応オプションとして警告して無視する処理があります。

`doorbell_publish` から明示的な memcpy 経路への切替、また QSA state の mapped memory kernel から非同期 host-to-device copy への切替が生じます。性能上の効果はこのコード調査だけでは確定できません。

## 出力とエラー

通常 parser ではこのフラグ自体に対する専用の標準出力・標準エラー出力はありません。未知の引数は `unknown argument: ...` と usage を標準エラーに出して終了コード `2` になります。フラグ指定時の doorbell コピーが失敗すると `moe_route: the doorbell handoff copy failed`、QSA の step-state copy が失敗すると `qsa_layer: the step-state upload failed` をエラー文字列に設定し、呼び出し側へ失敗を返します。

## 根拠

- オプションと既定値: `src/program/generate.cpp:606`（初期値 `false`）、parser 分岐 `src/program/generate.cpp:2784`。
- 有効化処理: `src/program/generate.cpp:3926-3928`、setter `src/core/layer.cpp:548`。
- doorbell の既定経路・代替コピー・共通 ring と失敗: `src/core/layer.cpp:424-439`。
- QSA step-state の mapped-memory 経路と host-to-device fallback: `src/core/layer.cpp:1172-1180`。
- doorbell 用 mapped pinned memory の確保: `src/core/layer.cpp:1312-1316`。
- 未知引数のエラー・usage・終了コード: `src/program/generate.cpp:2787-2792`。
- Qwen3.5 系への family dispatch: `src/program/generate.cpp:2393-2407`。別 parser の引数受理、serve 中の無視、通常時の未知引数処理: `src/qwen35/q36_engine.cu:3735-3795`。
- 通常 parser の help は `src/program/generate.cpp:806-808` から始まり、記載一覧にこのフラグを含みません。索引 [`docs/cli/README.md`](../../README.md) には予定リンクとして掲載されています。
