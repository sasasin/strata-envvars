# `--throttle`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--throttle` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると有効（既定値は無効） |

## 役割

tuned DFlash2 drafter を使う構成で、feed に該当 drafter がなかった、または feed に到達できなかった直後の再問い合わせを抑えます。直近12時間以内にその状態を記録した印があれば、feed を再確認せず tuned drafter を見送ります。主な用途はアプリの通常ロードや再起動など、利用者が drafter の取得を直接依頼していない経路です。このフラグはダウンロード速度を制限するものではありません。

## 使い方

```sh
# run config が選ぶ drafter を取得する。直近の feed miss があれば tuned drafter の再照会を抑える
strata drafting fetch --config /path/to/run.json --throttle
```

`--config` を省略した場合は、単一の対象モデルがインストール済みならその設定を使い、該当モデルが特定できなければ通常の fetch 対象を決めます。複数モデルが該当するときはモデルまたは config の指定を求めて終了します（`strata_cli/drafting_cmd.py:83-99,153-158`）。

## 値と既定値

- `argparse` の `store_true` フラグで、値は不要です。省略時は `False`、指定時は `True` です。別名は登録されていません（`strata_cli/drafting_cmd.py:34-38`）。
- `fetch` サブコマンドだけに登録されています。`strata drafting plan --throttle` では受理されません（`strata_cli/drafting_cmd.py:19-38`）。
- 入力値の追加検証はありません。時間窓は `strata_control/drafting.py` の `RETRY_AFTER_S = 12 * 3600` で定まり、`.tuned-feed-miss` の更新時刻が直近12時間以内かを判定します（`strata_control/drafting.py:1635-1645`）。

## 実行時の動作

CLI は `--throttle` の真偽値を `drafting_fetch.ensure_for()` に渡します（`strata_cli/drafting_cmd.py:199-202`）。その後の適用範囲と結果は次のとおりです。

- tuned drafter の適用条件を満たし、tuned ファイルが未取得の場合に限り、通常の署名付き feed 経路で miss 印を確認します。直近の印があれば feed を読み直さず `None` を返します（`strata_control/drafting_fetch.py:250-275`）。適用条件は backend・モデルの tuned entry と、カード／アーキテクチャ等の条件で決まります（`strata_control/drafting.py:375-384,421-444`）。
- feed を読んで tuned drafter が見つからない場合は miss 印を作成し、見つかった場合は既存の印を削除します。印はデータディレクトリ内の `dflash2/.tuned-feed-miss` に書かれ、ファイル更新に失敗しても fetch は止まりません（`strata_control/drafting_fetch.py:159-175,272-277`）。
- tuned drafter を見送った後は stock drafter が利用可能ならそれを返します。tuned entry のない構成では `ensure()` にそのまま進むため、`--throttle` による feed miss 抑制はありません（`strata_control/drafting_fetch.py:305-329`）。
- `STRATA_DFLASH2_TUNED_URL` 等で tuned ファイルの直接 URL が指定される経路は、feed と miss 印の判定を通らず到達確認を行います（`strata_control/drafting_fetch.py:250-274`、`strata_control/drafting.py:249-250`）。
- `--if-needed` は別の条件です。drafter が不要なら取得処理全体を省き、`--throttle` を指定していても通常の「Nothing to download.」結果になります（`strata_cli/drafting_cmd.py:162-165,186-191`）。

## 適用条件と副作用

このオプションが抑制するのは tuned drafter 用 feed の再照会だけです。stock drafter の取得、実際に開始された tuned／stock ダウンロードの転送速度、署名検証・サイズや SHA-256 の確認には影響しません。miss 印は feed lookup 結果に応じて作成・削除されます。通常の tuned feed は signed update feed を使い、既に受理済みの feed sequence より古い feed は拒否されます（`strata_control/drafting_fetch.py:185-227,272-300,332-385`）。

## 出力とエラー

- throttle 経路の結果が `None` なら、CLI は成功扱いで終了コード `0` を返します。人間向け出力は `Nothing to download.`、JSON／JSONL は `ok: true` と `skipped: true` を含む結果です（`strata_cli/drafting_cmd.py:199-207`）。
- 署名・feed trust の問題、転送中断、安全検査失敗など `DraftingError` または `AcquisitionRefused` になる場合は通常の失敗経路で、終了コード `5` です。人間向けメッセージは stderr、機械向けはエラー JSON に出ます（`strata_control/drafting_fetch.py:199-227,282-298,359-385`、`strata_cli/drafting_cmd.py:208-215`）。したがって `--throttle` はすべての feed エラーを無条件に隠すものではありません。
- `--output jsonl` の進捗は stdout に JSON 行で出ます。`ensure_for()` が `None` を返し、throttle によって成功扱いになる経路では、結果イベントが出ます（`strata_cli/drafting_cmd.py:193-197,202-207`）。

## 根拠

- `strata_cli/drafting_cmd.py:19-38` — `drafting fetch` parser と `--throttle` の型・既定動作・help 説明。
- `strata_cli/drafting_cmd.py:150-162,186-220` — fetch の実行、`ensure_for()` への引き渡し、出力・終了コード。
- `strata_control/drafting_fetch.py:159-175,250-302` — miss 印、直近 miss の抑制、feed lookup と tuned ファイル取得。
- `strata_control/drafting_fetch.py:305-329` — tuned drafter から stock drafter への fallback と offline 時の戻り値。
- `strata_control/drafting_fetch.py:185-227,332-385` — feed の信頼性確認、stock drafter のネットワーク・検証・失敗経路。
- `strata_control/drafting.py:333-344,375-444,1635-1645` — tuned entry、適用条件、12時間の miss 判定。
