# `--native-moe-combine`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（CMake 生成の `strata` エンジン） |
| オプション | `--native-moe-combine` |
| 別名 | なし |
| 値 | 取らない真偽値フラグ |

## 役割

MoE の routed expert 出力を routing weight で加重合算し、shared expert 出力を加える処理に、実験的な pinned CUDA weighted-reduction カーネルを選びます。既定では無効です。エンジンのヘルプも「experimental pinned CUDA routed/shared combination」と説明しています（`src/program/generate.cpp:847`）。

## 使い方

トークン ID を指定するエンジンの例です。`PACK` はモデル pack のディレクトリに置き換えます。

```sh
strata generate --pack PACK --tokens "1,2,3" --native-moe-combine
```

エンジンの使用形式は `strata generate --pack DIR --tokens "…" [options]` です（`src/program/generate.cpp:806-812`）。

## 値と既定値

- 値は不要です。指定すると `Options::native_moe_combine` を `true` にします。初期値は `false` で、同じフラグを複数回指定しても同じ値のままです（`src/program/generate.cpp:445`, `src/program/generate.cpp:2490-2492`）。
- `--native-moe-combine=...` のような値形式や、フラグ専用の値検証は parser にありません。未指定なら標準 MoE combine が選ばれます（`src/program/generate.cpp:2490-2492`, `src/program/generate.cpp:3932-3937`, `src/core/layer.cpp:514-529`）。
- `--native SHARD1` を指定した場合、このフラグも自動的に有効になります。`--native` は複数の native 経路をまとめて有効化する preset です（`src/program/generate.cpp:3232-3267`）。

## 実行時の動作

- 初期化時にフラグ値を `native_moe_combine_set_enabled` へ渡し、カーネルの有効状態を設定します（`src/program/generate.cpp:3932-3937`, `src/kernels/cuda/native_moe.cu:31-34,150-151`）。
- 通常の MoE 層では、この状態が有効なら `native_moe_combine`、無効なら既存の `moe_combine` を呼びます。native 側は各 expert の `parts` と、その層の router が作った `weights` を対応させて加重合算し、shared expert 出力を加算します（`src/core/layer.cpp:514-529`）。
- native カーネルは expert 数 `k` が1〜15、埋め込み幅が正で `int` 範囲内、CUDA stream があることを要求します。出力領域と入力領域の重なり、float 境界に整列していない span も拒否します（`src/kernels/cuda/native_moe.cu:152-175`）。`k=10`、shared 出力あり、幅が4要素単位、parts/shared/output が16-byte 整列の場合は float4 カーネルを使い、それ以外は scalar カーネルを使います（同 `:164-173`）。
- 複数 token の verify 経路では、native combine が有効で decode batch の token 数が2以上なら multi-token カーネルを使います。verify の expert-hit 加算も融合する経路は、追加で token 数1〜8、`k=10`、幅とアドレスの条件、profiling/remote/shared-gate 条件を満たす必要があります。条件を満たさない場合は通常の hit-add 後に combine する経路へ進みます（`src/core/verify.cpp:2168-2172,2179-2199`; カーネル側条件: `src/kernels/cuda/native_moe.cu:177-205`）。
- MTP の複数 token 経路でも、フラグが有効なら multi-token combine を呼びます（`src/core/mtp.cpp:1143-1154`）。
- Strata の Qwen3.6-35B-A3B family switch は GGUF を見て通常 parser より前に `src/qwen35` へ argv 全体を渡します（`src/program/generate.cpp:2393-2408`）。その実装の通常モードでは `--native-moe-combine` を受理せず、unknown option として usage を出し終了コード2を返します。`--serve` モードでは未知の `--` option を警告して無視します（`src/qwen35/q36_engine.cu:3742-3749,3782-3795`）。この family に本オプションの効果は適用されません。

## 適用条件と副作用

- 実際の置換先は CUDA native kernel です。`src/kernels/cuda/native_moe.cu` は CUDA kernel として定義され、CMake の CUDA kernel source 群に含まれます（`CMakeLists.txt:388-400`）。CUDA backend 以外の build でこのフラグを指定した場合の挙動は、この調査ではビルド生成バイナリを実行して確認していません。
- カーネルは device stream に処理を enqueue し、入力 span・カーネル起動エラーを検査します（`src/kernels/cuda/native_moe.cu:152-175,193-208`）。性能向上は測定していないため断定しません。
- `--native` preset と併用すると本フラグ単体の指定がなくても有効になります（`src/program/generate.cpp:3263-3267`）。

## 出力とエラー

- このフラグ単独の parser validation、警告、成功時メッセージはありません。カーネルの無効な引数・span は例外になり、通常 MoE 経路では `blk.<layer>.moe_combine: <error>` として呼び出し元へ返されます（`src/kernels/cuda/native_moe.cu:154-163`, `src/core/layer.cpp:523-529`）。verify 経路の例外は `verify combine: <error>` になります（`src/core/verify.cpp:2179-2193`）。
- CUDA launch の失敗は `cudaGetLastError()` の文言を含む例外になります（`src/kernels/cuda/native_moe.cu:174-175,207-208`）。その後のエンジン全体での表示・終了コードは、この個別 combine 関数の根拠範囲では特定していません。

## 根拠

- parser、既定値、ヘルプ、preset、有効状態の設定: `src/program/generate.cpp:445,806-812,847,2490-2492,3232-3267,3932-3937`
- 通常経路の切替と失敗伝播: `src/core/layer.cpp:514-529`
- CUDA kernel の選択、入力条件、launch error: `src/kernels/cuda/native_moe.cu:31-64,150-175,177-208`
- verify/MTP の複数 token 経路: `src/core/verify.cpp:2168-2199`, `src/core/mtp.cpp:1143-1154`
- Qwen3.6 family への引数委譲と同 family parser: `src/program/generate.cpp:2393-2408`, `src/qwen35/q36_engine.cu:3735-3795`
- CUDA build への source 登録: `CMakeLists.txt:388-400`

この調査では parser とソース上の呼び出し経路を確認しました。既存バイナリの `--help`、CUDA/HIP のビルド差、実機動作、性能は確認していません。
