# `--build-options`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--build-options` |
| 別名 | なし |
| 値 | `LIST`。カンマ区切りの文字列 |

## 役割

ソースからビルドした Strata の build option を、標準ベンチマークの結果 JSON に記録するための申告値です。実行中のサーバーから build option を取得する機能ではなく、エンジンのビルド設定を変更する引数でもありません。標準ベンチマークではサーバーから build option を読めないため、必要に応じて実行者が指定します（`docs/BENCHMARK_PROTOCOL.md:49-51,326-332`）。

## 使い方

```sh
strata bench run --url http://127.0.0.1:8000 --build-options cuda,sm86
```

`strata bench run` は `--profile` または `--url` のどちらか一方を必要とします。上の例はローカルの既存サーバーに接続する形です（`strata_cli/cli.py:293-300`）。

## 値と既定値

- `LIST` は必須の文字列引数です。省略時の値は `None` です。短縮 alias はありません（`strata_cli/cli.py:315-333`）。
- 値はカンマで分割され、各要素の前後空白を除去した後、空要素を捨ててリストにします。例: `cuda, sm86,,` は `cuda` と `sm86` の2要素になります（`strata_cli/cli.py:1274-1278`）。
- 値の内容、要素名、重複についての追加 validation はありません。分割後の重複要素はそのまま残ります。空文字列は偽値として扱われ `None` になります。一方、空白やカンマだけの非空文字列は空リスト `[]` になります（`strata_cli/cli.py:1278`）。

## 実行時の動作

`standard-v1` では、CLI が分割したリストを `declared["build_options"]` に入れて `bench_standard.run()` に渡します（`strata_cli/cli.py:1273-1278,1302-1305`）。レポート生成側はこれを `software()` に渡し、`software.build_options` として結果 JSON に格納します（`strata_cli/bench_standard.py:813-817`、`strata_cli/bench_facts.py:356-373`）。値は実行者の申告であり、サーバーやビルド成果物との一致確認はこの処理では行いません。

未指定の場合、`software.build_options` は `null` になり、`missing` に「server does not report build options; pass --build-options for a source build」という理由が記録されます（`strata_cli/bench_facts.py:383-384`）。レポート作成処理は `missing` を null 値から生成し、全 null 値に理由があることを検証します（`strata_cli/bench_standard.py:953-957,1066-1069`）。この未指定理由自体は `run.status` を `nonconforming` にする条件には含まれず、同 status は別途集めた `reasons_nonconforming` に基づいて決まります（`strata_cli/bench_standard.py:792-794,885-896`）。

## 適用条件と副作用

この値が結果に反映されるのは `--suite standard-v1` の経路です。`standard-v1` は既定 suite で、CLI は同 suite のとき `_bench_standard()` を呼びます（`strata_cli/cli.py:297-300,1183-1188`）。その他の serving suite は別経路で実行され、`build_options` を参照しません（`strata_cli/cli.py:1186-1198`）。parser 上は `bench run` 共通の引数として受理されるため、非標準 suite に指定しても拒否されず、ベンチマーク結果にも反映されません。

この引数によってビルド、ネットワーク接続先、サーバー設定は変わりません。影響は標準ベンチマークの結果に記録する metadata に限られます。ベンチマーク自体の出力先などは [`--out`](--out.md) および [`--suite`](--suite.md) を参照してください。

## 出力とエラー

値を省略した場合は argparse が引数不足として usage/error を出し、終了コード `2` で終了します。認識されない引数も `parse_known_args()` 後に argparse のエラー経路へ渡されます（`strata_cli/cli.py:2223-2231`）。`--build-options` の値そのものについて独自の拒否エラーはありません。

標準 suite の結果では指定値は `results.json` の `software.build_options` に記録されます。非空値にカンマだけを含めた場合など分割後が空でも `[]` として記録され、値未指定時の `null` / `missing` とは異なります（`strata_cli/cli.py:1278`、`strata_cli/bench_facts.py:370-384`）。

## 根拠

- `strata_cli/cli.py:315-333` — 標準 suite 用 option group と `--build-options LIST` の parser 定義。
- `strata_cli/cli.py:1183-1198,1237-1278,1302-1305` — suite 分岐、値の正規化、標準 benchmark runner への受け渡し。
- `strata_cli/bench_standard.py:813-817,953-957,885-896` — report の software block 生成と status 判定。
- `strata_cli/bench_facts.py:356-384` — `software.build_options`、未指定時の `missing` 理由。
- `docs/BENCHMARK_PROTOCOL.md:49-51,326-332` — 利用者向け protocol の説明。ソース実装の補足として参照。
