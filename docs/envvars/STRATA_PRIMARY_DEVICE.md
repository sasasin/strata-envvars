# `STRATA_PRIMARY_DEVICE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

標準の `strata generate` / `strata serve` 経路で、モデル本体のセッションが使う可視 GPU ordinal を選びます。既定は ordinal 0 です。値が正なら、起動後にエンジン本体のスレッドをその GPU に切り替えます。helper expert cache の配置と peer expert tier もこの primary ordinal を参照します。

この設定は `src/program/generate.cpp` でのみ環境から読まれます。Qwen3.5 MoE の専用エンジンへ振り分けられる場合は、その分岐がこの設定の読み取りより先に行われるため、この経路では適用されません。`--version`、`--families`、`--help` など通常の生成処理に入らず終了する経路も読み取りません。

## 値と判定

通常経路では `std::atoi` で整数に変換し、変換結果が正の場合だけ指定値を採用します。未設定、空文字、0、負数、整数の先頭として読めない文字列は ordinal 0 になります。`atoi` のため文字列全体の厳密な検証はなく、先頭の空白や符号を許し、数値の後ろに文字があっても数値部分を使います（例: `2x` は 2）。大文字小文字の規則はありません。整数型の範囲外の入力は有効な指定値として扱えません。

| 入力例 | 採用される ordinal | 結果 |
|---|---:|---|
| unset、空文字、`0`、`-1`、`abc` | 0 | runtime の既定 primary を維持 |
| `1`、`2`、`  +2tail` | 変換された正整数 | 指定 ordinal を使う。可視 GPU 範囲内である必要がある |
| GPU 数以上の正整数 | 指定 ordinal | 可視 GPU がないとしてエラー終了 |

CLI 引数による同等設定や上書きはありません。`--gpu` は CUDA/HIP の可視デバイス集合を先に設定するため、`STRATA_PRIMARY_DEVICE` はその後の可視 ordinal に対して解釈されます。たとえば `--gpu` でデバイスを絞った場合、指定できる ordinal は絞り込み後の並びに対する番号です。

## 有効になる条件

- 標準の generate/serve エンジン経路に入ること。Qwen3.5 MoE は `strata::qwen35::run` に先行して分岐するため、この選択処理を通りません。
- 0 以外を指定する場合、その番号が runtime の列挙する可視 GPU の範囲内であること。HIP ビルドではさらに、primary と実際に使う helper GPU がビルド済みアーキテクチャに対応する必要があります。
- `--layer-split` との併用は、指定値が 0 以外なら拒否されます。後段 GPU の split-device 番号が primary 0 前提のためです。
- Windows HIP でカードの runtime ordinal 固定順を変えるものではありません。選択した可視 ordinal にエンジン本体を置きます。`--gpu` / `HIP_VISIBLE_DEVICES` のフィルター後の ordinal が対象です。

helper cache を使う場合、primary が 0 なら既定の CUDA1..3 配置を使い、primary が非 0 なら可視 GPU から primary を除いた ordinal を順番に helper 候補にします。不足分は無効値 `-1` になります。peer tier は `primary_device()` を使って primary と peer の P2P 可否判定・有効化を行います。helper や peer 機能自体を有効にする設定ではなく、それらの GPU 選択・primary 参照に作用する設定です。

## 実行時の詳細

通常経路では CLI 引数を解析した後、`STRATA_PRIMARY_DEVICE` を一度読み、`set_primary_device()` に保存します。値の再読込やリクエストごとの評価はありません。のちに primary が 0 以外なら、可視 GPU 数を確認してから `cudaSetDevice()` を呼び、成功時は stderr に `strata generate: primary device from STRATA_PRIMARY_DEVICE: CUDA<N>` を出します。可視範囲外は `no such visible device` を出して終了コード 2、`cudaSetDevice` の失敗はエラー文を出して終了コード 1 です。0 の場合は切替もこのログもありません。

primary の検証・切替はモデルの重みやエンジン arena の割り当てより前ですが、起動時の一部 GPU 照会や backend の初期化はこの選択処理より前に ordinal 0 で実行されます。したがって、この変数が起動時のすべての GPU 照会先を変更するわけではありません。

通常経路とは別に、HIP で `STRATA_HIP_GFX906` 以外のビルドは `prime_hw_queues()` でもこの値を読みます。これは CLI 解析と通常の primary 保存より前です。ここでは `atoi` 結果が正ならその ordinal、そうでなければ 0 を queue primer の対象にします。デバイス数取得失敗または範囲外なら queue primer は何もせず戻ります。`STRATA_HIP_QUEUE_PRIME=0` の場合はこの関数が先に戻るため、primary も読みません。これは HIP queue 初期化の対象選択であり、通常経路における範囲エラーの検出・終了処理とは別です。

## 根拠

- `src/program/generate.cpp:2957-2979` — `--gpu` が最初の CUDA/HIP 呼び出し前に可視デバイス環境を設定する処理。
- `src/program/generate.cpp:2980-2999` — Qwen3.5 MoE への先行分岐と、HIP の queue primer 呼び出し。
- `src/program/generate.cpp:2748-2768,2791-2804` — HIP queue primer 側の独立した環境読み取り、整数変換、範囲確認、選択デバイス上での初期化。
- `src/program/generate.cpp:3566-3575` — 標準経路での `atoi` 判定と primary ordinal の保存。
- `src/program/generate.cpp:3637-3645` — 非 0 primary と layer split の拒否。
- `src/program/generate.cpp:3663-3675,3755-3769` — helper ordinal の選択と HIP build architecture の確認。
- `src/program/generate.cpp:4140-4158` — primary の可視範囲確認、デバイス切替、ログと失敗終了。
- `src/program/generate.cpp:5933-5939` — main session の初期化を primary ordinal 上で行う箇所。
- `include/strata/core/device.hpp:51-57`, `src/core/device.cu:87-92` — primary ordinal の意味とプロセス内保存。
- `src/core/remote_experts.cpp:71-81,136-149`, `src/core/peer_experts.cpp:125-154` — helper の primary 重複拒否と peer tier の primary 参照。
