# `--drafting`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--drafting` |
| 別名 | なし |
| 値 | `auto`、`mtp`、`dflash2`、`off` のいずれか |

## 役割

推測トークンを使う drafter を選びます。`auto` はモデル、engine backend、GPU、要求数などから DFlash2 または MTP を選び、`mtp` と `dflash2` はそれぞれを明示し、`off` は drafter を使わない指定です。DFlash2 は Qwen3.8-Flash-Next 向けで、対応しないモデルや実行条件では MTP などへフォールバックします。設定はこの起動の run config に記録され、保存プリセットを使う場合はプリセットの設定をコマンドライン指定で上書きできます。根拠: `strata_cli/launch/cmd.py:101-104`、`strata_cli/launch/cmd.py:206-210,247-248`、`strata_cli/launch/runner.py:483-485`、`strata_control/drafting.py:1364-1387`。

## 使い方

```sh
# 自動選択（未指定時と同じ選択規則）
strata launch --model iq3_xxs --drafting auto --no-tui

# DFlash2を指定。未取得なら通常起動では取得処理が行われる
strata launch --model iq3_xxs --drafting dflash2 --no-tui

# MTPを選択
strata launch --preset Office --drafting mtp --no-tui

# drafterなしで起動
strata launch --model iq3_xxs --drafting off --no-tui

# 起動せず、予定を表示する
strata launch --model iq3_xxs --drafting dflash2 --plan
```

## 値と既定値

- 値は必須です。parser は前後空白を取り除いて小文字化した後、`auto`、`mtp`、`dflash2`、`off` のみを受理します。したがって大文字や前後空白を含む値も正規化後に判定されます。未指定時は `LaunchSettings.drafting` が `None` で、選択処理では `auto` として扱われます。根拠: `strata_cli/launch/cmd.py:35-43,101`、`strata_cli/launch/settings.py:31-32,96`、`strata_control/drafting.py:818-820`。
- `--preset NAME` と併用すると、読み込んだプリセットに対して指定値が優先します。明示的な `--drafting` を付けなければ、プリセット側の選択を使います。parser の同じオプションを複数回指定した場合は argparse の通常の格納動作で後の値が残ります。根拠: `strata_cli/launch/cmd.py:206-212,247-248`。
- 未知の値は選択肢を示す parser の引数エラーとなり、起動処理には進みません。根拠: `strata_cli/launch/cmd.py:35-43,101`。

## 実行時の動作

- `auto` は、モデルが DFlash2 対応で engine に実装があり、backend と GPU が対応する場合に DFlash2 を選びます。それ以外では MTP を選びます。モデルセットやカードクラス別の既定値、および一部 GPU の Auto 抑制規則も選択に反映されます。根拠: `strata_control/drafting.py:1364-1387`、`strata_control/drafting.py:333-361`。
- `dflash2` を選んでも、そのモデル・engine・GPU で実行できない、複数要求などの実行モードと両立しない、または必要ファイルが揃わない場合があります。そのとき `decide()` は理由を添えて MTP に切り替え、MTP も利用できなければ `off` にします。DFlash2 は Qwen3.8-Flash-Next 専用です。根拠: `strata_control/drafting.py:463-467,1390-1425`。
- `--parallel` などで複数要求を処理する場合、`auto` は通常 MTP に切り替わります。DFlash2 を明示した場合は対応する engine で要求スロットごとに DFlash2 を使えますが、Metal では複数要求時に MTP へ戻り、`--pipeline-windows` は DFlash2 の実行を妨げます。起動処理は DFlash2 が選ばれ、要求数を明示していない場合に一要求設定を適用します。根拠: `strata_control/drafting.py:1045-1062,1434-1439`、`strata_cli/launch/runner.py:1614-1626`。
- DFlash2 が選ばれ、必要な drafter ファイルがデータフォルダーにない場合、通常起動では一度ダウンロードを試みます。取得失敗は起動自体を止めず、MTPがあればMTP、なければdrafterなしで続行し、警告を出します。`--plan` は予定表示で終了し、変更やダウンロードは行いません。根拠: `strata_cli/launch/runner.py:1629-1658,2524-2539`。
- `--drafting off` はこの起動の run config で MTP draft layer も無効にします。`--mtp off` も独立して draft layer を無効にする指定です。MTP layer の導入を必要とする起動では、setup が実行される条件に応じて取得されます。根拠: `strata_cli/launch/runner.py:483-500,944-952`、`strata_cli/launch/modelstate.py:121-126,143-150`。

## 適用条件と副作用

- `dflash2` の対応可否はモデルファミリーまたはモデル名、engine が提供する DFlash2 実装、検出された backend・GPU に依存します。対象外のモデルなどは値の validation エラーにはならず、実行時にフォールバックして理由を通知します。根拠: `strata_control/drafting.py:174-195,463-467,1364-1387,1416-1425`。
- `auto` / `dflash2` でファイルが不足している場合、ネットワーク経由で DFlash2 drafter を取得し、モデルデータ領域に保存します。既存ファイルを変換して必要な selector を作る経路もあります。取得・変換は必要時のみで、`--plan` では実行されません。根拠: `strata_cli/launch/runner.py:1638-1650,1629-1631`。
- `--drafting off` は MTP layer を使わずに起動するため、メモリ要件と推測処理が変わります。既存サーバーが要求した条件で停止・再起動されるかは `strata launch` の他の起動条件に従い、このオプション単独がサーバーを停止する処理は確認していません。根拠: `strata_cli/launch/runner.py:495-500`。

## 出力とエラー

- 不正な値は parser が選択可能な値を含むエラーにします。対象モデル・GPU・モードで DFlash2 が使えない場合は通常の入力エラーではなく、決定結果に理由が付き、MTP または `off` へフォールバックします。根拠: `strata_cli/launch/cmd.py:35-43`、`strata_control/drafting.py:1409-1425`。
- DFlash2 のダウンロードに失敗した場合は警告を出し、MTP があれば MTP で、MTP がなければ drafter なしで続行します。根拠: `strata_cli/launch/runner.py:1651-1658`。
- 起動後、server は実際に適用した drafter とフォールバック理由を起動ログ・状態情報に反映します。DFlash2 が起動後に準備完了せず終了した場合は server が MTP で再起動を試みる経路があります。根拠: `serve/server.py:1248-1255,1276,3893-3917`。

## 根拠

- `strata_cli/launch/cmd.py:35-43,73-80,101-104` — 値の正規化、parser 登録、コマンドの通常起動と計画表示の説明。
- `strata_cli/launch/cmd.py:206-212,238-250` — プリセット読み込み後に明示値で設定を上書き。
- `strata_cli/launch/settings.py:31-32,81-100` — 選択肢と未指定時の設定値。
- `strata_cli/launch/runner.py:483-500,928-952` — run config への保存、MTP layer と setup 引数への反映。
- `strata_cli/launch/runner.py:1524-1533,1599-1626,1629-1658` — 起動条件での解決、一要求設定、drafter 取得と失敗時の継続。
- `strata_control/drafting.py:174-195,463-467,818-826,1364-1425` — backend 対応、モデル範囲、正規化、Auto・フォールバック判定。
- `strata_control/drafting.py:1045-1062,1434-1439` — 要求数・実行モードとの相互作用。
- `serve/server.py:1235-1255,1276,3893-3917` — 起動失敗後の再試行と server 起動時の drafter 適用・表示。

調査範囲はこの checkout の Strata 所有ソースです。実機 GPU ごとの性能や、ここに挙げたコード以外の外部 engine の内部動作は実行・検証していません。
