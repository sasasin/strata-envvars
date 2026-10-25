# `--think`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh` / `BENCH.bat`（委譲先: `python tools/strata_bench.py`） |
| オプション | `--think` |
| 別名 | なし |
| 値 | 値なしのフラグ。指定すると有効 |

## 役割

Quick benchmark が送る Chat Completions 要求で thinking を無効にする指定を省き、サーバー側の既定の thinking 動作に委ねます。既定 suite は thinking を無効にする指定を付けます（`tools/strata_bench.py:19-21,130-141`）。

`--think` は要求に `enable_thinking: true` や `reasoning_effort` の値を明示的に設定しません。したがって、フラグ名や help の説明だけから、すべてのサーバー・モデルで thinking が必ず有効になるとは言えません。実際の状態は接続先の API とモデル側の既定動作に依存します（`tools/strata_bench.py:130-141`）。

## 使い方

Strata リポジトリのルートで実行します。

```sh
./bench.sh --think
```

Windows では `BENCH.bat --think`、または `python tools/strata_bench.py --think` として実行できます。両 wrapper は受け取った引数を Python スクリプトへ渡します（`bench.sh:6-10`、`BENCH.bat:8-18`）。

## 値と既定値

`argparse` の `action="store_true"` で定義されています。値は取らず、既定値は `False` です。省略時は thinking を無効にする要求パラメーターが付加されます。`--think` を指定すると真になり、同じフラグを複数回指定しても動作は変わりません。値を付ける形式ではなく、他の引数と同様に不正な余分の値は `argparse` に拒否されます（`tools/strata_bench.py:932-948`）。

## 実行時の動作

メイン処理はフラグを `Suite` に渡し（`tools/strata_bench.py:1000-1007`）、suite はウォームアップ、較正、短いチャット、4K/16K prompt、agent session、および `--clients` の同時要求へ同じ値を伝えます。`--long` を併用した32K promptも同じです（`tools/strata_bench.py:225-229,242-262,264-270,283-292,322-340,372-412`）。

通常の `chat()` 要求では、`--think` を省略したとき `reasoning_effort: "none"` と `chat_template_kwargs: {"enable_thinking": false}` の両方を送ります。`--think` を指定したときはこの2項目をどちらも要求 body に含めません。プロンプト、温度 (`0`)、streaming、生成上限など他の要求設定はこの分岐で変わりません（`tools/strata_bench.py:130-141`）。同時要求も `serve_load.one()` が同じ条件分岐で2項目を省略します（`tools/serve_load.py:34-40`）。

レポートには `params.think` として真偽値が保存され、README の設定欄に thinking の on/off が記録されます。再現用の記録コマンドにも、指定時だけ `--think` が含まれます（`tools/strata_bench.py:829-830,1011-1016`）。この記録は CLI の指定状態を示すもので、サーバーが実際に thinking を行ったことを独立に検証するものではありません。

## 適用条件と副作用

オプションは quick benchmark が送る要求のみに作用します。benchmark が設定ファイルからサーバーを起動する場合も設定を変更する処理はなく、既に動いているサーバーへ `--url` で接続する場合も、そのサーバー設定を変更しません（`tools/strata_bench.py:957-1007`）。

既定 suite では thinking 無効化を指定するため、フラグを付けると要求内容が変わり、応答や計測値も変わる可能性があります。ただし、このソースだけではモデルごとの thinking の有効状態、性能への方向・大きさは確定できません。実測や推奨値も本調査では確認していません。

## 出力とエラー

HTTP 要求の失敗は `chat()` がエラー情報として返し、suite の `failures` に記録して処理を続けます。報告には失敗件数が表示され、最終終了コードは要求失敗があり、かつ `chat`・`prompts`・`agent` の主要結果が一つもない場合に `1` となります。したがって、thinking 指定に関連する要求が失敗しても、他の主要結果があれば必ずしも非ゼロ終了にはなりません（`tools/strata_bench.py:142-177,238-240,1019-1022,1034`）。

## 根拠

- parser、既定値、help 文: `tools/strata_bench.py:932-948`
- request body の条件分岐: `tools/strata_bench.py:130-141`
- warm-up・calibration と各 suite の伝播: `tools/strata_bench.py:225-229,242-262,264-270,283-292,322-340,372-412`
- 同時要求側の request body: `tools/serve_load.py:34-40`
- CLI parser から suite への値の受け渡し、記録: `tools/strata_bench.py:1000-1016`
- README の thinking 記録: `tools/strata_bench.py:829-830`
- wrapper の引数委譲: `bench.sh:6-10`、`BENCH.bat:8-18`
- request error と終了コード: `tools/strata_bench.py:142-177,238-240,1019-1022,1034`

同一 revision の CLI `--help` は実行していません。parser 定義と要求の組み立てをソースで照合しました。server/backend ごとの thinking の既定値や実際の有効状態は調査範囲から確認できません。ソース変更、build、GPU 実行、性能測定、テストは行っていません。
