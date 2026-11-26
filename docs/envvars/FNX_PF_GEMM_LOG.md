# `FNX_PF_GEMM_LOG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

split engine の prompt prefill が `pf_gemm` を呼んだとき、その GEMM の形状 `(rows, cols, C, ldo)` を stderr に出す診断用スイッチです。値で演算を選んだり、GEMM の引数・結果を変えたりはしません。`pf_gemm` はこの判定の後、従来どおり `p.f16acc` に応じた cuBLAS GEMM を実行します（`engine/src/split/src/prefill.cu:463-479`）。

このコードは CUDA/HIP の split engine ターゲットに含まれる共有 prefill 実装です（`engine/src/split/CMakeLists.txt:76-92,116-129`）。split prefill の通常経路から `pf_dense` / `pf_dense_xh` を経由して呼ばれるため、コメントにあるベンチマーク専用の読み取りではありません（`engine/src/split/src/prefill.cu:482-496,1300-1308,1651-1663,1756-1759`）。

## 値と判定

`std::getenv("FNX_PF_GEMM_LOG") != nullptr` 相当の設定有無だけを判定します。値を parse・比較しません。未設定ならログなし、設定されていれば空文字、`0`、`1`、`true`、大文字小文字、空白、数値として無効な文字列を含めてログ有効です。CLI 引数や別の環境変数による上書きはこの箇所にありません（`engine/src/split/src/prefill.cu:463-467`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| split engine の `pf_gemm` 呼び出し | ログしない | 環境変数が設定済みのすべての値（空文字、`0`、`1`、`true` など） | なし（未設定のみログしない） |

## 有効になる条件

- `strata-split-2`、`strata-split-3`、`strata-split-4` のいずれかを CUDA または HIP でビルドし、そのプロセスが `pf_gemm` を通る prefill 処理を実行する必要があります。これらのターゲットに `prefill.cu` が含まれ、HIP ビルドでは同ファイルを HIP 言語としてコンパイルします（`engine/src/split/CMakeLists.txt:76-92,116-129`）。
- 値が設定されていても、`pf_gemm` が呼ばれなければ出力はありません。これは split engine の prefill 用フックで、他の engine/backend に同名の読み取りはありません（候補名の全参照は `engine/src/split/src/prefill.cu:464` のみ）。
- モデル・chunk・layer によって呼び出し形状や回数は変わりますが、形状ログ自体に CLI やモデル状態による追加ゲートはありません。

## 実行時の詳細

環境変数は `pf_gemm` の呼び出しごとに `getenv` で確認されます。環境変数の有効／無効状態を static cache しません。一方、出力済み形状を保持する `static std::set<std::tuple<int, int, int, int>>` はプロセス内で共有され、同一の `(rows, cols, C, ldo)` は最初の 1 回だけ出力されます。したがって実行中に環境値が設定されれば、その後の呼び出しで未出力形状を記録できますが、すでに出力した形状は再出力されません（`engine/src/split/src/prefill.cu:463-467`）。

この分岐は `fprintf` のみで、GEMM の演算経路やその結果を変更しません。後続の cuBLAS 呼び出しが失敗する場合は通常の `ckb` エラー処理に進みますが、この環境変数固有の失敗・fallback 経路はありません（`engine/src/split/src/prefill.cu:468-479`）。

## ログと測定値

有効時、各形状の初回に stderr へ次の書式で出力します。`rows`、`cols`、`C`、`ldo` は `pf_gemm` に渡された整数値です。

```text
pf_gemm: rows %d cols %d C %d ldo %d
```

ログは通常の split prefill でも出ます。Strata の資料にこの診断変数に関する測定値はありません（実装: `engine/src/split/src/prefill.cu:464-467`）。

## 根拠

- `engine/src/split/src/prefill.cu:463-479` — 環境変数判定、形状ごとの重複抑制、stderr 出力、GEMM の実行。
- `engine/src/split/src/prefill.cu:482-496,1300-1308,1651-1663,1756-1759` — 通常の split prefill から `pf_gemm` へ至る呼び出し。
- `engine/src/split/CMakeLists.txt:76-92,116-129` — CUDA/HIP split engine ターゲットへの prefill 実装の組み込み。
