# `--max-new`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--max-new` |
| 別名 | なし |
| 値 | 整数 `N`。parser は `type=int` で変換し、既定値は `128`。CLI parser には範囲検査がない。 |

## 役割

チューニング sweep で測る要求ごとの最大生成トークン数を指定する。値は候補ごとに変えず、baseline、各候補、最後の baseline 再測定で同じ workload として使われる。例:

```sh
strata tune run --engine ./strata --backend cuda --model example \
  --max-new 256
```

`--engine`、`--backend`、`--model` はこのコマンドで必須。オプションの宣言と既定値は `strata_cli/cli.py:414-430`、受け取った値を workload に含める箇所は `strata_cli/cli.py:1763-1770` にある。

## 値と既定値

省略すると `128`。`argparse` の整数変換以外に、このオプション固有の正数・上限検査は CLI parser にはない（`strata_cli/cli.py:429-430`）。したがって非整数は argparse の引数エラーになるが、0 や負数が parser 段階で拒否されるとは限らない。

## 実行時の動作

- `--mode protocol`（既定）では、`--max-new` を `GEN <N> ...` 要求の生成上限として engine harness に渡す。prompt token 数は `--prompt-tokens` で別に指定し、この harness は workload の同じ token ID 列を各測定に使う（`strata_cli/cli.py:1770-1786`、`strata_control/tune_engine.py:501-510,560-568`）。engine は要求の `max_new` が 1 未満なら `ERR bad request: max_new` を返す（`sycl/src/program/generate.cpp:9650-9656,9728-9732`）。
- `--mode api` では、API harness の chat completion 要求に `max_tokens: N` として渡す（`strata_cli/cli.py:1771-1784`、`strata_control/tune_api.py:146-163`）。実際の prompt は `--api-prompt` であり、`--prompt-tokens` が API の prompt 長を決めるわけではない。API mode は `--config` と `--api-expect` も必須で、欠けると `_error` を返して終了コード `2` になる（`strata_cli/cli.py:1771-1784`、`strata_cli/cli.py:527-532`）。
- workload は plan の比較 identity にも含まれるため、異なる生成上限で取った測定値は同一 workload として扱われない（`strata_cli/cli.py:1763-1768`、`strata_control/tuning.py:753-768`）。

生成上限であり、常にちょうど `N` token が出る指定ではない。モデルが先に終了する場合や、engine/API が要求を拒否する場合の実生成数は別になる。`--max-new` は候補設定の探索軸ではなく測定 workload の条件である。

## 適用条件と副作用

各測定は候補設定で engine を起動して workload を実行するため、この値は sweep 中の各測定の仕事量に影響する。`Tuner` は測定結果を job ディレクトリに保存し、baseline と候補の結果、report を記録する（`strata_control/tuning.py:317-362,423-475`）。保存先は `--state-dir`、環境変数 `STRATA_TUNE_DIR`、既定のユーザー状態領域 `tuning/` の順で決まる（`strata_cli/cli.py:458,1643-1650`、`strata_control/paths.py:13-20`）。

API mode は設定ファイル本体を書き換えず、候補ごとの一時 JSON を作り worker を起動し、終了時に一時ファイルを削除する（`strata_control/tune_api.py:259-292`）。protocol mode は engine subprocess を起動して測定し、終了時に `QUIT` を送り、終了しなければ kill する（`strata_control/tune_engine.py:389-427,570-585`）。どちらも実際の engine/API 実行を伴うため、GPU や計算資源を使用し得る。

## 出力とエラー

protocol mode で `N < 1` などの要求エラーが測定で発生すると、その測定は候補の失敗理由として記録される。baseline が失敗した場合も job は `baseline_failed` を記録して完了し、コマンド側は通常の report 出力後に `0` を返す経路がある（`strata_control/tuning.py:423-482,486-500`、`strata_cli/cli.py:1802-1847`）。エンジンが起動・要求処理に失敗した場合は、harness が理由を `MeasurementError` にし、候補状態・report に反映する（`strata_control/tune_engine.py:429-471,501-550`）。

## 根拠

- parser、既定値、コマンド scope: `strata_cli/cli.py:414-430`
- workload 構築、protocol/API mode への分岐: `strata_cli/cli.py:1759-1786`
- protocol 要求の組み立て、prompt token の生成: `strata_control/tune_engine.py:501-510,560-568`
- protocol の正数チェック: `sycl/src/program/generate.cpp:9650-9656,9728-9732`
- API request の `max_tokens`: `strata_control/tune_api.py:146-163`
- job の永続化・測定失敗処理: `strata_control/tuning.py:317-362,423-500`
- 索引上の位置: `docs/cli/README.md:741-767`

調査範囲は上記 checkout のソースと索引・調査規約。CLI の実行、engine build、GPU 実行、性能測定、テスト、および Release artifact の照合は行っていない。protocol の正数チェック例は SYCL engine の実装箇所であり、他 backend の engine 固有エラー文言までは確認していない。
