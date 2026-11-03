# `--stop-model`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--stop-model` |
| 別名 | なし |
| 値 | 値を取らない真偽値。指定すると `True`、省略時は `False` |

## 役割

更新対象 engine を使ってモデルが稼働中の場合に、更新処理がそのモデルを停止してよいことを明示します。特に、対話入力を受け取れないスクリプトで停止を許可するための指定です。稼働中モデルがない場合、この指定によるモデル停止はありません（`strata_cli/update_cmd.py:77-79,347-350`、`strata_control/engine_update.py:308-324`）。

## 使い方

```sh
strata components update --stop-model
```

この例は更新処理がモデル停止を許可された状態で実行します。停止したモデルを更新後も自動で起動するには `--start-again` も指定します。

## 値と既定値

- `argparse` の `store_true` option で、引数値は不要です。省略時は `False` です（`strata_cli/update_cmd.py:76-79`）。
- 値の範囲、空値、複数指定に対する独自 validation はありません。`--stop-model=true` のような値付き構文はこの parser の定義ではありません。
- `--yes` とは別の同意です。`--yes` は質問を省略しますが、モデル停止への同意を与えません。モデルが稼働中で `--stop-model` がない非対話実行は、変更前に exit code `7` で拒否されます（`strata_cli/update_cmd.py:67-69,333-350`、`strata_control/engine_update.py:317-324`）。

## 実行時の動作

1. `strata components update` parser がこの flag を受け取り、共通 dispatch から `update_cmd.run()` に渡します（`strata_cli/update_cmd.py:70-79`、`strata_cli/cli.py:139-140,512-515,2136-2138`）。
2. `run()` は `--check` の場合を除き、更新を `engine_update.update_with_models()` と `ModelGate` に委譲します。`ModelGate` の `allow_stop` にこの flag の値が渡ります（`strata_cli/update_cmd.py:290-301,347-350`）。
3. 更新予定があり稼働中モデルが見つかると、`--stop-model` がない対話端末では停止前に確認します。指定がある場合はこの停止確認を行わず、対象モデルを停止可能として同意済みに記録します。更新はモデルが稼働したままダウンロードを進め、その後停止してから staging / test start に進みます（`strata_control/engine_update.py:308-332,334-363`、`strata_control/updater.py:327-331,1703-1710`）。
4. モデル停止では `runtime.stop()` を呼び、関連 tunnel の停止も試みます。tunnel 停止で例外が起きても無視します（`strata_control/engine_update.py:217-224`）。
5. 停止後は既定で再起動しません。`--start-again` を併用すると、保存済み profile の設定でモデルを起動します。再起動指定は更新失敗時にも適用され、その場合は旧 engine のままで起動を試みます（`strata_cli/update_cmd.py:69,347-350`、`strata_control/engine_update.py:376-406,412-432`）。

## 適用条件と副作用

- モデルが稼働している場合にだけ停止許可として意味を持ちます。`--check` は `update_with_models()` に進まず feed を確認して終了するため、モデル停止 gate は通りません（`strata_cli/update_cmd.py:290-301`）。
- Strata がこのプロセスから起動していない service、`strata serve`、または別プログラムが保持する server は `can_stop` 不可と分類され、この flag を指定しても停止されません。変更前に exit code `7` で拒否されます（`strata_control/engine_update.py:189-199,308-324`）。
- 更新ダウンロード中に新たに起動した未同意モデルは停止対象に追加されず、更新を進める前に拒否されます。対話時に追加確認できるケースもありますが、`--stop-model` 指定時は `allow_stop` が有効なため追加モデルも自動停止の許可対象にはならず、エラーになります（`strata_control/engine_update.py:334-352`）。
- flag だけを指定し `--start-again` を指定しなければ、モデルは停止状態のままです。人向け出力では再開方法が表示されます（`strata_control/engine_update.py:376-405`）。
- 停止後に再起動を試みて失敗したとき、更新成功なら exit code `8` になります。更新自体の失敗は通常の更新エラーを維持します（例: 更新失敗 `6`）。停止中の更新拒否や停止失敗は `7` です（`strata_control/engine_update.py:34-35,357-363,424-432`、`strata_cli/update_cmd.py:307-319`）。
- `--output json` / `jsonl` など機械出力モードでは対話質問は行われません。`--stop-model` は停止同意として渡り、機械出力に model phase event が含まれます（`strata_cli/update_cmd.py:98-107,333-350`、`strata_control/engine_update.py:316-317,354-363`）。

## 出力とエラー

- 稼働モデルがあるのに停止同意がない非対話実行では、モデル名、変更していない旨、再実行時に `--stop-model` を付ける案内を含むエラーになり、通常 human 出力では `strata: ...` を標準エラーへ出して code `7` を返します。機械出力時は同じ失敗を JSON の `error` として標準出力に出します（`strata_control/engine_update.py:317-324`、`strata_cli/update_cmd.py:237-242,307-311`）。
- この flag 自体に成功メッセージはありません。停止・再起動の状態は human 出力または JSON/JSONL の model event と結果に反映されます（`strata_control/engine_update.py:316,354-363,397-405`、`strata_cli/update_cmd.py:98-115,302-306`）。

## 根拠

- `strata_cli/update_cmd.py:67-79` — `strata update` と `strata components update` の parser 宣言。両方の command scope で flag を定義。
- `strata_cli/cli.py:139-140,512-515,2136-2138` — parser 登録、共通 `--json` / `--quiet` 追加、実行関数への dispatch。
- `strata_cli/update_cmd.py:290-301,333-350` — `--check` 分岐、gate への値の引き渡し、対話可否と `allow_stop` の生成。
- `strata_control/engine_update.py:189-209,217-224,292-363,376-432` — 稼働モデルの分類、停止処理、同意・release・再起動と終了コード。
- `strata_control/updater.py:327-331,1703-1710` — engine 停止前の gate 呼び出し。
- `docs/INSTALL.md:122-128` — 利用者向け説明との照合。

調査範囲は上記 commit の checkout にある Terminal CLI と `strata_control` 実装です。ソースを変更せず、build、GPU 実行、性能測定、テスト、Release artifact の実行・取得は行っていません。
