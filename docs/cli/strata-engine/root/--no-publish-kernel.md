# `--no-publish-kernel`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。モデル選択後の通常 parser） |
| オプション | `--no-publish-kernel` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

MoE の doorbell handoff と QSA の step-state 転送で使う publish 用 GPU kernel 経路を無効にします。転送そのものを止めるフラグではなく、該当経路では通常のメモリコピーへ切り替わります。CUDA/HIP 系と SYCL 系の通常 parser の双方にあります。

## 使い方

```sh
strata model.strata --no-publish-kernel
```

`model.strata` を指定してエンジンを実行する例です。このフラグ自体に追加の値は指定しません。

## 値と既定値

引数構造体の初期値は `false` で、指定時に `true` へ設定されます。値を受け取る処理や個別の範囲 validation はありません。同じフラグを複数回指定しても同じ真偽値を設定します。フラグの後ろに別の値を置くと、その値は未知引数として扱われます（`engine/src/program/generate.cpp:4265-4273`、`engine/sycl/src/program/generate.cpp:2211-2219`）。

## 実行時の動作

parser の値は `layer_set_publish_kernel(!o.no_publish_kernel)` を通じて core の共有フラグへ反映されます（CUDA/HIP 系: `engine/src/program/generate.cpp:6108-6110`、SYCL 系: `engine/sycl/src/program/generate.cpp:3223-3225`。格納先: `engine/src/core/layer.cpp:51,548`、`engine/sycl/src/core/layer.cpp:47,550`）。

- **MoE doorbell handoff:** doorbell がある (`db != nullptr`) 場合、通常は `doorbell_publish` kernel が入力・expert ID・weight を handoff buffer へ書き、通知します。フラグ指定時はその kernel 分岐を通らず、CUDA/HIP 系では device-to-device の `cudaMemcpyAsync`、SYCL 系では queue の `memcpy` で同じ3種類のデータをコピーしてから ring を行います（`engine/src/core/layer.cpp:429-439`、`engine/sycl/src/core/layer.cpp:423-447`）。doorbell がない場合、この分岐では何もしません。
- **QSA step-state 転送:** QSA layer が step/position を host 側 state に作った後、通常は mapped host memory を読む `copy_i32_from_mapped` kernel 経路を試します。フラグ指定時はその条件を満たさないため、step と position を host-to-device `cudaMemcpyAsync`（CUDA/HIP 系）または queue `memcpy`（SYCL 系）でアップロードします（`engine/src/core/layer.cpp:1195-1203`、`engine/sycl/src/core/layer.cpp:1213-1229`）。

それ以外の publish 経路を無効化するか、他のエンジン設定を変更する処理は確認できません。どちらの効果も、対応する MoE doorbell または QSA layer を実行する場合に限られます。

## 適用条件と副作用

この設定は parser で読み取られ、実行開始時に core のフラグとして設定されます。対象経路では専用 kernel の代わりに非同期メモリコピーをキューへ投入します。コピー API が失敗すると、MoE handoff は `moe_route: the doorbell handoff copy failed`、QSA は `qsa_layer: the step-state upload failed` をエラー文字列へ設定し、処理を失敗させます（前掲の `layer.cpp` 使用箇所）。実行時性能への影響量はソースからは確定できません。

## 出力とエラー

このオプション固有のメッセージ出力はありません。未知引数は stderr に `unknown argument: <値>` を出して usage を表示し、終了コード `2` で戻ります（`engine/src/program/generate.cpp:4268-4273`、`engine/sycl/src/program/generate.cpp:2214-2219`）。上記コピー失敗時は各呼び出し元へ失敗を返します。終了コードや最終表示は上位のエラー処理に依存するため、ここで参照した範囲からは特定できません。

## 根拠

- `engine/src/program/generate.cpp:957,4265,6108-6109` — CUDA/HIP 系 parser 状態、フラグ登録、core への反映。
- `engine/sycl/src/program/generate.cpp:623,2211,3223-3224` — SYCL 系の同じ処理。
- `engine/src/core/layer.cpp:429-439,1195-1203` — CUDA/HIP 系の doorbell と QSA の条件分岐、代替コピー、失敗経路。
- `engine/sycl/src/core/layer.cpp:423-447,1213-1229` — SYCL 系の対応する分岐と失敗経路。
- `docs/cli/README.md:1155` — `strata-engine` の root scope に予定された索引項目。
