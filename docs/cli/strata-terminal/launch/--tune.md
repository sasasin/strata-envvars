# `--tune`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--tune` |
| 別名 | なし |
| 値 | `quick`、`thorough`、`skip` |

## 役割

`strata launch` がモデルを準備して起動する前に、現在の PC でエンジン設定を測定して、より速い候補を探すモードを選びます。`quick` は短い探索、`thorough` は候補を広く測る探索、`skip` は測定を行いません。測定結果は Strata の tuning preset として保存され、適用可能な構成では後続の起動にも共有されます。`strata launch` 自体の通常のセットアップやサーバー起動を省略する指定ではありません。

## 使い方

```sh
# モデルを準備し、quick 測定の後にサーバーを起動して端末モニターを開く
strata launch --model iq3_xxs --tune quick

# thorough モードで測定してから起動する（時間は最大約2時間の見込み）
strata launch --model iq3_xxs --tune thorough

# 測定せずモデルを起動する（既定のモード）
strata launch --model iq3_xxs --tune skip --no-tui

# --plan と併用し、選択内容を確認する。測定も設定変更も行わない
strata launch --model iq3_xxs --tune quick --plan
```

## 値と既定値

- 値は必須で、`quick`、`thorough`、`skip` のいずれかです。parser は前後の空白を除去して小文字化してから検証するため、大文字小文字は区別されません。無効な値は argparse の引数エラーとなり、選択肢を含むメッセージを出します（`terminal/strata_cli/launch/cmd.py:35-43,121`、選択肢は `terminal/strata_cli/launch/settings.py:29`）。
- 省略時は `skip` です（`terminal/strata_cli/launch/settings.py:141`）。
- `quick` は tuner の quick モード（約20分の予算）、`thorough` は thorough モード（最大約2時間、確認測定を含む）へ渡されます。これはソース上の予算・説明であり、実行時間の保証ではありません（`terminal/strata_cli/launch/runner.py:2395-2404`、`terminal/strata_cli/tune_commands.py:21-30`）。
- `skip` は測定を行いません。`--retune` を併用して `--tune` を省略した場合だけ、launch parser 側で `quick` に切り替わります（[`--retune`](--retune.md)、`terminal/strata_cli/launch/cmd.py:874-877`）。

## 実行時の動作

指定値は `LaunchSettings.tune` に設定されます（`terminal/strata_cli/launch/cmd.py:274-275`）。`--plan` では選んだモードを計画表示に含めて終了し、測定に進みません（`terminal/strata_cli/launch/cmd.py:897-925`）。通常実行では、launch の engine・model・drafter の準備、実行設定の作成と保存を経てからチューニング段階に進みます（`terminal/strata_cli/launch/runner.py:3296-3338`）。

`quick` と `thorough` は `strata tune auto <launch-profile> --mode ... --output json` の子プロセスを起動します。`--tune-allow-small` が指定されているときは、さらに tuner の `--allow-small-differences` として渡されます。候補の探索・測定は tuner が担当し、成功した改善または既定設定が最速と確認された場合は結果を preset として保存します（`terminal/strata_cli/launch/runner.py:2395-2407`、`terminal/strata_cli/tune_commands.py:37-39,383-410`）。

再測定を明示しない場合、同じ launch preset に有効な tuning 結果があると測定を省略します。preset の tuning ID が見つかる場合、または標準設定が最速と記録済みの場合はその旨を表示します。preset を使わず同じモデルと選択で測った結果も再利用対象です。`--retune` はこれらの再利用判定を越えて測定します（`terminal/strata_cli/launch/runner.py:2378-2394,2466-2479`）。チューニング preset は起動設定に対する共有ストアで管理され、preset 側では機器・モデルの識別が変わった場合の非適用も扱います（`terminal/strata_control/presets.py:488-506`）。

## 適用条件と副作用

- `skip` または Hy4-Flash / Inkling-2-Mini の launch では、この段階の tuner を呼びません。これら2系統は launch runner がチューニング対象外として処理します（`terminal/strata_cli/launch/runner.py:2373-2377`）。
- tuner の計測にはエンジン実行と PC の計算資源を使います。測定前に同じ launch profile の既存サーバーが動作中なら停止し、測定後は launch がサーバーを起動します。他の profile のサーバーを止める必要が生じる場合もあります。停止できない場合は launch error（終了コード 6）となり、停止を促す案内を出します（`terminal/strata_cli/launch/runner.py:2443-2464`）。
- launch 用の tuning 進捗 JSON は launch ディレクトリに作成・更新されます。開始前に同名ファイルの削除を試み、tuner 子プロセスの終了後に読み取ります（`terminal/strata_cli/launch/runner.py:2396-2401,2415-2421`）。tuner は実行記録・レポートを保存し、改善または標準設定の確認時には preset も保存します（`terminal/strata_cli/tune_commands.py:371-374,402-424`）。
- `--tune-allow-small` は測定候補に答えがわずかに変わる可能性のある設定を加える別オプションです。併用しない場合は tuner の該当フラグを渡しません（[`--tune-allow-small`](--tune-allow-small.md)、`terminal/strata_cli/launch/runner.py:2401-2404`）。
- `--tune` 単独ではモデル・構成を選ばないため、例のように `--model`、`--model-path`、`--preset` など起動対象を指定してください。コマンド例と「選択があるか」の判定は `terminal/strata_cli/launch/cmd.py:14-25,849-862` にあります。

## 出力とエラー

launch はチューニングの進捗と結果をモニターまたは通常出力へ渡します。tuner が改善を検出したとき、標準設定がすでに最速のとき、測定が混雑のため不確定なとき、失敗・中止したときで結果文言を分けます。tuner が結果を返さない、または測定に失敗した場合、標準設定で launch を続行する旨を表示します。測定結果がないこと自体は launch の即時エラーにはせず、その後のモデル起動で問題があれば別途起動エラーになります（`terminal/strata_cli/launch/runner.py:229-249,2423-2439,3333-3343`）。

`tune auto` 自体の target 読み込み、未導入 engine、対象外モデルなどの失敗は JSON または stderr にエラーを出し、終了コードを返します。launch runner は子プロセスの終了コードと JSON 結果から結果表示を組み立て、通常は tuner が失敗しても標準設定で後続の起動へ進みます（`terminal/strata_cli/tune_commands.py:109-114,309-345,421-425`、`terminal/strata_cli/launch/runner.py:2423-2439`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:14-28,73-80,121-122` — `strata launch` の説明・例と parser 定義。
- `terminal/strata_cli/launch/cmd.py:35-43,274-277,874-877` — 値の正規化・検証、設定への反映、`--retune` 時の既定変更。
- `terminal/strata_cli/launch/settings.py:29,141-159` — 有効なモード、未指定時の値、tuning 済み状態。
- `terminal/strata_cli/launch/runner.py:2373-2439,2443-2479` — 適用条件、既存結果の再利用、tuner 呼び出し、進捗・結果・停止処理。
- `terminal/strata_cli/tune_commands.py:21-50,309-425` — tuner の mode parser、target/engine の検査、探索実行、preset・レポート保存、終了コード。
- `terminal/strata_control/presets.py:488-506` — 保存済み tuning preset の構成への適用条件。
