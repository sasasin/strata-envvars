# `--drafting`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--drafting` |
| 別名 | なし |
| 値 | `auto`、`mtp`、`dflash2`、`off` のいずれか（値を1つ取る） |

## 役割

起動するモデルの推測デコーダー（drafting）を選びます。Strata は1回の起動で DFlash2、モデル内蔵の MTP draft layer、または drafting なしのいずれか1つを使います。DFlash2 は対応モデル・engine が利用可能な場合の選択肢で、MTP はモデルに含まれる draft layer です。 (`strata_cli/launch/cmd.py:104-107`; `strata_control/drafting.py:1-20`)

## 使い方

```sh
strata launch --model iq3_xxs --drafting mtp --no-tui
strata launch --preset "Office" --drafting off --no-tui
```

モデル識別子は例です。実際には `--model` に Terminal のモデル一覧にある名前を指定します。プリセットと併用したときは、この起動での値がプリセット設定に重ねられます。 (`strata_cli/launch/cmd.py:84-85,104-107`; `strata_cli/launch/cmd.py:212-218,249-250`)

## 値と既定値

- `auto`: LaunchSettings の初期値。プリセットを指定しない場合は `None`（Auto）で、`strata_control.drafting` がモデル・backend・engine に応じて MTP または DFlash2 を決めます。プリセットに drafting の選択が保存されていれば、それを引き継ぎます。 (`strata_cli/launch/settings.py:110-129`; `strata_cli/launch/cmd.py:212-218`; `strata_control/drafting.py:34-41,404-406`)
- `mtp`: モデルの MTP draft layer を使います。
- `dflash2`: DFlash2 を選びます。対応モデル・engine で pack が未取得なら起動準備時に取得を試みます。
- `off`: MTP と DFlash2 の両方を使いません。 (`strata_control/drafting.py:784-794`)

値は前後空白を除いて小文字化してから照合されるため、大文字・小文字は区別されません。ほかの文字列は parser の型変換で拒否され、選択肢と近い値があれば候補を添えた argparse エラーになります。 (`strata_cli/launch/cmd.py:37-45,104-107`)

`--drafting` を省略すると、新しい設定では Auto、`--preset` 使用時は保存済み設定が基準です。明示した値は `settings_from_args` がその設定に上書きします。なお DeepSeek-V4.1 では launch config にこの選択を書き込まず、DeepSeek 独自の DSpark 経路を使います。 (`strata_cli/launch/settings.py:127`; `strata_cli/launch/cmd.py:212-218,249-250`; `strata_cli/launch/runner.py:533-549`; `strata_cli/launch/runner.py:2473-2479`)

## 実行時の動作

- Auto は通常、DFlash2 対応モデルかつ利用可能な engine なら DFlash2、それ以外は MTP に解決されます。対応 family は `qwen`、`gyro`、`unsloth`。DFlash2 engine 対応 backend は CUDA、HIP、Metal、SYCL です。実際の判定はモデル名/family、backend、engine、MTP の有無などを `decide` に渡して行います。 (`strata_control/drafting.py:34-41,254-258,664-691`; `strata_cli/launch/modelstate.py:84-92`)
- DFlash2 は複数同時リクエストなどの併用不可条件に当たる場合、または pack / vocabulary が使えない場合に適用できません。適用不能時は MTP があれば MTP、なければ drafting なしへ切り替え、理由を通知します。DFlash2 は1リクエストずつ処理するため、Auto が DFlash2 になる条件で並列数を指定しなければ、Terminal は1リクエストに設定する旨を通知します。利用者が複数リクエスト数を明示した場合はその数を維持し、MTP に切り替わります。 (`strata_control/drafting.py:534-542,664-702`; `strata_cli/launch/runner.py:1567-1579`)
- DFlash2 pack が必要でデータディレクトリが判明しているとき、起動準備で selector pack のローカル変換（該当engineの場合）を行い、続けて pack を取得します。取得失敗は warning として記録し、MTP が利用可能なら MTP で、そうでなければ drafting なしで起動を続けます。 (`strata_cli/launch/runner.py:1581-1606`)
- `--drafting off` は launch config の `mtp` を false にし、既存 engine 引数から MTP 指定を取り除きます。`--mtp off` も draft layer を無効にします。明示的な `--drafting mtp` 等は既存の `mtp: false` を上書きして有効化する場合があります。 (`strata_cli/launch/runner.py:558-565`; `strata_control/drafting.py:807-820`)
- 全カード分割 engine が対象となるとき、Auto はこの engine が実行する MTP を計画・取得対象にします。明示した `dflash2` または `off` は全カード分割 engine の選択条件に合わず、通常の layer split 経路になります。分割に必要な MTP ファイルがない場合、`--split-engine on` では不足を通知して通常の layer split に戻ります。 (`strata_cli/launch/runner.py:1511-1518,1552-1565,1652-1661`; `strata_control/split_engine.py:461-471`)
- エンジン引数には選択された drafter の設定だけが残るよう変換されます。MTP は DFlash2 の引数を除去し、DFlash2 は MTP 引数を除去して DFlash2 の engine flags を追加します。 (`strata_control/drafting.py:784-831`)

## 適用条件と副作用

DFlash2 は Qwen3.8-Flash-Next 系（`qwen`、`gyro`、`unsloth` family）向けです。指定してもモデルや環境が対応しない場合は parser で拒否されず、通常は MTP へ fallback します。 (`strata_control/drafting.py:254-258,664-691,796-801`)

DFlash2 が未取得の場合、ネットワーク取得とローカル pack 生成が発生することがあります。全カード分割 engine で Auto を使う場合は MTP draft layer の取得が起動準備の対象になり得ます。`--plan` は起動時に必要な MTP / DFlash2 を表示しますが、計画表示メソッド自体は変更・ダウンロードを行わないと記載されています。 (`strata_cli/launch/runner.py:1581-1598,2260-2284,2473-2488`; `strata_cli/launch/runner.py:2473-2475`)

## 出力とエラー

無効な値は parser の validation error になります。DFlash2 が利用できない理由や取得失敗は warning / notice として表示され、実装上、取得失敗だけを理由に launch を中止せず代替 drafting で続行します。全カード分割 engine を明示的に要求して MTP layer がない場合は、必要な layer と `--drafting mtp` を案内して通常の layer split へ戻します。 (`strata_cli/launch/cmd.py:37-45`; `strata_cli/launch/runner.py:1581-1606,1652-1661`)

## 根拠

- `strata_cli/launch/cmd.py:37-45,104-107,212-218,247-250` — parser 値の検証、選択肢、設定への反映。
- `strata_cli/launch/settings.py:110-129` — 初期値とプリセット設定フィールド。
- `strata_cli/launch/runner.py:533-565,936-957` — launch config と setup 引数への反映。
- `strata_cli/launch/runner.py:1511-1518,1552-1565,1581-1606,1652-1661,2260-2284,2473-2488` — Auto 解決、分割 engine、取得・fallback、計画表示。
- `strata_control/drafting.py:34-41,254-258,404-406,534-542,664-702,784-831` — 選択肢、対応条件、fallback と engine 引数構成。
- `strata_control/split_engine.py:461-471` — 全カード分割 engine が受け付ける drafting 条件。

注: CLI の `--help` は実行していません。現行ソースの parser と実装を根拠にしています。backend ごとの実機動作や全モデル・engine 組み合わせは、この調査では実行確認していません。
