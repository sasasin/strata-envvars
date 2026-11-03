# `STRATA_DISPATCH_STATS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata の dispatch 経路を記録するホスト側カウンタを有効・無効にします。カウンタは選ばれた kernel path や graph launch などを集計する診断用のもので、この環境変数による分岐は kernel の選択・計算経路を変えません。`Stats::count()` と `Stats::note()` は無効時に直ちに戻ります。

実装は共通ヘッダー `include/strata/core/dispatch_stats.hpp` にあります。実際の呼び出しは verifier の記録処理と CUDA kernel の計測箇所にあります。ヘッダー自体は backend 型に依存しませんが、この checkout で確認した kernel-level の呼び出し箇所は CUDA ソースです。

## 値と判定

値全体の parse や数値変換は行わず、`getenv()` の結果と先頭文字だけで判定します。

| 設定 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効（設定値の先頭文字は `\0`） |
| 先頭文字が `0` | 無効。例: `0`, `00`, `0anything` |
| それ以外 | 有効。例: `1`, `true`, `false`, 空白で始まる文字列 |

したがって `false` も有効です。大文字小文字、後続文字、数値としての妥当性、範囲は検査されません。無効値の警告や fallback はなく、無効時は統計 API がカウントを省略します。

## 有効になる条件

環境変数が有効でも、計測 API が呼ばれる処理経路に限って記録されます。たとえば verifier は window に `Scope` を設定し、window 状態の note を追加し、graph launch を数えます。CUDA kernel の dense/expert/hyper-connection 計測は各 callsite で `kernel()` を呼びます。全ての dispatch 箇所を網羅する仕組みとは実装されていません。

この設定を CLI 引数や別環境変数が上書きする処理は確認できません。`--stats` は generate CLI の別の per-stage / per-token 統計表示フラグです。dispatch header のコメントには `--stats` が dispatch JSON を stdout に出すとありますが、この checkout の Strata 所有ソースには `Stats::json()` の呼び出しやその stdout 出力箇所が見つかりませんでした。したがって、現行実装で `--stats` がこの環境変数を有効化したり dispatch JSON を出したりするとは確認できません。

## 実行時の詳細

設定値は `Stats` singleton の初回生成時に一度だけ読み込まれ、`on_` に保存されます。最初の `Stats::get()` より後にプロセス環境を書き換えても反映されません。有効な場合だけ `atexit` に終了時レポート関数を登録します。カウンタ記録はホスト側の mutex / hash map、および graph launch 用 atomic counter を使います。診断記録の有効・無効だけを変え、dispatch 結果そのものを変えるコードはありません。

`STRATA_DISPATCH_REPORT` は別設定です。有効時に終了処理で読み直され、未設定または空文字ならファイルを書きません。非空なら JSON を指定パスに書こうとしますが、`fopen()` が失敗してもエラー出力や終了コード変更はありません。`STRATA_DISPATCH_STATS=0` の場合は終了処理の登録自体がなく、report path があっても出力されません。

## 根拠

- `include/strata/core/dispatch_stats.hpp:45-57,107-120` — singleton、カウンタ無効時の早期 return、report path の読み取りと終了時登録、`STRATA_DISPATCH_STATS` の値判定。
- `include/strata/core/dispatch_stats.hpp:77-105,107-112` — JSON 生成、report path の空判定、ファイル出力。`fopen()` 失敗時の診断処理はありません。
- `src/core/verify.cpp:1391-1396,3211-3214` — verifier の window scope / note と graph launch カウント。
- `src/kernels/cuda/native_mmvq.cu:3569-3574`, `src/kernels/cuda/iq_kernels.cu:6268-6275`, `src/kernels/cuda/fused_gr.cu:1623` — CUDA kernel-level の計測呼び出し例。
- `src/program/generate.cpp:781,1191,3674,20569-20583` — `--stats` の CLI 状態、help、parse と per-token 統計出力。dispatch JSON 呼び出しはこれらの処理にありません。
