# `--native-ple-key`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数） |
| オプション | `--native-ple-key` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。既定値は無効 |

## 役割

PLE（per-layer token embedding）の key 行列 `blk.1.ple_key.weight` を、対応する native dense GGUF から読み込み、対応する量子化形式のままネイティブ CUDA 行列積で使います。parser はこのフラグを指定すると有効化します（`src/program/generate.cpp:444`, `src/program/generate.cpp:2488-2491`）。

## 使い方

```sh
strata --pack pack/full --ple-gguf model-ple.gguf \
  --native-dense-gguf model-native.gguf --native-ple-key \
  --tokens 1,2,3
```

`--native-dense-gguf` は複数回指定できます。実際に使うモデル、pack、および PLE ファイルは手元のモデル構成に合わせてください（`src/program/generate.cpp:863`, `src/program/generate.cpp:2473-2474`, `src/program/generate.cpp:2500-2504`）。

## 値と既定値

- 引数値は不要です。`--native-ple-key` を付けない場合 `native_ple_key` は `false` のままです（`src/program/generate.cpp:444`, `src/program/generate.cpp:2490`）。
- 同じフラグを複数回指定しても同じ boolean を `true` にするだけです。空値や数値の範囲はありません。
- 有効にする場合、`--native-dense-gguf` が少なくとも1つ必要で、`--no-ple` との併用は拒否されます。満たさない場合は stderr に `--native-ple-key requires PLE and --native-dense-gguf` を出し、終了コード 2 で終了します（`src/program/generate.cpp:3403-3405`）。
- ネイティブ行列の候補となる PLE key は `Q2_0`、`IQ3_XXS`、`IQ4_XS`、`Q8_0` です。その他の key 形式は、この native key 対象にせず pack 側の既存 BF16 経路に残します（`src/core/native_dense.cpp:154-165`）。

## 実行時の動作

`NativeDense::served_names` はこのフラグを受け、上記形式の PLE key が native matrix multiplication 対応かつ2次元テンソルの場合、pack から読み込む canonical tensor の skip 集合に含めます（`src/core/native_dense.cpp:178-192`）。既定の `--keep-canonical` なしでは served tensor の canonical copy を読み飛ばします。native pack で非量子化 key がある場合は、それを skip から外して pack 側に保持します（`src/program/generate.cpp:3774-3791`, `src/core/native_dense.cpp:239-247`）。`--keep-canonical` を指定すると canonical copy も読み込まれますが、native key の有効化自体は変わりません（`src/program/generate.cpp:3774-3795`）。

続いて `NativeDense::load` が各 `--native-dense-gguf` を読み、テンソル名・形状・量子化型を照合して GPU メモリへ転送します。`generate` は PLE key の pack 参照が量子化済みの場合、native data、型、Q8_1 入力用領域を PLE weights に設定します（`src/core/native_dense.cpp:265-273`, `src/core/native_dense.cpp:344-374`, `src/program/generate.cpp:4113-4142`）。

verify の複数行バッチ経路では、PLE embedding を `native_quantize_q8_1` で量子化し、`native_mmvq` で key 投影します（`src/core/verify.cpp:1267-1289`）。chunk prefill で PLE batching が有効になり、key が native/BF16 のいずれかで、native PLE postops と十分な region memory がある場合は、embedding を F16 に変換して native GEMM で投影します。条件が成立しない場合は per-token 経路になります（`src/prefill/prefill.cpp:2669-2678`, `src/prefill/prefill.cpp:3141-3156`）。

## 適用条件と副作用

- フラグ単独では GGUF の場所を決めません。`--native-dense-gguf` に key を含む shard を渡す必要があります。GGUF 読み込み後に `NativeDense::load` が key の重複、canonical pack での不在、形状不一致などを検出すると失敗します（`src/core/native_dense.cpp:344-363`）。
- PLE 自体が必要です。`--no-ple` は拒否されます。`--native` プリセットは関連 native 経路をまとめて有効にし、`native_ple_key` も true にします。通常は native model shard 群を `native_dense_gguf` に設定する処理もあります（`src/program/generate.cpp:3263-3281`）。
- native load はデバイス上に重み領域を確保して GGUF tensor を転送します。割当・転送失敗時は `NativeDense::load` が `native dense upload <tensor>: <CUDA error>` を返し、呼び出し側はエラーを stderr に出して終了コード 1 で終了します（`src/core/native_dense.cpp:364-374`, `src/program/generate.cpp:3912-3919`）。
- pack 側の key が量子化済みなのに native key のデータ・対応型・Q8_1 領域のいずれかが利用できない場合、PLE の配線時に `native PLE key is absent or incompatible` を stderr に出して終了コード 1 で終了します。pack 側が非量子化（BF16）なら、この native key 接続分岐には入らず pack の BF16 key を使います（`src/program/generate.cpp:4126-4142`）。
- help はこのオプションを experimental と説明しています（`src/program/generate.cpp:846`）。性能や精度の優位性はこの調査では測定していません。

## 根拠

- parser、既定値、help: `src/program/generate.cpp:444`, `src/program/generate.cpp:846`, `src/program/generate.cpp:2488-2491`
- 適用条件と `--native` の自動設定: `src/program/generate.cpp:3263-3281`, `src/program/generate.cpp:3403-3405`
- pack skip と native GGUF の読み込み: `src/program/generate.cpp:3774-3791`, `src/program/generate.cpp:3912-3919`
- 対象 key 型、native tensor 選択・検証・転送: `src/core/native_dense.cpp:154-192`, `src/core/native_dense.cpp:344-374`
- PLE key の接続と実際の使用経路: `src/program/generate.cpp:4113-4142`, `src/core/verify.cpp:1267-1289`, `src/prefill/prefill.cpp:2669-2678`, `src/prefill/prefill.cpp:3141-3156`
- 索引上の scope とリンク: `docs/cli/README.md:1128-1134`, `docs/cli/README.md:1212-1218`
