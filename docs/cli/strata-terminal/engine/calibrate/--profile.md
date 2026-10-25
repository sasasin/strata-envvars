# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 必須の profile 名、または run config JSON ファイルのパス |

## 役割

校正の対象となる保存済み serving profile、または run config を選びます。対象は `--plan`、`--measure`、結果の review/apply、rollback review/実行の全操作で共通です。profile 名を渡すと、その profile が指す run config を読み、profile ID・revision も校正レポートの対象識別に使います。JSON パスを渡すと run config を直接選び、保存 profile の識別情報や journal 記録を使わない従来経路になります。

これはネイティブ推論エンジンの profile 指定ではなく、Terminal CLI の校正対象の指定です。

## 使い方

```sh
# 保存済み profile を対象に、読み取り専用の事前確認
strata engine calibrate --profile office --plan

# run config を直接指定して、校正結果を新規ファイルへ測定
strata engine calibrate --profile ./strata-model.json --measure --exclusive --out ./calibration-report.json
```

校正の計測は GPU への排他的アクセスを要求し、通常 15〜30 分かかると CLI が案内します。実測または設定適用を行う前に、対象 profile の稼働インスタンスを停止してください。

## 値と既定値

- parser では値の型変換・選択肢・既定値は指定されず、`--profile` 自体は必須です。校正アクションも `--plan`、`--measure`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result` のいずれか一つが必須です（`strata_cli/cli.py:176-189`）。
- 値に `.json` 拡張子がある、絶対パスである、または `/` か `\` を含む場合はファイルパスとして解決されます。`~` は展開され、パスは絶対化されます。それ以外は保存 profile 名として扱われ、名前は小文字英字で始まり、小文字英数字・`_`・`-` のみ、最大64文字です（`strata_control/profiles.py:25,48-55,382-388`）。
- 保存 profile は既定で POSIX では `$XDG_CONFIG_HOME/strata/profiles`（未設定時 `~/.config/strata/profiles`）、Windows では `%APPDATA%/Strata/profiles` に置かれます。`STRATA_PROFILE_DIR` が設定されていればその場所を使います（`strata_control/profiles.py:38-45`）。
- run config JSON は `args` が文字列配列、`exe` と `tokenizer` が空でないパス文字列である必要があります（`strata_control/profiles.py:135-147`）。

## 実行時の動作

`--plan` は対象 config とコンポーネントを確認し、計画と校正ツールの有無を表示します。エンジン起動や設定ファイル書き込みは行いません（`strata_control/calibration.py:90-111`、`strata_cli/cli.py:1114-1126`）。

`--measure` は対象を再解決して変更がないことを確かめた後、profile の serving concurrency override を runtime 用 config に反映して計測し、config 自体は変更せず report を新規作成します。保存 profile を指定した場合、直接実行操作はローカル journal に記録されます。JSON パス指定時は journal を介しません（`strata_cli/cli.py:1048-1056,1065-1075`、`strata_control/calibration.py:270-286,289-336`）。

review と rollback review は指定 report を対象 config と照合し、適用可能性を JSON または整形 JSON で表示します。apply は report が新しく対象と一致することを再確認し、候補設定で smoke generation を行ってから config と setup の校正設定を更新し、復元用 backup と application record を保存します。rollback は適用時の状態が変わっていないことを確認し、復元候補の smoke generation 後に以前の config/settings を戻します（`strata_cli/cli.py:1076-1113`、`strata_control/calibration.py:363-385,526-626,646-681,684-710`）。

## 適用条件と副作用

- profile 名は既存の有効な profile でなければなりません。profile の `source_config` が対象 config になり、その ID/revision は校正結果の同一性確認に含まれます。profile の `parallel` / `batch_groups` override は計測時の runtime config に反映され、engine args との衝突は拒否されます（`strata_control/profiles.py:120-132,150-166,382-388`、`strata_control/calibration.py:125-139,146-166`）。
- パス指定は profile 名への fallback をしません。`.json`、絶対パス、または区切り文字を含む値は、ファイルとして読み込まれます（`strata_control/profiles.py:382-388`）。
- `--measure`、`--apply-result`、`--rollback-result` は `--exclusive` が必要です。measure はさらに `--out REPORT.json` を要求します。`--out` は measure 以外で使えず、`--exclusive` は measure/apply/rollback 以外では使えません（`strata_cli/cli.py:1062-1067,1086-1089,1104-1107`）。
- 計測・適用・復元では管理下の実行インスタンスがないこと、profile の port で server が応答しないことを確認します。条件を満たさない場合は停止を要求して失敗します（`strata_control/calibration.py:192-211,214-229`）。
- `tools/calibrate.py` と `setup.py` を含まない Terminal archive では計測・結果の identity 確認に必要な full Strata folder がありません。`STRATA_INSTALL_DIR` で両ファイルを含む folder を指定すれば探索対象になります（`strata_control/calibration.py:41-79,146-151`）。
- 計測はエンジンを起動して hardware 依存設定を測ります。apply/rollback も smoke generation のためエンジンを起動します。plan と review 系は設定を書き換えません（`strata_control/calibration.py:95-111,289-336,388-409,526-626,646-681`）。

## 出力とエラー

- `--profile` が欠けている場合や校正アクションがない/複数ある場合は argparse が usage error にします（`strata_cli/cli.py:176-189`）。
- 不正な profile 名、存在しない profile、読めない/不正な run config は `ProfileError`（`ValueError`）となり、通常は `strata: <message>` を stderr に出してその例外の exit code（既定2、指定により5/6等）を返します。JSON 出力時は `ok:false` と error object を stdout に出します（`strata_control/profiles.py:30-35,48-55,135-166`、`strata_cli/cli.py:527-532,2166-2173`）。
- report 出力先がすでに存在する場合は上書きせず失敗します。また出力ディレクトリがない場合も、計測前に拒否されます（`strata_control/calibration.py:289-296`）。
- 計測では全対象インスタンス停止、port 非稼働、engine/model component の存在が前提です。校正中に profile/config、engine、model、hardware identity が変わった場合は report が stale 扱いになるか、適用を拒否します（`strata_control/calibration.py:292-325,363-385,537-571`）。
- 校正計測の中断は「config unchanged」として exit code 130、その他の測定失敗や古い report は主に exit code 6 で報告されます（`strata_control/calibration.py:303-315,543-545`）。

## 根拠

- `strata_cli/cli.py:174-189` — コマンド parser、`--profile` の必須指定、アクション・関連 option。
- `strata_cli/cli.py:1048-1056,1059-1126` — 対象の profile/path 解決と各アクションへの受け渡し、制約、出力。
- `strata_control/profiles.py:25,30-55,120-147,150-166,382-388` — profile 名・保存場所・run config 検証・名前と path の判定。
- `strata_control/calibration.py:41-79,90-111,125-166,192-229,270-336,363-385,526-626,646-710` — 対象 config の利用、排他確認、計測・review・適用・復元と副作用。
- `strata_cli/cli.py:527-542,2166-2188` — 人向け/JSON のエラーと成功出力。

調査範囲は上記 checkout の Python CLI と calibration/profile 実装です。同一 revision の CLI `--help`、Release 配布物、各 OS での実行結果は確認していません。
