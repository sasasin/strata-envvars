# `STRATA_PF_ALLOC_TRACE`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

プロンプト処理の `Prefill::init` 中に、GPU の空きメモリ量とコードが要求した割当量を stderr に記録する診断スイッチです。プロンプト処理や割当方法を変更する分岐ではなく、計測とログ出力だけを有効にします。候補一覧には載っていますが、今回確認した実装は `src/prefill/prefill.cpp` の直接読み取り 1 か所です。

## 値と判定

`std::getenv()` の結果が null でないことに加え、先頭文字が `'1'` かを比較します。文字列全体の parse や数値変換はしません。

| 環境変数の値 | 診断 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定値の先頭文字が `\0`） |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | 有効 |
| その他（例: `0`, `true`, ` 1`） | 無効 |

有効・無効の判定は `pf_alloc_trace()` の初回呼び出し時に `static const bool` へ保存されます。そのプロセスで後から環境値を変えても再評価されません。既定値は無効です。CLI 引数や別の環境変数による上書きは、この判定にはありません。根拠: `src/prefill/prefill.cpp:641-644`。

## 有効になる条件

プロンプト経路が `Prefill::init` に到達すると、冒頭で判定され、開始時の計測点が出力されます。通常の CUDA/HIP 互換 GPU 経路では、その後のステージング領域、routing table、host buffer、GEMM scratch、chunk buffer の各計測点と、`Alloc` による割当集計が実行されます。単一 GPU 経路と layer split の各 GPU stage のどちらも `Prefill::init` を呼びます（`src/program/generate.cpp:11127-11145,11157-11159,20026-20032`）。

`STRATA_GPU_METAL` の場合は `Prefill::init` が冒頭の開始計測後に Metal window へ委譲して戻るため（`src/prefill/prefill.cpp:1797-1808`）、CUDA 経路の後続計測点や `Alloc` 集計は通りません。ビルド macro によるこの早期 return 以外に、CLI・モデル状態・backend 固有の値判定や追加条件はありません。

## 実行時の詳細

`pf_mark()` は各時点で `cudaMemGetInfo` から得た空き MiB、その直前の計測点からの差（`last - now`）、その区間でコードが要求した MiB を stderr に出します。ログの形式は次のとおりです。

```text
prefill alloc trace: <mark> free <MiB> MiB, dropped <MiB> MiB, asked <MiB> MiB
```

`dropped` は空き量の差分で、負値にもなり得ます。`cudaMemGetInfo` の戻り値はこの計測 helper では検査されず、失敗時は初期化された `f = 0` に基づく値が使われます（`src/prefill/prefill.cpp:645-656`）。

`Alloc::take()` が通常の割当経路で成功した `cudaMalloc` については、割当の前後に空き量を測り、要求 byte 数・割当回数・空き量の差を集計します。`Prefill::init` の carve が成功すると、回数、要求 MiB、計測した空き量の差に加えて、`bytes_needed()` の見積りと `o.used` を出力します（`src/prefill/prefill.cpp:659-692,2014-2031`）。

この集計は全メモリ使用量の記録ではありません。`count_only` の見積り専用経路、借用領域内の sub-allocation、base の容量不足で失敗した take、失敗した `cudaMalloc` は成功割当カウンタに入りません。また、`cudaHostAlloc` など `Alloc::take()` の外の処理もこの集計値ではありません。したがって `asked` は `Alloc` 経由で成功した `cudaMalloc` の要求量であり、`dropped` はその前後で観測した空き量の差です（`src/prefill/prefill.cpp:671-691`）。

変数を無効にしたり有効にしたりしても `Alloc` の成功・失敗処理は変わりません。carve が失敗すると成功時の集計行には到達せず、`Prefill::init` は必要量と失敗 buffer のサイズを含むエラー文字列を返します。通常 generate 経路では stderr に `strata generate: ...` と出して終了コード 1、layer split の stage 初期化では `layer split, CUDA<device> prompt path: ...` に包み、サイズ不適合なら 2、それ以外は 1 を返します（`src/prefill/prefill.cpp:2015-2023`; `src/program/generate.cpp:11143-11147,20027-20032`）。

## 根拠

- 候補名の全参照を Strata ソースで検索し、実際の `getenv("STRATA_PF_ALLOC_TRACE")` は `src/prefill/prefill.cpp:642` のみと確認。ほかの一致はコメント内の説明・集計フィールド（`src/prefill/prefill.cpp:639-640,662`）。helper は `pf_mark` と `Alloc::take` から呼ばれます（同 `:651-656,685-687`）。
- prompt 初期化と先頭の計測点: `src/prefill/prefill.cpp:1797-1808`。
- 各計測点および集計行: `src/prefill/prefill.cpp:1911,1949,1987,2014-2031`。
- generate 側の単一 GPU / stage 初期化とエラー処理: `src/program/generate.cpp:11127-11147,11157-11159,20024-20032`。
- `docs/DETAILS.md` にはこの診断変数に関する追加説明や測定値を確認できませんでした。
