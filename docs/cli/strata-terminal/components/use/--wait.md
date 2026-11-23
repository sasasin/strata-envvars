# `strata components use --wait`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数を表す浮動小数点数。省略時は `None`（実行時に `0.0` として扱う）。 |

## 役割

エンジンを切り替える前に、実行中モデルが停止するまで待つ時間を指定する。実行中モデルを停止させるオプションではなく、指定時間を過ぎても稼働中なら切り替えを拒否する。選択したエンジンは、その後に起動するモデルで使われる。

## 使い方

```sh
# 15秒まで、稼働中モデルが停止するのを待ってから切り替える
strata components use 0.1.54 --wait 15
```

引数 `0.1.54` にはインストール済みエンジンのバージョン、フォルダー名、または `newest` を指定できる。`--wait` は `strata components use` の共通オプションで、`--family` などと併用できる。

## 値と既定値

parser は `type=float`、`default=None` で値を読み取る。数値形式以外は argparse の引数エラーになる。正の値はその秒数を待つ。コードに値の範囲・上限を検証する処理はなく、0 または負数は待機せず、稼働中なら即座に busy として失敗する。`None` は実行時に `0.0` に置き換えられる（`terminal/strata_cli/update_cmd.py:51-52, 319-321`、`terminal/strata_control/updater.py:381-388`）。

浮動小数点値の有限性も検証されない。したがって `inf` は実質的な上限なしの待機になり、`nan` は期限比較が成立しないため、モデルが稼働し続ける間待機が終わらない可能性がある（`terminal/strata_control/updater.py:384-392`）。

## 実行時の動作

`use` parser はこのオプションを含む共通引数を登録する。実行時に `a.wait or 0.0` が updater の context に渡され、`use` 処理はエンジン一覧から対象を解決した後、`use_engine` の更新ロック内で待機を行う。3秒間隔で稼働状態を再確認し、アイドルになったら切り替え処理へ進む（`terminal/strata_cli/update_cmd.py:84-87, 319-321, 445-471`、`terminal/strata_control/engine_library.py:211-228`、`terminal/strata_control/updater.py:381-392`）。

オプションを省略するか `--wait 0` を指定した場合、対話端末で外部のエンジンが稼働中なら、先に「停止まで待つか」を尋ねる。`y` / `yes` の回答は `ctx.wait` を6時間に設定する。それ以外の回答では追加待機せず、稼働状態なら失敗する。JSON系出力または非対話入力では質問せず、待機時間0のまま処理する。Strata 自身の `launch-` プロファイルで起動したエンジンの場合もこの質問を省略する（`terminal/strata_cli/update_cmd.py:445-449, 466-471, 500-515`）。

待機中は人向け出力では標準出力に待機メッセージを表示し、`--output jsonl` では待機イベントを出力する。`--output json` はイベント出力を抑止する。アイドルになった後、選択先が現在のエンジンと異なる場合には、対象パッケージの署名とファイルを検証して選択状態を保存する。選択が最新エンジンなら更新追従状態となり、古いエンジン等を選ぶ場合は pin が保存される。稼働中モデルの engine は変わらず、ダウンロードや削除も行わない（`terminal/strata_cli/update_cmd.py:121-139, 471-490`、`terminal/strata_control/engine_library.py:211-228, 231-274, 296-312`）。

## 適用条件と副作用

- 待機の対象は `updater.serving_now` が検出する稼働中エンジン。待機中にモデルを停止させたり、エンジンの切り替えを先行させたりはしない（`terminal/strata_cli/update_cmd.py:445-449`、`terminal/strata_control/engine_library.py:211-228`）。
- タイムアウトまたは待機なしで稼働中モデルが残ると切り替えは行われず、busy エラーになる。切り替えが実行される場合は、選択したエンジンに応じて updater の状態ファイル・履歴・backend 選択が更新される（`terminal/strata_control/engine_library.py:202-208, 255-274, 280-312`）。
- 待機処理には OS/backend 別の時間補正は確認できない。実際の稼働状態の検出条件は `serving_now` の実装とプロセス状態に依存する。

## 出力とエラー

待機時間内に稼働状態が解消しない場合、`wait_until_idle` は `Busy` を送出し、`use_engine` は exit code `7` の `SwitchBusy` に変換する。人向け出力では `strata: ...` を標準エラーに出し、JSON/JSONL モードでは `ok: false` とエラー情報を標準出力に出す（`terminal/strata_control/updater.py:381-392`、`terminal/strata_control/engine_library.py:202-208, 221-225`、`terminal/strata_cli/update_cmd.py:303-312, 374-380`）。

数値として解釈できない値は parser のエラーとなり、コマンド本体には進まない。未インストールまたは曖昧なエンジン名、当該 PC に適合しないエンジン、検証に失敗したエンジンも別の失敗経路となる（`terminal/strata_cli/update_cmd.py:84-87, 466-471`、`terminal/strata_control/engine_library.py:184-197, 249-254, 296-310`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-57, 84-87` — 共通オプションの parser 定義と `use` への登録。
- `terminal/strata_cli/update_cmd.py:303-321, 445-471, 500-515` — context への値の受け渡し、use の実行経路、対話時の既定待機。
- `terminal/strata_control/updater.py:381-392` — 待機期限、稼働状態の再確認間隔、Busy への移行。
- `terminal/strata_control/engine_library.py:202-228, 231-274, 277-312` — 忙しい場合の失敗と、待機後のエンジン選択・状態保存。
- `terminal/strata_cli/update_cmd.py:117-139, 374-380` — 待機イベントおよびエラー出力。
