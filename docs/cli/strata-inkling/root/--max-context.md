# `strata-inkling --max-context`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root。CUDA/HIP の Inkling-2-Mini エンジン） |
| オプション | `--max-context` |
| 別名 | `--ctx` |
| 値 | 整数として読み取られるコンテキスト長（token/cell 数）。CLI に明示的な範囲検証はない |

## 役割

モデル実行で使う最大コンテキスト長を `BackendOpts::max_ctx` に設定します。通常の直接生成では backend の slot 割り当てに、serve では各 slot と `READY` 応答の上限に使われ、CUDA/HIP backend の初期化では KV 容量見積り・runner の context 容量にも反映されます。ベンチマークでは prompt と生成長の指定が収まらない場合に限り、この値を内部で拡張します。

## 使い方

```sh
# serve モードで最大コンテキストを 65536 token に設定
strata-inkling --serve --native model.strata --max-context 65536

# 同じ設定を別名で指定
strata-inkling --serve --native model.strata --ctx 65536
```

## 値と既定値

- 値は `std::atoi` で整数に変換され、既定値は `BackendOpts::max_ctx` の `32768` です（`engine/src/inkling2/ink_main.cpp:409-410`、`engine/src/inkling2/ink_backend.h:17-19`）。
- parser に正値・上限などの明示的 validation はありません。数値でない文字列を含む場合の `atoi` の変換結果も、Strata 側でエラーとして検査していません（`engine/src/inkling2/ink_main.cpp:409-410`）。
- CUDA は runner 初期化時に `max(256, opts.max_ctx)` を渡し、HIP は `max_ctx_ = max(256, opts.max_ctx)` とするため、これらの backend では指定値が `256` 未満なら実効値は `256` です（`engine/src/inkling2/cuda/ink_cuda_backend.cu:240-245`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:700-702`）。
- `--max-context` と `--ctx` は同じ分岐で同じ値に設定されます。複数回指定した場合は argv を左から処理するたびに代入され、最後に現れた方が残ります（`engine/src/inkling2/ink_main.cpp:379-410`）。

## 実行時の動作

- 通常の直接生成では backend 初期化後、`cfg.bopts.max_ctx` を使って slot 0 を割り当てます（`engine/src/inkling2/ink_main.cpp:564-578`）。CUDA/HIP では backend 初期化時にもこの値を用いて KV の初期容量や runner の context を決めます（`engine/src/inkling2/cuda/ink_cuda_backend.cu:174-181,240-245`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:700-702`）。
- `--serve` では `parallel` 個の slot に設定値を渡し、backend が返す実効値（未提供なら設定値）を `READY <値>` として出力します（`engine/src/inkling2/ink_serve.h:441-465,471-485`）。
- `--bench` では `prompt_len + gen_len > max_ctx` のとき、ベンチマーク専用コピーの `max_ctx` を合計値 `+16` に拡張してから backend を初期化します。そのため、このモードでは指定値が prompt/生成の合計上限としては維持されません。backend の実効上限に収まらない prompt/生成長は clamp され、stderr に通知されます（`engine/src/inkling2/ink_main.cpp:130-157`）。
- 同じ root parser の `--selfcheck`、`--kld-eval`、`--dump-ref` にも値は保持され、それぞれ backend 初期化または slot 割り当てへ渡ります（`engine/src/inkling2/ink_main.cpp:101-127,273-280,324-332,544-549`）。`--info` と `--export-tokenizer` は早期に専用処理へ戻るため、コンテキスト値を使いません（同 `:544-545`）。

## 適用条件と副作用

- 索引でこの root parser の対象は CUDA/HIP (`engine/src/inkling2/ink_main.cpp`) です。CUDA/HIP では context 長が KV 容量見積りや runner 容量に関わり、長くすると必要メモリが増える可能性があります。CUDA の初期 KV 見積りは KV offload 設定・GPU メモリ・parallel 数でも変わります（`engine/src/inkling2/cuda/ink_cuda_backend.cu:170-191`）。
- `--bench` はこの値を内部拡張する場合があります。serve の `READY` 値は backend の実効値を示すため、指定値と一致しない場合があります（`engine/src/inkling2/ink_main.cpp:137-157`、`engine/src/inkling2/ink_serve.h:471-485`）。
- このオプションは context 上限の設定であり、モデル自体の学習済み context 長を変更する処理は parser から確認できません。

## 出力とエラー

- 引数値を省略した場合は `next()` が `missing value after --max-context` を stderr に出して終了コード `2` で終了します（`engine/src/inkling2/ink_main.cpp:380-383,409-410`）。
- `--bench` では prompt または生成長を実効 context 内に収める clamp が起きると、stderr に `[bench] clamping ...` を出します（`engine/src/inkling2/ink_main.cpp:147-156`）。
- モデル読み込み失敗は `open: ...`、backend 初期化失敗は `init: ...`、通常生成の slot 割り当て失敗は `alloc_slot: ...` を stderr に出して終了コード `1` になります（`engine/src/inkling2/ink_main.cpp:556-578`）。serve の初期化・slot 割り当て失敗はプロトコルの `ERR` 応答を出して終了コード `1` です（同 `:564-572`、`engine/src/inkling2/ink_serve.h:458-464`）。
- parser に context 値の範囲エラー専用メッセージはありません。大きな値を設定した際の具体的なメモリ確保失敗条件・CUDA/HIP ランタイムの診断文言は、該当 backend と実行環境に依存するため、このソース調査だけでは一律に特定できません。

## 根拠

- parser、別名、数値変換、ヘルプ上の serve 構文: `engine/src/inkling2/ink_main.cpp:409-410,488-497`
- 既定値: `engine/src/inkling2/ink_backend.h:17-19`
- CUDA の context 下限、KV 見積り、runner 初期化: `engine/src/inkling2/cuda/ink_cuda_backend.cu:170-191,240-245`
- HIP の context 下限: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:700-702`
- bench の自動拡張・clamp: `engine/src/inkling2/ink_main.cpp:130-165`
- 通常生成の slot 割り当て・エラー: `engine/src/inkling2/ink_main.cpp:556-578`
- serve の slot 割り当て・実効上限応答: `engine/src/inkling2/ink_serve.h:441-485`
