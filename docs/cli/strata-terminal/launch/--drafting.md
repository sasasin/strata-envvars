# `strata launch --drafting`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--drafting` |
| 別名 | なし |
| 値 | `auto`、`mtp`、`dflash2`、`off` |

## 役割

推論時に先読み候補を作る drafter を選びます。`auto` はモデルと実行環境に応じて DFlash2 または MTP を選択し、`mtp` と `dflash2` はそれぞれを指定、`off` は drafter を使いません。これは `strata launch` の設定であり、ネイティブ engine の `--drafting` 引数ではありません。Terminal は選択を run config に保存し、server 側が起動時に engine 引数へ反映します（`strata_cli/launch/cmd.py:104-107`、`strata_cli/launch/runner.py:552-569`、`serve/server.py:3781`）。

## 使い方

```sh
strata launch --model iq3_xxs --drafting auto --no-tui
strata launch --preset "Office" --drafting mtp
strata launch --model iq3_xxs --drafting off --plan
```

`--preset` と組み合わせた場合は、その起動では指定値が preset の値に重なります。`--plan` は選択結果の計画表示に使えます（`strata_cli/launch/cmd.py:83-90,104-107,142-152`、`:212-218,249-250,930-960`）。

## 値と既定値

- 値は必須です。parser は `auto|mtp|dflash2|off` のみを受け付け、前後空白を除去して小文字化してから照合します。大文字小文字は区別されず、空値やその他の値は `argparse` の引数エラーになります（`strata_cli/launch/cmd.py:37-45,104-107`、`strata_cli/launch/settings.py:31-32`）。
- オプション省略時、parser 自体は値を設定しません。新規設定では `LaunchSettings.drafting` が `None`（Auto 相当）で、preset 起動なら既存値が維持されます。明示した `auto` は preset 値を上書きします（`strata_cli/launch/settings.py:110-128`、`strata_cli/launch/cmd.py:212-218,249-250`）。
- 同じオプションを複数回指定した場合は `argparse` の通常の単一値 action で最後の値が使われます。空値を指定して解除する動作はありません（`strata_cli/launch/cmd.py:104-107`）。

## 実行時の動作

- Auto は、DFlash2 対応モデルかつ DFlash2 を含む engine/backend の組み合わせなら DFlash2、それ以外は MTP に解決されます。明示的な `dflash2` も実行できないモデルやカードでは MTP に切り替わります（`strata_control/drafting.py:34-41,657-670`）。
- 起動前の判定では、選択された DFlash2 が必要なのに未取得なら drafter pack をデータフォルダーへ取得します。計画表示では必要な取得内容を示しますが、`--plan` では変更・ダウンロードしません（`strata_cli/launch/runner.py:1606-1623,2334-2341,2530-2546`）。
- 起動時 server は config の選択に応じて engine 引数を構成します。DFlash2 の場合は DFlash2 用の引数を追加し、MTP 用の引数を除きます。MTP の場合は DFlash2 用引数を除き、`off` は両方を外して `mtp=false` にします（`strata_control/drafting.py:793-843`）。
- `--drafting off` は MTP の draft layer も無効にします。`--mtp off` と組み合わせた場合も layer は無効です。一方、明示的な `--drafting mtp` または `dflash2` は、保存済み config の `mtp=false` を上書きして drafter を有効にする処理があります（`strata_cli/launch/runner.py:564-570`、`strata_control/drafting.py:820-831`）。
- `--parallel N` が複数リクエストの処理を指定すると、Auto は MTP を使います。明示的な DFlash2 は、対応 engine では指定 parallel 数のまま動かし、リクエストごとに drafter を使います。Metal では複数リクエスト時に MTP へ fallback します（`strata_cli/launch/cmd.py:100-107`、`strata_control/drafting.py:535-550,673-700`）。
- all-cards split engine がこの launch に適用される Auto は MTP に解決されます。split engine はモデルの draft layer を必要とし、明示的な `--drafting dflash2` と split engine の組み合わせには別処理があります。必要な MTP ファイルがなければ split engine を使わず通常の layer split に戻る場合があります（`strata_cli/launch/runner.py:1522-1529,1581-1590,1696-1715`）。

## 適用条件と副作用

- DFlash2 は Qwen3.8-Flash-Next 向けで、backend は CUDA、HIP、Metal、SYCL が対象です。カードやモデルが非対応の場合、値自体は受理されますが実行時に MTP（MTP がなければ off）へ解決され、理由が表示されます（`strata_control/drafting.py:39-41,657-670,673-700`）。
- DFlash2 pack が未取得なら約 1.2 GB を一度ダウンロードします。取得失敗時は通常、MTP があれば MTP、なければ drafter なしで続行し、警告を出します。キャンセルは続行扱いにせず伝播します（`strata_cli/launch/runner.py:1606-1631`）。
- DFlash2 が選ばれていて利用可能な pack が取得済みの場合、`--parallel` を省略すると一度に処理する request 数を 1 にする旨を通知します。取得できなかった場合はこの調整を行いません（`strata_cli/launch/runner.py:1592-1604`）。
- run config には明示した選択が保存され、次回起動にも影響します。`--drafting` を省略したときは preset / 既存 config の選択が残り得ます（`strata_cli/launch/runner.py:552-554`、`strata_cli/launch/settings.py:127`）。

## 出力とエラー

- 不正値は parser の usage/error 出力となり、選択肢を示します（`strata_cli/launch/cmd.py:37-45,104-107`）。
- DFlash2 の pack 取得に失敗した場合、警告に続けて MTP または drafter なしで起動を試みます（`strata_cli/launch/runner.py:1624-1631`）。
- Auto が選んだ DFlash2 が起動準備前に失敗すると、server は MTP で再起動を試みます。VRAM 不足による失敗では drafter なしで再起動する経路があります（`serve/server.py:1281-1301`）。起動自体が失敗した場合は launch がエラーを報告し、非ゼロ終了します（`strata_cli/launch/runner.py:2172-2179`）。
- 実際に起動後の fallback が起きたとき、launch は server の `/metrics` を best-effort で読み、理由があれば通知します。取得に失敗してもこの補助通知だけが省略されます（`strata_cli/launch/runner.py:2243-2256`）。

## 根拠

- `strata_cli/launch/cmd.py:37-45,83-107` — 値検証、parser 定義、parallel との説明。
- `strata_cli/launch/cmd.py:212-218,239-250` — preset 読込と CLI 値の上書き。
- `strata_cli/launch/settings.py:31-32,110-128` — 値集合と設定の既定値。
- `strata_cli/launch/runner.py:552-570,1522-1529,1577-1631,1696-1715,2172-2181,2243-2256` — run config への保存、Auto の調整、取得、split engine、失敗・通知経路。
- `strata_control/drafting.py:34-41,657-700,793-843` — 対応範囲、選択決定、engine 引数への反映。
- `serve/server.py:1281-1301,3781` — 起動時の engine 設定と DFlash2 起動失敗後の再試行。

調査は上記 commit のソースに限定しました。同 revision の CLI `--help` と Release 配布バイナリは実行・照合していません。旧文書は陳腐化判定により削除済みとの依頼情報があるため、その説明は引き継がず現行 parser と使用箇所から作成しました。
