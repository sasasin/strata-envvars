# `--native-gdn`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数 parser） |
| オプション | `--native-gdn` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

GDN（Gated Delta Network）層の正規化、ゲート、再帰計算に、実験的な pinned CUDA 実装を選びます。Strata はフラグを process-wide の native GDN 有効状態へ渡し、通常経路の GDN 層がその状態を見て native kernel を呼び分けます。CLI の説明も「experimental pinned CUDA GDN norms/gates/recurrence」としています（`src/program/generate.cpp:848`、`:3937`、`src/core/layer.cpp:251-252`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --native-gdn
```

`--pack` と `--tokens` はエンジンの基本引数です。実際のモデルではモデル用 pack と入力 token ID に置き換えてください（`src/program/generate.cpp:806-812`）。

## 値と既定値

- 値を取りません。parser は指定時に bool 値を `true` にし、既定値は `false` です（`src/program/generate.cpp:446`、`:2492`）。
- 同じフラグを複数回指定しても同じ bool を `true` にするだけで、複数指定専用の処理はありません（`src/program/generate.cpp:2492`）。
- 値の範囲を検証する option-level validation はありません。値を後置すると、その文字列は別引数として処理され、未知の引数として usage を stderr に出して終了コード 2 になります（`src/program/generate.cpp:2416-2423`、`:2787-2792`）。

## 実行時の動作

指定されると `native_gdn_set_enabled(true)` が呼ばれ、GDN 層で次の処理が native 実装へ切り替わります（`src/program/generate.cpp:3932-3937`、`src/core/layer.cpp:282-312`、`:337-369`）。

- convolution と SiLU、Q/K の L2 正規化
- beta sigmoid と alpha/dt/ssm_a からの gate 計算
- GDN の状態更新（再帰）
- 出力 RMS 正規化と sigmoid gate

native の再帰 kernel は状態バッファを書き換えるため、通常の推論中に GDN の状態が更新されます（`src/kernels/cuda/native_gdn.cu:48-83`）。native preprocessing と再帰は CUDA stream、バッファの整列・サイズ・重なり、geometry などを実行時検査し、条件違反または CUDA kernel launch error を例外にします（`src/kernels/cuda/native_gdn_preprocess.cu:116-138`、`:142-198`、`src/kernels/cuda/native_gdn.cu:98-123`）。

`--native`（`--native SHARD1`）プリセットを使う場合、このフラグも自動で有効になります。プリセットは `--stream-token`、native BF16 など他の native 経路もまとめて有効化します（`src/program/generate.cpp:3263-3267`）。

## 適用条件と副作用

- 対象は `generate.cpp` の通常 engine parser を通る実行経路です。Qwen3.6 family は parser より前に専用実装へ振り分けられるため、この root option の説明はその専用 parser には適用されません（`src/program/generate.cpp:2393-2407`）。
- native GDN の再帰 kernel は `S=128` を前提とし、コンパイル時に Strata の geometry と一致することを検査します。preprocessing kernel は `d_conv == 4` を要求します（`src/kernels/cuda/native_gdn.cu:37-39`、`src/kernels/cuda/native_gdn_preprocess.cu:142-146`）。
- `--no-fused-gdn` は fused GDN 経路を無効にしますが、native GDN の enabled 状態は別に設定されます。その場合も native 個別 kernel は選択され得ます。融合経路には `g_fused_gdn` に加えて native GDN、state size 128（前処理融合ではさらに native BF16 projections と `d_conv == 4`）が必要です（`src/program/generate.cpp:3928,3937`、`src/core/layer.cpp:282-289`、`:349-368`）。
- Qwen3.6 以外の対応モデルでも、実際の GDN 層でのみ処理に作用します。CLI parser 自体は GPU/モデル状態に応じた可否判定や fallback 警告を出しません。

## 出力とエラー

オプションを受理した時点で専用の成功メッセージを出す処理は確認できません。未知引数は `unknown argument: ...` と usage を stderr に出し、終了コード 2 です（`src/program/generate.cpp:2787-2792`）。実行中の native GDN kernel validation / launch 例外は GDN 層内で `err` に変換され、層処理は失敗を返します（`src/core/layer.cpp:294`、`:307`、`:345`、`:353-355`、`:369`、`:1548`）。最終的な上位呼び出し側の表示・終了コードはこのオプション専用の経路ではないため、ここでは断定しません。

## 根拠

- parser の既定値と宣言: `src/program/generate.cpp:446`
- help 表示・parser 分岐: `src/program/generate.cpp:848`、`:2492`
- `--native` preset による暗黙有効化: `src/program/generate.cpp:3263-3267`
- process-wide 設定と native / 通常 GDN の分岐: `src/program/generate.cpp:3928-3937`、`src/core/layer.cpp:280-312`、`:337-369`
- kernel の validation・状態更新・例外: `src/kernels/cuda/native_gdn.cu:37-39`、`:48-83`、`:98-123`、`src/kernels/cuda/native_gdn_preprocess.cu:116-138`、`:142-198`
- root option の対象外になる Qwen3.6 振り分け: `src/program/generate.cpp:2393-2407`
