# `HY4_ALLOC_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`strata-hy4` の `Runner::dalloc` が行う大きな GPU デバイスメモリ割り当てについて、成功時にサイズ情報を `stderr` へ出す診断スイッチです。割り当て方法やサイズを変える分岐ではなく、ログ出力だけを制御します。判定箇所は `engine/src/hy4flash/run/hy4_graph.hip.h:1282-1289` です。

この関数は Runner の作業用バッファなどで使われます（例: `engine/src/hy4flash/run/hy4_graph.hip.h:1450-1495`）。`strata-hy4` は `STRATA_BUILD_HY4=ON` でビルドし、CUDA または HIP を有効にする構成です。CUDA と HIP の双方が `hy4_main.hip.cpp` を同じ GPU ソースとして使い、CUDA 構成では `hipMalloc` を `cudaMalloc` に対応付けます（`engine/CMakeLists.txt:929-935,967-974`、`engine/src/hy4flash/run/hy4_gpu.h:1-9,17-55`）。通常の CLI 経路と `--serve` 経路のどちらも `Runner` を初期化します（`engine/src/hy4flash/run/hy4_main.hip.cpp:725-736`、`engine/src/hy4flash/run/hy4_serve.hip.h:307-315`）。

## 値と判定

コードは `getenv("HY4_ALLOC_TRACE")` の戻り値が null でないかだけを確認します。値の文字列を解析・比較しません。したがって、環境変数が未設定なら無効、設定されていれば空文字を含むどの値でも有効です。数値変換、大文字小文字、空白、`0` / `1` / `true` / `false` の解釈はありません（`engine/src/hy4flash/run/hy4_graph.hip.h:1286`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `strata-hy4` の CUDA/HIP `Runner::dalloc` | ログを出さない | 空文字、`0`、`1`、`true`、`false`、その他任意の文字列。ただし割り当て成功かつサイズが 300 MiB 以上の場合に限り出力 | 設定値の内容による無効値はない。割り当て失敗、または 300 MiB 未満は設定済みでも出力しない |

境界は `n * sizeof(T) >= (300ull << 20)`、すなわち 314,572,800 bytes（300 MiB）です。ログの GB 値はこのバイト数を 1,000,000,000 で割った十進 GB 表記です（同上）。

## 有効になる条件

- 実行ファイルに `Runner::dalloc` を含む `strata-hy4` の CUDA または HIP ビルドが使われること。Metal / SYCL の別実装にはこの名前の参照がありません（`engine/CMakeLists.txt:929-974` とソース全体の `HY4_ALLOC_TRACE` 検索結果）。
- `Runner::dalloc` 経由の割り当てであること。直接 `hipMalloc` を呼ぶ箇所すべてを対象にするスイッチではありません（判定は `dalloc` 内の `engine/src/hy4flash/run/hy4_graph.hip.h:1282-1289` にあります）。
- その `hipMalloc` が成功し、要求サイズが 300 MiB 以上であること。失敗時はサイズ条件のログを出さず、既存の割り当て失敗ログの後に `HCK` がエラーを報告して終了コード 3 で終了します（`engine/src/hy4flash/run/hy4_graph.hip.h:1272-1287`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:29-36`）。
- CLI 引数や別の環境変数による優先順位・上書き条件は、この判定箇所にはありません。条件を満たす割り当てで環境変数が設定されているかだけで決まります。

## 実行時の詳細

各 `Runner::dalloc` 呼び出しで `hipMalloc` を実行し、失敗時の注記を処理した後に、成功とサイズの境界を確認してから環境変数を読みます。関数内 `static` などへの保存はなく、起動時の一括読み込みやキャッシュもありません。ログ判定の `getenv` は割り当てごとに行われます。環境変数が unset の状態では `stderr` の割り当てサイズ行だけが抑止され、割り当て自体は同じ `hipMalloc` で行われます（`engine/src/hy4flash/run/hy4_graph.hip.h:1282-1289`）。

## ログと測定値

対象の条件を満たす割り当てごとに、次の行を `stderr` に出します。`n` は要素数、`sizeof(T)` は要素あたりのバイト数です（`engine/src/hy4flash/run/hy4_graph.hip.h:1286`）。

```text
[alloc] %.3f GB (%zu x %zu B)
```

割り当て失敗時のサイズ行は出ません。失敗注記は `stderr` に `[runner] device allocation of ... failed: ...` の形式で出し、その後 `HCK` が `HIP error ... at ...` を出して終了コード 3 で終了します（`engine/src/hy4flash/run/hy4_graph.hip.h:1272-1287`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:29-36`）。この変数について記載された測定値はありません。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:1282-1289` — `Runner::dalloc` の割り当て、成功・サイズ判定、環境変数参照、ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1272-1280`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:29-36` — 失敗ログと `HCK` の終了処理。
- `engine/CMakeLists.txt:929-974`、`engine/src/hy4flash/run/hy4_gpu.h:1-9,17-55` — `strata-hy4` の CUDA/HIP ビルド経路。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:725-736`、`engine/src/hy4flash/run/hy4_serve.hip.h:307-315` — CLI / serve の Runner 初期化。
