# `--peer-device`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（root / 通常の engine parser） |
| オプション | `--peer-device` |
| 別名 | なし |
| 値 | 整数。`1` 以上で第2 expert-cache tier を有効化 |

## 役割

主 GPU の adaptive expert cache にない expert を、指定した別 GPU の cache に追加するための起動時オプションです。profile のランキングに従い、主 GPU が保持しない expert を第2 GPU の空き VRAM に収まる範囲で配置します。serve 中の adaptive 更新にも参加し、prefill では設定された行数をその GPU に計算させる経路があります。Qwen3.6 family は別 parser・別スコープで、索引上も `strata-engine/qwen36/--peer-device.md` に分かれています。

## 使い方

```sh
# expert profile と主 GPU の cache を使い、device ordinal 1 に peer tier を置く
strata --native model.gguf --expert-profile profile.bin --expert-cache 4096 --peer-device 1
```

この例の `model.gguf` と `profile.bin` は利用者のファイルに置き換えてください。`--expert-profile` と正の `--expert-cache` はこのオプションを有効にするときに必要です。

## 値と既定値

- parser は値を `std::atoi` で整数化します。省略時の内部値は `-1` で無効です。`0` と負数も有効化条件 `peer_device >= 1` を満たさないため、tier は開かれません。
- 値の形式や範囲を parser で個別検証していません。数値に変換できない文字列は `atoi` の結果が `0` となり、tier は無効になります。オプションを重ねて指定した場合は、引数走査で後から代入された値が残ります。
- 値を省略すると parser の `next()` が stderr に `--peer-device needs a value` を出し、終了コード `2` で終了します。
- `1` 以上でも指定 GPU が実行時の device 数の範囲外、または主 GPU と同じ ordinal なら、peer cache の初期化に失敗します。

## 実行時の動作

正の値を指定すると、engine は起動時に mapped host buffer を portable 扱いに設定し、prefill の prompt path に peer device があることを伝えます。通常の expert cache のランキングから主 GPU が保持していない expert を選び、peer GPU の空き VRAMから予約量を引いた範囲で cache を作成します。空き容量に収まる前に選択が止まり、`--peer-slots` が正ならその上限も適用されます。serve の adaptive 更新では peer cache も別に候補を入れ替えます。prefill では `--peer-prefill-rows` が 0 でなければ peer path を構成し、負値の既定設定では chunk × top-k の半分を行数として渡します。

peer cache 初期化時は、両 GPU が相互 P2P access 可能かを調べます。可能な場合も topology と小さな双方向コピーを確認し、安全性またはコピー内容を確認できなければ P2P を使わず pinned host staging に切り替える実装です。P2P が利用できないこと自体はこの経路では失敗条件ではありません。

## 適用条件と副作用

- `--expert-profile` が読み込まれており、主 GPU の `--expert-cache` が正であることが必要です。条件を満たさない場合は stderr に `--peer-device needs --expert-profile and the expert cache` を出し、終了コード `1` で終了します。
- `--layer-split` および `--expert-cache-device1..3`（remote/helper expert cache）とは併用できません。該当時は理由を stderr に出し、終了コード `2` で終了します。
- peer GPU 上に cache・実行用 device memory を確保し、input/result/plan staging 用の portable mapped pinned host memory も確保します。peer GPU の空きが予約量を差し引いた後に残らない場合や、残りのランキング対象がない場合は初期化エラーになります。
- peer 指定時は prefill の fused path を使わず MMQ 用の buffer 配置を保つ分岐があります。
- SYCL parser もこの引数を受け取りますが、同 backend の `PeerExperts::open()` は「second-GPU expert tier is not ported to SYCL yet」として拒否します。したがって SYCL build では正の値を指定しても tier は利用できず、peer 初期化で終了コード `1` になります。

## 出力とエラー

peer cache の初期化成功時は、peer GPU 番号、搭載 expert 数・容量と、主 GPU cache と合わせた総数を stderr に表示します。GPU ordinal 不正、device 操作・memory allocation の失敗、cache を置く余地がない場合は初期化エラーを stderr に出し、呼び出し元は終了コード `1` で終了します。P2P の topology/copy 検査で直接転送を採用しない場合は stderr に理由を表示して host staging を使います。

## 根拠

- `engine/src/program/generate.cpp:913-918` — 内部値と既定値（`peer_device = -1`）。
- `engine/src/program/generate.cpp:1424-1429` — root parser の help 説明と同時使用上の注意。
- `engine/src/program/generate.cpp:3837-3842,4200` — 引数値の取得、欠落時の終了、`atoi` 変換。
- `engine/src/program/generate.cpp:4721-4723` — 正の値を portable mapping と prefill peer flag に反映。
- `engine/src/program/generate.cpp:5256-5263` — layer split / helper cache との併用拒否と終了コード `2`。
- `engine/src/program/generate.cpp:10133-10149` — profile/cache 必須条件、peer cache 起動、成功表示、失敗時の終了コード `1`。
- `engine/src/program/generate.cpp:920-922,13064-13075,15410-15418` — prefill 行数の既定値、peer path の構成と serve 中の adaptive 更新。
- `engine/src/core/peer_experts.cpp:192-201` — device ordinal の範囲・主 GPU との重複検査。
- `engine/src/core/peer_experts.cpp:208-235` — P2P の確認と host staging への切替。
- `engine/src/core/peer_experts.cpp:246-258,264-285` — staging/device memory 確保、VRAM 予約と slot 上限、容量不足エラー。
- `engine/src/prefill/prefill.cpp:780-781,5688-5692` — peer 指定時に fused prefill 経路を避ける分岐。
- `engine/sycl/src/program/generate.cpp:2169,5736-5752`、`engine/sycl/src/core/peer_experts.cpp:19-23` — SYCL parser の受理と peer 初期化時の未対応エラー。
