# `--draft-plain`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（サブコマンドなし） |
| オプション | `--draft-plain` |
| 別名 | なし |
| 値 | 数値。`std::atof` で `double` に変換され、backend 内で `float` として扱われる。正の値が fallback 候補の評価に使われる。 |

## 役割

CUDA backend の speculative decoding で、DSpark drafter が作る tree のサイズ選択に plain decoding の候補を加える値です。正の値を指定すると、候補 tree が1または2ノードのケースも評価対象になります。Strata の `BackendOpts` コメントでは `1.0` を損益分岐値として説明しています。これは性能保証値ではありません。 (`engine/src/inkling2/ink_backend.h:39`, `engine/src/inkling2/cuda/ink_dspark.cuh:1754-1774`)

## 使い方

```sh
strata-inkling --native model.gguf --draft-plain 1.0
```

モデル読み込み後の通常生成に値を渡す例です。モデルパスは手元の Inkling 対応モデルに置き換えてください。 (`engine/src/inkling2/ink_main.cpp:870-871`, `engine/src/inkling2/ink_main.cpp:904-905`, `engine/src/inkling2/ink_main.cpp:1073-1087`)

## 値と既定値

- parser は次の引数を `std::atof` で変換し、`BackendOpts::spec_plain` に格納します。CLI 側の明示的な範囲検証や拒否処理はありません。 (`engine/src/inkling2/ink_main.cpp:904-905`)
- 引数省略時の `spec_plain` は `-1.0` です。これは CUDA backend が CLI 値で環境変数設定を上書きしないことを示す sentinel です。CUDA backend の初期値は `0.0` です。 (`engine/src/inkling2/ink_backend.h:39`, `engine/src/inkling2/cuda/ink_cuda_backend.cu:120-123,1205-1206`)
- CUDA backend では `STRATA_INK_SPEC_PLAIN` を読み込んだ後、CLI 値が `0.0` 以上なら CLI 値で上書きします。したがって `--draft-plain 0` は環境変数を無効化する値として働き、負数は環境変数の値を上書きしません。 (`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125`)
- `atof` が数値として解釈できない文字列を受け取ると変換値は `0` になります。オプションの後に引数がなければ `missing value after --draft-plain` を stderr に出し、終了コード `2` で終了します。複数回指定した場合は引数走査で後の値が設定を上書きします。 (`engine/src/inkling2/ink_main.cpp:846-849,904-905`)

## 実行時の動作

CUDA backend は、`spec_plain` を初期化時に `STRATA_INK_SPEC_PLAIN` から読み、CLI で `0` 以上が渡されていればそれを優先します。通常の DSpark speculative step では値が `draft_beam_tree` の `plain_margin` 引数に渡されます。 (`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,1057-1076`)

この選択処理は `adaptive_moe_ratio > 0` の場合に行われます。候補数・上限内の tree サイズを比較し、`plain_margin <= 0` なら1・2ノード候補を飛ばします。正の値なら1・2ノード候補の評価率にその値を乗じます。候補から選ばれたノード数に応じて生成する speculative tree を組み立てます。 (`engine/src/inkling2/cuda/ink_dspark.cuh:1696-1699,1754-1778,1781-1790`; 呼び出し元は `engine/src/inkling2/cuda/ink_cuda_backend.cu:1073-1079`)

このオプションと同等の環境変数は `STRATA_INK_SPEC_PLAIN` です。環境変数一覧には掲載されていますが、対応する個別文書は確認できなかったため、ここではソースで確認できた優先順位だけを記載します。 (`engine/src/inkling2/cuda/ink_cuda_backend.cu:120-123`; `docs/envvars/000_envvers.md:1277-1280`)

## 適用条件と副作用

- parser はオプションを受理しますが、実際に値を読み、DSpark tree に渡す処理は CUDA backend に確認できました。CPU および HIP backend でこの値が参照される実装は確認できず、そこでは指定値の効果を確認できませんでした。 (`engine/src/inkling2/ink_main.cpp:904-905`; CUDA の読み取り・使用は `engine/src/inkling2/cuda/ink_cuda_backend.cu:120-123,1073-1079`)
- CUDA backend が DSpark を初期化する条件は、DSpark が有効で、モデル manifest に DSpark があり、`model_.ls_active` ではないことです。DSpark 初期化が GPU メモリ不足で失敗すると drafter が停止され、このオプションも効果を持ちません。 (`engine/src/inkling2/cuda/ink_cuda_backend.cu:343-352`)
- `--draft off` は DSpark を無効にするため、併用時はこの値を使う draft 処理に到達しません。 (`engine/src/inkling2/ink_main.cpp:895-897`, `engine/src/inkling2/cuda/ink_cuda_backend.cu:343-344`)
- CLI 値自体について、負値や非有限値を含む明示的 validation、警告、clamp は確認できませんでした。負値は前述の環境変数上書き条件により無視されます。NaN/Infinity の下流での扱いはソースから確定できないため、使用可能な値として推奨しません。 (`engine/src/inkling2/ink_main.cpp:904-905`, `engine/src/inkling2/cuda/ink_cuda_backend.cu:120-123`)

## 出力とエラー

このオプション固有の成功時出力や validation error はありません。引数が欠けた場合は parser が stderr にエラーを出して終了コード `2`、不明なオプションも stderr に `unknown option` を出して終了コード `2` になります。 (`engine/src/inkling2/ink_main.cpp:846-849,985-988`)

## 根拠

- parser と値変換: `engine/src/inkling2/ink_main.cpp:846-849,904-905`
- 設定値の sentinel と説明: `engine/src/inkling2/ink_backend.h:36-40`
- CUDA backend の既定値、環境変数・CLI 優先順位: `engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,1205-1206`
- DSpark の適用条件と draft tree 呼び出し: `engine/src/inkling2/cuda/ink_cuda_backend.cu:343-352,1057-1079`
- plain 値による候補サイズ評価: `engine/src/inkling2/cuda/ink_dspark.cuh:1696-1699,1754-1778,1781-1790`
