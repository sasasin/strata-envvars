# `STRATA_COLD_TRACE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

prefill の `native_proj` が実行する GPU native projection のうち、プロセス内で最初の最大80回について処理時間を stderr に出す診断用フックです。初回呼び出しで発生するライブラリ／code object のロード時間などを調べる目的がソースコメントに記されています。これは測定のため同期を追加するため、通常実行のタイミングを観測するものではありません。

## 値と判定

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定はあるが `e[0]` は `\0`） |
| 先頭文字が `1` | 有効 |
| その他 | 無効 |

文字列全体の比較や数値変換はせず、先頭1文字だけを `1` と比較します。したがって `1`, `10`, `1abc` は有効で、`true`, `01`, ` 1` は無効です。大文字小文字の変換や値の範囲検査もありません。値はグローバル `ColdTrace` オブジェクトのコンストラクターで読み取られます。起動後に環境を変更しても `on` は更新されません。

## 有効になる条件

- `src/prefill/prefill.cpp` の prefill 実装がビルドに含まれ、`native_proj` を通る投影が実行される必要があります。
- `native_proj` は native GGUF block がない場合、エラーを設定して計測前に戻ります。ソースのエラー文は `has no native GGUF blocks (run with --native)` です。したがって native block を使わない投影は計測されません。
- 計測フックは `native_proj` にのみ接続されています。同じファイルの `bf16_proj` 呼び出しはこのカウンターに含まれません。
- 呼び出し回数の上限はプロセス全体で80回です。対象となる `native_proj` が80回未満なら実際の出力もその回数までです。

## 実行時の詳細

`ColdTrace::begin()` は有効かつ出力回数が80未満の場合、投影前に `cudaDeviceSynchronize()` を行い、その後から `steady_clock` の計測を始めます。`native_proj` が GEMM を呼んだ後、`end()` は再び `cudaDeviceSynchronize()` して完了を待ち、経過時間をミリ秒で出力してカウンターを1増やします。同期失敗の戻り値はこのコードでは確認しません。無効時または80件出力後は `begin()` が false を返すため、これらの同期・時間計測・ログ出力は行いません。

有効時の出力形式は次のとおりです（`what` は現在 `native`）。

```text
strata cold-trace: #<番号> native <weight名> T=<T> N=<N> K=<K> <ミリ秒> ms
```

投影自体の戻り値や出力データを書き換える分岐はありませんが、同期によって処理の重なり方や実行時間には影響し得ます。この変数を使った性能値は診断出力であり、通常実行のレイテンシとして扱えません。

## 根拠

- `src/prefill/prefill.cpp:2428-2447` — 設定値の読み取り、先頭文字判定、80回上限、同期、時間計測、stderr 出力、およびプロセス全体の `g_cold`。
- `src/prefill/prefill.cpp:2448-2454` — native block の検査後に `begin`、GEMM、`end` を呼ぶ順序。
- `src/prefill/prefill.cpp:2456-2460` および `3177-3261,3481-3493` — `bf16_proj` は別 helper であり、native と BF16 の projection 呼び出しが区別されていること。
- `docs/AMD_HIP.md:527-533` — R9700 / gfx120X wheel の hipBLASLt 1.2.0 における初回 BF16/FP16 product の測定と、この変数を使った first 80 dense projections の診断への言及。記載値はその資料にある測定条件での値であり、本調査で再測定したものではありません。
