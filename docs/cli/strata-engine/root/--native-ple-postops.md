# `--native-ple-postops`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（`generate` エンジン parser） |
| オプション | `--native-ple-postops` |
| 別名 | なし |
| 値 | 値なしのフラグ。指定すると有効 |

## 役割

PLE（Per-Layer Embeddings）ブロックの投影後処理に、実験的なネイティブ演算経路を選びます。対象はキーとクエリの正規化、ゲート、値のブロードキャスト、畳み込み、残差加算です。キー／値の投影方式を選ぶオプションとは独立しています（`include/strata/kernels/ple.hpp:38-42`）。

## 使い方

`strata generate` の引数として指定します。例では既存の pack と PLE GGUF、トークン列を使います。

```sh
strata generate --pack /models/pack --ple-gguf /models/ple.gguf \
  --tokens 1,2,3 --native-ple-postops
```

エンジンの usage は `--pack`、`--tokens`、`--ple-gguf` を案内しており、`--tokens` または `--tokens-file` が必要です（`src/program/generate.cpp:806-818`, `3174-3178`）。

## 値と既定値

このスイッチは値を取りません。parser は引数が `--native-ple-postops` と一致したとき `o.native_ple_postops = true` にします（`src/program/generate.cpp:465`, `2497`）。Options の初期値は `false` なので、省略時は従来の PLE 後処理経路です（同 `:465`）。繰り返し指定しても同じ真偽値を設定するだけです。

## 実行時の動作

初期化時に parser の値が `ple_set_native_postops` へ渡されます（`src/program/generate.cpp:3959`）。CUDA PLE 実装はこの状態を保持し、有効時にキー／クエリの正規化、ゲート、値のブロードキャスト、正規化、畳み込みと残差加算を `native_ple_postops` に委譲します。無効時は従来の個別カーネル列を使います（`src/kernels/cuda/ple.cu:199-202`, `319-350`）。ネイティブ演算自体は明示 stream、ポインタの有効性・alignment・範囲、入出力の重なりを検査し、CUDA kernel launch error を例外にします（`src/kernels/cuda/native_ple_postops.cu:217-255`）。

`--native` はモデル由来の PLE shard を解決した後、このフラグを含む複数の native スイッチを有効化します（`src/program/generate.cpp:3232-3268`）。そのため、`--native` と併用した場合は個別指定なしでもこの後処理が有効です。

prefill の chunk 全体をまとめて処理する経路は、このスイッチだけでは選ばれません。PLE が有効であることに加え、`STRATA_PLE_BATCH`（未設定なら有効、`0` なら無効）、対応する BF16/native キー重み、scratch 領域の容量が必要です。条件を満たさない場合は token ごとの経路に進みます（`src/prefill/prefill.cpp:2669-2678`, `3119-3164`）。これは後処理を有効にするフラグと、prefill のバッチ化条件が別であることを示します。

## 適用条件と副作用

- `--no-ple` と同時に指定すると、`strata generate: --native-ple-postops requires PLE enabled` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:3290-3296`）。また、PLE を無効にせず `--ple-gguf` も解決できない場合は、別の必須引数エラーになります（同 `:3298-3300`）。
- 指定すると通常の CUDA PLE ブロックがネイティブ後処理を選択します。生成される値に関わる演算経路が変わり、PLE の畳み込み履歴も更新されます（`src/kernels/cuda/ple.cu:335-350`; `src/kernels/cuda/native_ple_postops.cu:247-255`）。フラグによる性能向上や出力の同一性は、このソース確認だけでは保証できません。
- `--native` の設定スイッチ群は session configuration fingerprint にも記録されます（`src/program/generate.cpp:9450-9462`）。
- SYCL 側にも同名 setter と PLE 経路があります（`sycl/src/kernels/cuda/ple.dp.cpp:285-286`, `433-522`）。個別の build 構成や配布バイナリで当該経路が利用可能かは、このソース checkout だけでは確認していません。

## 出力とエラー

オプション単体の成功時に固有のメッセージやファイル出力はありません。parser が未知の引数を受け取った場合は `unknown argument` と usage を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2787-2792`）。ネイティブ kernel 呼び出しで引数検査または launch 検査が失敗すると例外になります（`src/kernels/cuda/native_ple_postops.cu:217-255`）。呼び出し側の実行結果・終了コードは失敗箇所に依存するため、当該オプション固有の固定値としては確認できません。

## 根拠

- parser の初期値、usage、認識処理: `src/program/generate.cpp:465`, `842-859`, `2490-2500`
- `--native` による暗黙の有効化、PLE 必須条件、`--no-ple` との拒否: `src/program/generate.cpp:3232-3268`, `3290-3300`
- 初期化時の setter と session fingerprint: `src/program/generate.cpp:3959`, `9450-9462`
- CUDA PLE の切り替えと演算列: `src/kernels/cuda/ple.cu:199-202`, `319-350`
- ネイティブ演算の入力・出力検査、launch: `src/kernels/cuda/native_ple_postops.cu:217-255`
- prefill バッチ化の追加条件: `src/prefill/prefill.cpp:2669-2678`, `3119-3158`
- オプションの索引と scope: `docs/cli/README.md:1128-1134`, `1217-1219`
