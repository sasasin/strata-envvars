# `--gr-native-mmvf`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。Terminal CLI とは別） |
| オプション | `--gr-native-mmvf` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

GR（gated residual / hyper-connection）の正規化と投影に、固定された native MMVF 実装を選びます。このモードは FP32 活性値も有効にします。エンジンの help は experimental と記載しています。

## 使い方

```sh
strata --pack ./pack/full --tokens "1,2,3" --gr-native-mmvf
```

`strata generate` の usage が示す基本形は `strata generate --pack DIR --tokens LIST [options]` です。実際の build で公開される実行ファイル名に合わせて呼び出してください。

## 値と既定値

値は不要です。指定すると真偽値を `true` にし、未指定時は `false` です。繰り返し指定しても同じ値のままです。値を続けて書いてもこのオプションの値として消費されず、別の引数として解析されます。独自の範囲 validation はありません。

## 実行時の動作

エンジンはオプションを受け取ると `Options::gr_native_mmvf` を有効にします。起動時にこの値を CUDA GR カーネル設定へ渡し、カーネル側では `native_mmvf` が有効なら native RMSNorm、BF16 重みと FP32 入力を使う down/up MMVF 投影、および native GR 前処理・後処理を選びます。native モードでは `fp32_activations` の個別指定がなくても FP32 入力経路になります。

また、native GR の指定があり、`--no-fused-gr`、`--gpu-stages`、`--dump-layers`、`--dump-halves`、`--stage-timing` のいずれも指定されていない場合、層側の fused GR も有効になります。これらの条件で fused GR が無効でも `native_mmvf` 自体は無効化されず、非 fused GR 呼び出しでも native GR の投影・書き込み経路が選択されます。

`--native` モデル経路は、このフラグを内部で有効化します（他の native 関連フラグや `--stream-token` も同時に設定）。その経路でフラグだけを独立して切り替える指定ではありません。

## 適用条件と副作用

実装されている効果は CUDA GR カーネル経路にあります。native MMVF は GR の `hc*n_embd` と `hc_lr` がともに偶数であることを要求し、満たさない場合 `std::invalid_argument` を送出します。複数 token の native GR 経路は `n_tok > 1` かつ multi 用作業領域が揃う場合に選択されます。環境変数 `STRATA_NO_MULTI_GR` が空でない値（先頭文字が `0` 以外）なら複数 token 専用経路を抑止し、通常の token ごとの処理へ戻ります。

カーネル起動エラーや同期エラーは stderr に CUDA エラーを出し、GR の一部経路では `exit(1)`、native helper では例外となります。専用フラグに対する起動時の追加出力、性能向上の保証、他 backend での同等性はソースから確認できません。

## 出力とエラー

オプション自体の値検証エラーはありません。未知の余剰引数は `unknown argument: ...` と usage を stderr に出し、終了コード `2` になります。GR 実行時は形状不適合で例外、CUDA launch/synchronize 失敗で CUDA エラー表示と終了（または helper から例外）になる経路があります。例外の最終表示・終了コードは呼び出し元の処理に依存し、ここでは一律に確定できません。

## 根拠

- `src/program/generate.cpp:440-441` — オプション状態と既定値。
- `src/program/generate.cpp:840-843` — help 表示と FP32 活性値への含意。
- `src/program/generate.cpp:2416-2423,2484-2488` — 引数ループ、フラグとしての解析。
- `src/program/generate.cpp:2787-2792` — 未知引数の stderr、usage、終了コード `2`。
- `src/program/generate.cpp:3258-3268` — `--native` 経路が当該フラグを暗黙に有効化する箇所。
- `src/program/generate.cpp:3922-3932` — GR カーネル設定と fused GR の適用条件。
- `src/kernels/cuda/gr.cu:349-351,410-423` — 設定の保持、native による FP32 経路、native GR の正規化・投影。
- `src/kernels/cuda/gr.cu:414-416,479-503` — 偶数形状の要件と複数 token native 経路の CUDA 失敗処理。
- `src/kernels/cuda/gr.cu:466-472,517-543` — `STRATA_NO_MULTI_GR` と native GR 書き込み処理。
- `src/kernels/cuda/native_gr_norm.cu:91-106`、`src/kernels/cuda/native_gr_postops.cu:97-109` — native helper の引数・起動検証。
