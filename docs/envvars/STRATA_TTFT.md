# `STRATA_TTFT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

この名前は Strata の実行本体の設定ではなく、保存済みの community benchmark runner がストリーミング TTFT 測定を実行するかを選ぶために使っています。`STRATA_TTFT` を読むコードは、HEAD 内では `bench/results/2026-10-04-community-2x-rtx3060/bench.py` と同じ場所の `bench-0.1.39.py` の2ファイルだけです。これらは特定の測定結果に付属するスクリプトであり、現在の Strata サーバーやエンジンがこの環境変数を読む根拠にはなりません。

## 値と判定

両スクリプトとも `os.environ.get("STRATA_TTFT", "1") == "1"` で判定します。環境変数の値を文字列として完全一致比較し、数値変換や前後空白の除去はしません。

| 値 | 判定 | 結果 |
|---|---|---|
| 未設定 | `"1"` が既定値 | 有効 |
| `1` | 文字列が `"1"` と一致 | 有効 |
| 空文字 | `""` は一致しない | 無効 |
| その他（例: `0`, `true`, `01`, ` 1`） | `"1"` と一致しない | 無効 |

## 有効になる条件

この判定が使われるのは上記の2つの保存済みベンチマークスクリプトを実行した場合だけです。Strata 本体のソースを HEAD 全体で完全一致検索した結果、この名前を読む実装はありません。

## 実行時の詳細

スクリプトの import 時に `DO_TTFT` へ一度読み込みます。そのため、同じプロセスの実行中に環境を変更しても再判定されません。真の場合、通常の非ストリーミング測定後に `TARGETS` の各値につき1回ずつストリーミング要求を送り、TTFT を測ります。偽の場合、そのストリーミング要求群を省略します。非ストリーミング測定はどちらの場合も実行されます。

TTFT はスクリプト側で計測します。`run_stream()` は要求送信直前の `time.perf_counter()` を起点とし、最初に `content` または `reasoning_content` が空でない delta を受け取った時点との差を記録します。そのような delta がなければ `ttft_seconds` は `None` です。結果は `results.json` の run 記録に入り、各 streaming run の TTFT と wall time が標準出力にも表示されます。これはベンチマーククライアントの観測値であり、Strata エンジン内部の時間値ではありません。

## 根拠

- `bench/results/2026-10-04-community-2x-rtx3060/bench.py:16-23,40-48` — 説明、既定値、環境変数の判定。
- `bench/results/2026-10-04-community-2x-rtx3060/bench.py:149-180,221-249` — TTFT の計測、対象ごとの streaming run、実行・表示。
- `bench/results/2026-10-04-community-2x-rtx3060/bench-0.1.39.py:16-23,40-48,149-180,221-249` — 旧版 runner にも同じ判定と処理がある。
- Strata HEAD に対する `git grep -n STRATA_TTFT` — 上記2ファイル以外の完全一致参照はない。
