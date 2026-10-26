# `--wait`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。調査対象 checkout は `## main...origin/main` で、`git status --short --branch` に未コミット変更の表示はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数。`float` として解析される。 |

## 役割

engine が稼働中の場合に、停止するまで指定秒数の範囲で待つようにします。時間内に停止しなければ、engine の切り替えは行わず失敗します。このオプションは engine を停止させるものではありません。

## 使い方

```sh
strata components install-file ./strata-engine-package.tar.gz --wait 300
```

`file` はローカルの engine package（`.tar.gz` または `.zip`）を指定します。`--wait` は `_common()` で追加されるため、同じ parser の `--feed`、`--components-dir`、`--backend` などとともに受理されます。

## 値と既定値

- `argparse` の `type=float`、`default=None` で定義されています。指定を省略すると実行コンテキスト上の待ち時間は `0.0` 秒です。
- 明示値に最小値・最大値や有限値の検証はありません。数値に変換できない文字列は `argparse` が拒否し、通常の usage エラー（終了コード 2）になります。
- 待機処理では `wait <= 0` の場合、稼働中 engine があれば即座に `Busy` になります（ただし端末での対話確認で待機を選ぶと、コンテキスト値は6時間に変更されます）。正の値では、その秒数を期限として最大約3秒間隔で稼働状態を再確認します。

## 実行時の動作

1. `install-file` は共通 parser option を受け取り、`run()` が `--wait` の値を `Context.wait` に渡します。`None` や `0` は `0.0` として扱われます。
2. `run()` は install-file 経路で、まず `_maybe_wait()` を呼びます。正の `--wait` が指定されている場合、対話確認を省いて後続処理へ進みます。値を省略するか `0` を指定した場合、engine が稼働中かつ端末入力が対話可能なら「待つか」を尋ねます。`y` / `yes` の場合は6時間を上限として待ちます。非対話実行では確認せず、稼働中なら待機判定で失敗します。負数は truthy として対話確認を省きますが、待機判定では即時失敗になります。
3. 実際の `wait_until_idle()` は、一時 engine の test-start が成功した後、engine の保存先を切り替える直前に呼ばれます。したがって、`--wait` はファイルの展開・署名と内容の検証や test-start 自体を待機後まで遅らせる指定ではありません。
4. 待機中は3秒ごとに稼働状態を確認します。engine が停止すれば切り替えへ進みます。待機は `strata_control` の管理対象インスタンスまたは共有 activity lease による稼働検知を使います。

## 適用条件と副作用

- 待機チェックは「稼働中 engine がある場合」に限って時間を消費します。稼働していなければ直ちに通過します。
- 待機対象の停止操作は行いません。engine が指定時間内に停止しない場合、`Busy` で切り替えを拒否します。
- package の展開・検証は components 配下の一時 staging 領域を使い、署名と各ファイルを検査します。test-start は別の一時 runtime/profile を使い、保存済みモデルがあれば起動・1トークン確認後に停止します。選択した package ファイルは残されます。
- 実装上、待機判定は test-start 後です。稼働中 engine がある状況での test-start が成功しない場合は、その失敗経路が先に返るため、`--wait` を指定していても待機処理まで到達しないことがあります。

## 出力とエラー

- 人間向け出力では待機中に `An engine is serving; waiting for it to stop before updating.` を表示します。
- `--output jsonl` では待機イベントを JSON Lines で出力します。`--output json` ではイベント出力を抑制します。
- 時間切れ時は失敗メッセージを出し、終了コード 7 を返します。JSON / JSONL の機械向けモードではエラーオブジェクトを出力し、人間向けでは `strata: ...` を標準エラーへ出します。
- file 不在、archive 形式・署名・内容の不正などは別の検証エラー経路です。待機時間切れと混同しないでください。

## 根拠

- parser と install-file のスコープ: `strata_cli/update_cmd.py:30-39, 57-62`。索引も `install-file` に `--wait` を掲載しています: `docs/cli/README.md:229-244`。
- CLI から Context への値の受け渡しと install-file 経路: `strata_cli/update_cmd.py:174-195, 208-217`。
- 対話確認、非対話時の扱い、待機時の6時間上限: `strata_cli/update_cmd.py:258-273`。
- 稼働 engine の検知と待機間隔・期限判定: `strata_control/updater.py:281-317, 322-340`。
- install-file の一時展開、署名・全ファイル検証、対象 engine 判定、test-start 呼び出し: `strata_control/updater.py:1088-1145`。
- test-start 後、保存先の切り替え前の待機判定: `strata_control/updater.py:994-1025`。
- `Busy` の終了コードとメッセージ: `strata_control/updater.py:71-82`。失敗の JSON / 標準エラー出力: `strata_cli/update_cmd.py:174-183, 246-255`。
- 待機イベントの human / JSONL / JSON 出力: `strata_cli/update_cmd.py:65-87`。
