# `strata components add-build --wait`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components add-build` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数（`float`） |

## 役割

エンジンが稼働中のとき、停止するまで最大何秒待ってから、この PC でビルドしたエンジンへの切り替えを行うかを指定します。対象コマンドはビルドをローカルのコンポーネント領域へ追加した後、選択中のエンジンをそのビルドへ切り替えます。`--wait` はこの切り替え処理の稼働中チェックに待ち時間を渡します（`terminal/strata_cli/update_cmd.py:425-442`、`terminal/strata_control/engine_library.py:211-228`）。

## 使い方

```sh
# エンジンが止まるまで最大 120 秒待ってからローカル build を選択する
strata components add-build ./build --wait 120
```

## 値と既定値

`--wait SECONDS` は `argparse` の `type=float` で解釈され、既定値は `None` です。コマンド実行時には `None` を `0.0` に置き換えて待機時間として使います（`terminal/strata_cli/update_cmd.py:47-56,303-321`）。通常の数値範囲や正値を確認する追加 validation はありません。秒数として解釈できない値や値の省略は parser の引数エラーになります。オプションを複数回指定した場合は通常の値格納 action により最後の指定値が残ります（`terminal/strata_cli/update_cmd.py:51-52`）。

`engine_library.use_engine` に渡った待機時間が `0` 以下の場合、稼働中のエンジンがあれば待たずに busy 扱いになります。正の値の場合は稼働状態を最大その時間まで確認し、3 秒間隔で再確認します（`terminal/strata_control/updater.py:381-392`、同 `:415-423`）。

## 実行時の動作

parser は `--wait` を `strata components` の複数サブコマンドに共通登録していますが、この文書の対象は `add-build` スコープです（`terminal/strata_cli/update_cmd.py:47-56,95-99`）。`add-build` はまず `_maybe_wait` を呼びます。明示した値が truthy（ゼロ以外）ならここでは稼働確認や対話質問をせず、後段へ進みます。未指定または `0` なら、対話端末では通常の稼働中エンジンについて待つか質問し、肯定すると内部値を 6 時間にします。機械出力または非対話実行では質問せずに後段へ進みます。Strata 自身の `launch-*` が稼働しているときも質問を省略します（`terminal/strata_cli/update_cmd.py:500-515`）。

その後 `local_engine.add_build` が build をコンポーネント領域へコピーし、最後に `engine_library.use_engine` が `--wait` の時間で稼働終了を待ってから選択状態を切り替えます（`terminal/strata_cli/update_cmd.py:425-442`、`terminal/strata_control/local_engine.py:127-177`、`terminal/strata_control/engine_library.py:211-228`）。待機確認は初回から始まり、稼働中なら待機イベントを出して 3 秒休止し、再確認します（`terminal/strata_control/updater.py:381-392`）。

## 適用条件と副作用

- エンジンが稼働していなければ待機しません。
- 待機はエンジンの切り替え前に行います。ローカル build の追加・コピーは待機の前に行われるため、待機時間切れや `--wait 0` で切り替えに失敗しても、追加済みのローカル build はコンポーネント領域に残ります（`terminal/strata_cli/update_cmd.py:429-434`、`terminal/strata_control/local_engine.py:153-177`）。
- 明示した `--wait 0` は `_maybe_wait` では未指定と同じ扱いです。対話端末では質問が表示され、肯定すると内部値が 6 時間に設定されます。質問に否定するか、機械出力・非対話実行の場合は `0` のまま後続の切り替えに進み、稼働中なら待たずに失敗します（`terminal/strata_cli/update_cmd.py:320,500-515`、`terminal/strata_control/updater.py:381-388`）。
- `--output json` / `jsonl` では対話質問を行いません。JSONL は待機イベントを出力し、通常の JSON 出力では進捗イベントを抑制します（`terminal/strata_cli/update_cmd.py:117-139`、同 `:400-417`）。
- このオプションによるダウンロードはありません。ローカル build は署名なしで追加され、コマンドの選択操作によって使用対象になります。ただし `STRATA_REQUIRE_SIGNED_COMPONENTS` が有効なら署名なし package の選択時に拒否されます（`terminal/strata_control/local_engine.py:127-130,166-177`、`terminal/strata_cli/update_cmd.py:434-441`、`terminal/strata_control/engine_component.py:386-394`）。

## 出力とエラー

待機中は人向け出力で「停止を待っている」旨が表示されます。指定時間までに停止しなければ `Busy` となり、`add-build` の切り替えでは終了コード `7` で失敗します（`terminal/strata_control/updater.py:381-392`、`terminal/strata_control/engine_library.py:202-208,221-225`）。`update_cmd.run` は人向けエラーを標準エラーへ、JSON 系のエラーを JSON として出力します（`terminal/strata_cli/update_cmd.py:303-312,374-378`）。ただし前述の順序により、この失敗より前にローカル build の追加が完了している場合があります。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56,95-99` — 共通 parser の定義と `add-build` への登録。
- `terminal/strata_cli/update_cmd.py:303-321,425-442,500-515` — 値の Context への格納、add-build の処理順、対話・非対話時の事前分岐。
- `terminal/strata_control/local_engine.py:127-177` — 入力 build の検査、コンポーネント領域へのコピー、manifest 作成。
- `terminal/strata_control/updater.py:352-392,415-423` — 稼働状態の確認、待機期限と再確認間隔。
- `terminal/strata_control/engine_library.py:202-228` — 切り替え時の待機と busy エラー。
