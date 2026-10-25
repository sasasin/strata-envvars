# `--no-fused-gdn`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジンのトップレベル CLI） |
| オプション | `--no-fused-gdn` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

対応する GDN 層で、融合 GDN カーネルを使わないようにします。実装の A/B 比較や診断に使えるスイッチです。CUDA/HIP 実装と SYCL 実装の両方に parser と切替処理があります（`src/program/generate.cpp:2785,3928`、`sycl/src/program/generate.cpp:2063,3006`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --no-fused-gdn
```

`strata generate` の構文は `src/program/generate.cpp:806-812` に定義されています。実際の実行にはモデル pack と有効な入力トークンが必要です。

## 値と既定値

値は不要です。オプションを省略すると `no_fused_gdn` は `false` のままで、融合 GDN は許可されます（`src/program/generate.cpp:607`、`src/core/layer.cpp:51`）。指定すると parser が `true` にします。値の範囲検証はありません。同じフラグの複数指定は同じ真値を設定するだけです（`src/program/generate.cpp:2785`）。値を後ろに付けず別引数で渡すと、その引数は別のオプションとして解析されます。

## 実行時の動作

parser の値は `layer_set_fused_gdn(!o.no_fused_gdn)` に渡されます（`src/program/generate.cpp:3926-3929`）。通常の GDN 層では、融合前処理（畳み込み・正規化と alpha/beta 計算）と、GDN step・出力 norm の融合呼び出しを無効にします。代わりに、前処理は個別の処理へ、step と出力 norm は `native_gdn_step` と `native_gdn_out_norm` へ分けて実行します（`src/core/layer.cpp:280-307,321-345,347-369`）。SYCL 側も同じ条件と代替経路です（`sycl/src/core/layer.cpp:274-307,320-337,339-361`）。

この切替は `native_gdn_enabled()` が有効な場合に融合処理の選択へ影響します。`--native` は `native_gdn` を有効にし、個別指定では `--native-gdn` が有効化します（`src/program/generate.cpp:2492,3263-3267,3937`）。ネイティブ GDN が無効なら融合条件が成立しないため、このフラグによる実行経路の変化はありません。融合前処理はさらに BF16 projection、有効な形状 `ssm_d_conv == 4` と `ssm_state_size == 128` が条件です。step と norm の融合は `ssm_state_size == 128` も条件です（`src/core/layer.cpp:282-283,349`）。

このフラグはセッション設定 fingerprint に `no_fused_gdn` として含まれます（`src/program/generate.cpp:9458-9467`）。したがって設定識別にも反映されます。直接のファイル・ネットワーク操作は確認できません。

## 適用条件と副作用

- `--verify` の検証窓は既定の fused native decode path との互換性を要求します。このフラグを指定すると fused GDN が無効になり、互換性チェックが失敗し、`verify: the fused native GDN kernels are off ...` のエラーになります（`src/core/layer.cpp:537-546`、`src/core/verify.cpp:732-735`）。SYCL でも同じチェックがあります（`sycl/src/core/layer.cpp:539-547`、`sycl/src/core/verify.cpp:493-495`）。
- Qwen3.6-35B の専用経路は共通 parser より前に分岐します（`src/program/generate.cpp:2393-2407`）。専用 parser は通常の生成モードではこのフラグを認識せず、unknown option として終了コード 2 で拒否します。serve モードでは未知の `--...` 引数を警告して無視するため、このフラグも効果を持ちません（`src/qwen35/q36_engine.cu:3742-3795`）。
- 通常 parser における未知引数は stderr に `unknown argument` と usage を出して終了コード 2 です（`src/program/generate.cpp:2787-2792`）。現行 `usage()` の表示には `--no-fused-gdn` の項目がありません（`src/program/generate.cpp:806-875`）。つまり parser は受理しますが、`--help` のオプション一覧からは確認できません。

## 根拠

- CUDA/HIP の parser・既定値・適用: `src/program/generate.cpp:607,2785,3926-3929`
- SYCL の parser・適用: `sycl/src/program/generate.cpp:585,2063,3004-3007`
- 融合経路と代替経路、条件: `src/core/layer.cpp:280-307,321-369`、`sycl/src/core/layer.cpp:274-307,320-361`
- 検証との相互作用: `src/core/layer.cpp:537-549`、`src/core/verify.cpp:732-735`
- Qwen3.6-35B の委譲と専用 parser: `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3742-3795`
- 索引上の配置: `docs/cli/README.md:1227`（`strata-engine/root` の指定リンク）

## 調査範囲

ソース checkout の CUDA/HIP、SYCL、Qwen3.6-35B の該当 parser・使用箇所を確認しました。同一 revision の既存 CLI help は実行していません。CUDA/HIP と SYCL のビルド済みバイナリ、各 GPU での実動作・性能差は確認していません。
