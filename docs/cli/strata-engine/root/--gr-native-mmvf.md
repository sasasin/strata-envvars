# `--gr-native-mmvf`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--gr-native-mmvf` |
| 別名 | なし |
| 値 | 値なしの真偽値フラグ |

## 役割

GR（hyper-connection）の正規化・射影・後段計算に、固定された native MMVF 実装を選びます。この経路では入力 activation を FP32 のまま使い、射影に BF16 重みと FP32 入力の MMVF カーネルを使います。単なる FP32 activation 指定より適用範囲が広く、native の weighted RMSNorm、非線形・結合計算、GR write も選択します（`engine/src/kernels/cuda/gr.cu:410-423,517-521`、`engine/include/strata/kernels/gr.hpp:33-38`）。

## 使い方

```sh
strata generate --pack ./pack --tokens "1,2,3" --gr-native-mmvf
```

`--pack` と `--tokens` は `strata generate` の基本入力です（`engine/src/program/generate.cpp:1208-1214`）。

## 値と既定値

値を取りません。parser はオプションが現れると `Options::gr_native_mmvf` を `true` にし、`Options` の初期値は `false` です。複数回指定しても同じ `true` を設定するだけです。値の検証はありません（`engine/src/program/generate.cpp:779,3912-3914`）。

`--native` モデル設定を使う場合は、このフラグも内部で `true` に設定されます（`engine/src/program/generate.cpp:5155-5164`）。

## 実行時の動作

起動時に値を GR kernel 設定へ渡します。native MMVF が有効なら FP32 activation を使い（`fp32_activations || native_mmvf`）、GR read の正規化・down/up 射影・SiLU・結合処理に native 実装を選びます。GR write も native の post kernel に切り替わります（`engine/src/program/generate.cpp:6104-6105`、`engine/src/kernels/cuda/gr.cu:410-423,517-521`）。

`--gr-fp32-activations` だけを指定した場合も activation は FP32 になりますが、native MMVF 射影と native write は選ばれません（`engine/src/program/generate.cpp:3912-3914`、`engine/src/kernels/cuda/gr.cu:410-424,517-521`）。

レイヤーの fused GR は、このフラグに加えて `--no-fused-gr` がなく、GPU stages・layer dump・half dump・stage timing がいずれも無効な場合だけ有効になります。これらの条件で fused GR が無効でも、native MMVF 設定自体は GR kernel に渡されます（`engine/src/program/generate.cpp:6112-6114`）。

## 適用条件と副作用

- native 射影は `hc * n_embd` と `hc_lr` がともに偶数であることを要求します。条件を満たさない native read は `std::invalid_argument` を送出します。これは CLI parser の事前検証ではなく、kernel 実行時の制約です（`engine/src/kernels/cuda/gr.cu:414-416`）。
- 複数 token の GR read/write は、必要な作業領域があり `STRATA_NO_MULTI_GR` で無効化されていない場合に multi-token native 経路を使います。そうでなければ read は token ごとの処理にフォールバックし、write も通常の `gr_write` 呼出しに戻ります（`engine/src/kernels/cuda/gr.cu:466-509,531-545`）。関連設定: [`STRATA_NO_MULTI_GR`](../../../envvars/STRATA_NO_MULTI_GR.md)。
- kernel 起動または同期で CUDA エラーが発生した場合、GR read はエラー内容を stderr に出して終了コード `1` で終了します（`engine/src/kernels/cuda/gr.cu:452-462`）。

## 出力とエラー

フラグを受理したことを示す専用出力は parser にありません。未知の引数は `unknown argument: ...` と usage を stderr に出し、終了コード `2` で拒否されます（`engine/src/program/generate.cpp:4268-4274`）。次元制約違反は GR kernel の実行時例外になります（`engine/src/kernels/cuda/gr.cu:414-416`）。

## 根拠

- 索引上のツール ID・parser scope: `docs/cli/000_cli_tools.md:10`。
- オプション一覧: `docs/cli/README.md:1104`。
- parser、既定値、`--native` からの暗黙設定: `engine/src/program/generate.cpp:779,3912-3914,5155-5164`。
- GR kernel の切替、制約、失敗経路: `engine/src/kernels/cuda/gr.cu:410-423,452-462,466-509,517-545`。
- fused GR の適用条件と kernel 設定の API 契約: `engine/src/program/generate.cpp:6104-6114`、`engine/include/strata/kernels/gr.hpp:27-38`。
