# `strata serve --max-queue`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--max-queue` |
| 別名 | なし |
| 値 | 0〜4096 の整数 `N` |

## 役割

HTTP 推論 API が同時に受け付けて保持する呼び出し数を制限します。エンジンの実効枠を超えて保持する呼び出し数を `N` で指定し、上限に達した後の呼び出しを拒否します。これは `strata serve` のサーバー起動時に適用される値で、エンジンの並列枠自体は変更しません。

## 使い方

```sh
# エンジン枠を超えて最大8件の推論呼び出しを保持する
strata serve --profile ./run.json --max-queue 8

# 超過分を保持せず、エンジン枠を超える呼び出しを受け付けない
strata serve --profile ./run.json --max-queue 0
```

## 値と既定値

- `N` は `int` として解析され、0〜4096 の範囲が有効です。省略した場合の CLI 既定値は `None` で、保存プロファイルまたは run config に `max_queue` があればその値を使います。どこにも設定がなければ上限は設けません（`terminal/strata_cli/cli.py:76,783-803`、`terminal/serve/server.py:9183-9184,9289-9292`）。
- CLI 値、保存プロファイルの override、run config の順に優先されます。CLI 以外の値を選んだときは、run config 由来の値は設定から直接読み、保存プロファイル由来の値は `--max-queue N` として server parser に渡します（`terminal/strata_cli/cli.py:783-807,833-840`）。
- `0` は有効です。負数、4096 より大きい数、整数として解析できない値は受理されません（`terminal/strata_cli/cli.py:76,963-964`）。

## 実行時の動作

`strata serve` は選択した設定と有効値から server 起動引数を組み立てます。値がある場合は `--max-queue N` を server に渡し、server は CLI 値を設定ファイルの `max_queue` より優先します。確定値は `Service.max_queue` に設定されます（`terminal/strata_cli/cli.py:821-840`、`terminal/serve/server.py:9289-9292,9492-9499`）。

上限は `Service.admission_limit()` が返す `max(1, engine.batch) + max_queue` です。したがって、指定数は「エンジン枠を超えて保持する件数」で、エンジン枠内の呼び出しも含めた総予約数はこの合計です。`0` の場合はエンジン枠相当まで予約でき、それを超える呼び出しを拒否します（`terminal/serve/server.py:4354-4357`）。

予約判定は `/v1/chat/completions`、`/v1/messages`、`/v1/responses` の推論要求に対して行われます。上限を満たしている場合は予約数を増やさず、満たしていなければ要求を予約します。予約状態は監視テレメトリにも `max_queue`、`admission_limit`、`admission_reserved`、`admission_rejected` として載ります（`terminal/serve/server.py:4373-4388,7775-7792,7466-7474`）。

## 適用条件と副作用

- 上限はサーバーインスタンス単位で、HTTP 推論要求の受け付けに作用します。CLI からの起動計画 `--plan` では有効値を計画に含めますが、サーバーは起動しません（`terminal/strata_cli/cli.py:979-982`）。
- 値の設定だけでは設定ファイルを書き換えません。server への引数転送と `Service` 上の値設定であり、推論枠の予約・拒否を変えます（`terminal/strata_cli/cli.py:833-840`、`terminal/serve/server.py:9492-9499`）。
- `--queue-timeout` を使う場合は `--max-queue` または設定の `max_queue` が必要です。timeout は最初のエンジンターン待ちの期限であり、エンジンが要求を受け付けた後の生成を中断する設定ではありません（`terminal/serve/server.py:9289-9298,5854-5862,5999-6001,1817-1842`）。
- `max_queue` が未設定なら `admission_limit()` は `None` を返し、この admission 上限による拒否は行いません（`terminal/serve/server.py:4354-4357`）。

## 出力とエラー

- CLI の範囲外の整数は `strata: --max-queue must be in 0..4096` を標準エラーへ出し、終了コード 2 で終了します。整数に変換できない値は argparse の型エラーになります（`terminal/strata_cli/cli.py:76,558-563,963-964`）。server parser を直接使う経路でも、設定値を含む有効値が整数でない、または範囲外なら argparse のエラーになります（`terminal/serve/server.py:9183-9184,9289-9292`）。
- admission 上限に達した推論要求には HTTP 429、エラーコード `admission_full`、`Retry-After: 1` が返ります（`terminal/serve/server.py:7775-7792`）。
- `--queue-timeout` も設定されており、待機期限を超えた非ストリーミング要求には HTTP 429 と `queue_wait_timeout` が返ります。ストリーミング中に期限切れとなった場合は、開始済みストリームへ API 形式のエラーイベントが出力されます（`terminal/serve/server.py:7883-7890,8274-8278,8572-8580`）。

## 根拠

- `terminal/strata_cli/cli.py:67-77` — `strata serve` parser の定義、値型、既定値、関連する `--queue-timeout`。
- `terminal/strata_cli/cli.py:783-840` — CLI・保存プロファイル・run config の値選択、相互条件、server 引数への転送。
- `terminal/strata_cli/cli.py:954-980` — 値域検証と `--plan` の処理。
- `terminal/serve/server.py:9183-9186,9289-9298` — server parser、設定値との優先順位、範囲検査と timeout の必須条件。
- `terminal/serve/server.py:4230-4236,4354-4388,9492-9499` — admission 状態、総予約上限、予約と値の適用。
- `terminal/serve/server.py:7775-7792,7883-7890,8274-8278,8572-8580` — HTTP 推論要求の拒否と timeout のエラー経路。

調査は指定 revision のソースに限定しました。実際のネットワーク要求や性能への影響は実行・測定していません。
