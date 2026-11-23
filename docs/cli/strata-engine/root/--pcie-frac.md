# `strata --pcie-frac`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`generate` / `serve` の処理） |
| オプション | `--pcie-frac` |
| 別名 | なし |
| 値 | 数値 `N`。ミスした expert のうち GPU が PCIe 経由で読む割合。実行時表現は 0〜256 / 256。 |

## 役割

GPU の VRAM にない expert（miss）の一部を、CPU pool で計算する代わりに GPU がホスト側の expert arena から PCIe 経由で読む割合を指定します。値 0 は PCIe lane を使わず、値 1 は対象となる miss 全体を上限として GPU 側へ回します。割合は各レイヤーの distinct miss に適用され、常に全 miss が存在するとは限りません（`engine/src/core/expert_source.cpp:5476-5477`, `5544-5545`）。

## 使い方

```sh
# serve 起動時の割合を明示する例
./engine/strata --serve --pack ./pack --native ./model.gguf --pcie-frac 0.25

# 単発 generate でも同じエンジン引数を指定する例
./engine/strata --pack ./pack --native ./model.gguf --tokens '1,2,3' --pcie-frac 0
```

## 値と既定値

- parser は次の引数を `std::atof` で `double` に変換します。数値として読めない文字列は `atof` の変換結果 0 として扱われます。オプションを繰り返すと、引数走査の最後に代入された値が残ります（`engine/src/program/generate.cpp:4052`; SYCL parser: `engine/sycl/src/program/generate.cpp:2051`）。
- 値域エラーを返す validation はありません。`pcie_num` への変換時に `round(N * 256)` 相当へ丸め、0〜256 に clamp します。したがって通常の範囲の負値は 0、1 より大きい値は 1 相当になります（`engine/src/program/generate.cpp:14839`, `13176`; generate 経路: `24443-24445`）。
- 値の省略時は内部値 `-1` が使われ、pack・GPU・PCIe の測定結果などに応じた既定値決定へ進みます。Q2_0 canonical pack や native pack で基準値が異なり、NVFP4・HIP gfx12 などにも個別条件があります。リンク帯域の probe が成功すると既定 share を調整し、失敗時は基準値を使います（`engine/src/program/generate.cpp:1039`, `5507-5551`; `engine/src/program/generate.cpp:2865-2873` は gfx12 条件の説明）。
- `STRATA_PCIE_FRAC_DEFAULT` などの環境変数は未指定時の既定値選択に関与します。CLI 値が 0 以上なら既定値計算を通らないため、明示値が優先されます（`engine/src/program/generate.cpp:4777`, `5507`, `5510-5512`）。環境変数文書がある場合は [`STRATA_PCIE_FRAC_DEFAULT`](../../../../envvars/STRATA_PCIE_FRAC_DEFAULT.md) も参照してください。
- `STRATA_PCIE_BALANCE=1` は native pack・単一 GPU・非 batch などの条件で、CPU/GPU の実測コストから PCIe miss 数を決めますが、CLI 値を明示するとこの自動選択条件を満たしません（`engine/src/program/generate.cpp:5563-5569`; `engine/src/core/expert_source.cpp:5543-5545`）。
- `--pcie-frac` の値が欠けている場合、parser の `next()` が stderr に `--pcie-frac needs a value` を出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3841-3846`, `4052`）。

## 実行時の動作

生成・serve の起動時に割合を 0〜256 の整数へ変換し、verify window ごとにレイヤー内の distinct expert miss 数と掛け合わせて GPU 側へ割り当てる個数を決めます。ルーティング順のうち後ろ側の miss が PCIe lane に選ばれ、残りは CPU 側で計算されます。resident expert と peer/helper GPU が保持する expert はこの miss 割合の対象外です（`engine/src/core/expert_source.cpp:5476-5477`, `5483-5492`, `5544-5545`）。

`--serve` で layer split を使うと、明示した一つの割合が全 stage に適用され、stage ごとの PCIe probe による個別設定をスキップします。異なる速度のリンクに stage が分かれていても、この引数だけでは stage ごとの割合を分けられません（`engine/src/program/generate.cpp:4775-4777`, `6682-6689`）。一方、オプションを省略した場合は GPU・pack・backend によって probe または自動調整の経路に入ることがあります。

serve では明示した割合が起動時の初期値になりますが、request JSON の `pcie_frac` が指定されると、その request に限って 0〜1 に clamp した値で上書きされます（`engine/src/program/generate.cpp:18755`, `18816`, `21336-21341`）。起動時に `--pcie-frac` を指定しない場合に限り、対応 backend / GPU 条件で初期 probe 後の PcieAuto が decode windows の miss と CPU pool の計測を使って share を更新することがあります。更新値と計測は stderr に出力されます（`engine/src/program/generate.cpp:14821-14838`, `14909-14931`）。

0 を指定すると、対象 miss は CPU 側に残ります。条件が整えば verifier は PCIe share を使わない計画経路へ切り替わります（`engine/src/program/generate.cpp:14966-14971`）。GPU と CPU で expert を計算する経路は丸めが異なる場合があり、実行結果の末尾ビットや出力が変わり得る旨が実装コメントに記されています（`engine/src/program/generate.cpp:2868-2870`）。

## 適用条件と副作用

- CUDA/HIP 系と SYCL 系に parser があります（`engine/src/program/generate.cpp:4052`; `engine/sycl/src/program/generate.cpp:2051`）。ただし既定値と保護条件は backend ごとに同一ではありません。
- SYCL の Intel `xe` driver で `--stream-experts` が無効な場合、未指定なら share を 0 に変更します。正の明示値は維持されますが、pageable host memory を GPU が読むため hang / device loss の危険があるという警告を stderr に出します（`engine/sycl/src/program/generate.cpp:2832-2833`, `2863-2877`）。
- layer split で明示値を使うと全 stage の PCIe share が同じになり、個別リンク probe が省かれます（`engine/src/program/generate.cpp:4775-4777`, `6682-6689`）。
- 割合が 0 より大きいと GPU がホスト側 arena からデータを読む経路が有効になり得ます。割合だけで読み取りが必ず起きるわけではなく、そのレイヤーに miss があることや、backend / source が PCIe read を利用できることが条件です（`engine/src/core/expert_source.cpp:5544-5545`）。
- 値の設定自体はファイル出力やネットワーク接続を行いません。serve 起動中は上記の request-level 上書きや、条件付きの PcieAuto 更新があります。

## 出力とエラー

- 欠落値は stderr にエラーを出し終了コード 2 です（`engine/src/program/generate.cpp:3841-3843`）。
- 不明な引数は stderr に `unknown argument: ...` と usage を出して終了コード 2 ですが、これは `--pcie-frac` 固有ではありません（`engine/src/program/generate.cpp:4264-4269`）。
- 指定値の範囲外を拒否する専用エラーはありません。変換後の `pcie_num` が 0〜256 に clamp されます（`engine/src/program/generate.cpp:14839`）。
- SYCL xe driver で pageable memory を読む可能性がある正の明示値には `WARNING` を stderr に出します。値は自動的に 0 へ戻されません（`engine/sycl/src/program/generate.cpp:2873-2877`）。

## 根拠

- `engine/src/program/generate.cpp:1039-1041` — 値の保持方法と未指定 sentinel、auto 状態。
- `engine/src/program/generate.cpp:4052` — CUDA/HIP 系 parser。
- `engine/sycl/src/program/generate.cpp:2051` — SYCL parser。
- `engine/src/program/generate.cpp:4775-4777`, `6682-6689` — multi-GPU stage への適用と probe 抑止。
- `engine/src/program/generate.cpp:5507-5558` — 既定値、probe、環境変数による分岐。
- `engine/src/core/expert_source.cpp:5476-5477`, `5483-5492`, `5544-5545` — distinct miss のうち PCIe 経由で GPU に割り当てる処理。
- `engine/src/program/generate.cpp:14839`, `14909-14931`, `21336-21341` — 割合の量子化、自動更新、serve request の上書き。
- `engine/sycl/src/program/generate.cpp:2832-2833`, `2863-2877` — SYCL xe driver の条件付き変更と警告。
