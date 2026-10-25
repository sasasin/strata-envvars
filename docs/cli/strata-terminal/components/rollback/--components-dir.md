# `--components-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネントフォルダーのパス（文字列） |

## 役割

rollback 対象となるエンジンと updater の状態ファイルを置くコンポーネントフォルダーを指定します。rollback はそのフォルダー内に保存された「前回の更新で保持したエンジン」を探し、次回起動時にそのエンジンが選ばれるよう pin を記録します。rollback 自体はネットワークから取得しません（`strata_control/updater.py:1033-1035`）。

## 使い方

```sh
strata components rollback --components-dir /srv/strata/components
```

## 値と既定値

- parser は値を1つ受け取ります。型変換、選択肢、存在確認、絶対パス要件などの parser 側 validation はありません（`strata_cli/update_cmd.py:30-39,57-59`）。
- 値が空でない場合は `Path(a.components_dir)` を使います。省略時、または空文字列の場合は `strata_control.engine_component.components_dir()` にフォールバックします（`strata_cli/update_cmd.py:174`; `strata_control/engine_component.py:176-186`）。
- 既定の格納先は `STRATA_COMPONENTS_DIR` が設定されていればその値、なければ Windows では `%LOCALAPPDATA%/Strata/components`（未設定時はホーム下の `AppData/Local/Strata/components`）、それ以外では `$XDG_DATA_HOME/strata/components`（未設定時は `~/.local/share/strata/components`）です（`strata_control/engine_component.py:176-186`）。
- 指定先は updater の状態・ロック・エンジン格納場所に使われます。ディレクトリがなければ、少なくともロック取得時に `<指定先>/.updates` が作成されます（`strata_control/updater.py:129-152`）。

## 実行時の動作

1. 共通 parser で `--components-dir` を受理し、`update_cmd.run` が指定値または既定値を `root` として `Context.components` に設定します（`strata_cli/update_cmd.py:30-39,57-59,163-184`）。
2. `strata components rollback` の分岐では、実行中エンジンの検出関数を設定し、必要なら待機処理を行った後、`rollback_engine(ctx)` を呼びます。この分岐は update の feed 読み込みや acquire 禁止チェックを通りません（`strata_cli/update_cmd.py:185-196`; feed/acquire を行う通常 update 側は同:197-213）。
3. rollback は `<root>/.updates/state.json` の engine セクションに保存された `previous` を読み、`<root>/engine/<previous>` の manifest を読み込み、署名と全ファイルを検証します。検証後、現在の engine とハードウェア条件を使って解決し、`previous` が実際に選ばれることを確認します（`strata_control/updater.py:1033-1066`）。
4. 成功時は state に `pinned`, `previous`, `active` を記録します。現行 engine のバージョンが対象と異なる場合、そのバージョンを `skipped` に追加します。次の成功した更新時に pin は解除されます（`strata_control/updater.py:1033-1035,1055-1078`）。

同じ `--components-dir` 定義は `strata update` と `strata components update` にも使われますが、この文書の対象は索引どおり `strata components rollback` です（`strata_cli/update_cmd.py:42-59`）。`--backend` はハードウェア検出結果の backend を上書きし、rollback 時の engine 解決に影響します。一方、`--feed`、`--force`、`--model-config` は rollback 分岐の処理では参照されません（`strata_cli/update_cmd.py:174-188`; `strata_control/updater.py:1033-1078`）。

## 適用条件と副作用

- `previous` が state にない場合は「戻す先がない」として終了コード 2 になります。指定フォルダーが誤っていると、意図した Strata 環境とは別の場所の state / engine を参照します（`strata_control/updater.py:1036-1042`）。
- rollback は serving 中の engine がなくなるまで待つか、待機期限・停止要求に達すると拒否します。`--wait` は秒数の浮動小数値で、未指定時は 0 秒です。CLI 側では、human 出力かつ TTY の場合に確認を促すことがあります。それ以外は待機を依頼しないまま busy 判定へ進みます（`strata_cli/update_cmd.py:34-35,182-188,237-252`; `strata_control/updater.py:300-311,1036-1044`）。
- rollback の分岐より前に backend を含むハードウェア情報を検出します。実装コメントでは `nvidia-smi`、`rocminfo`、sysfs など既存情報を読む probe とされ、必要な場合は既存ツールの読み取り専用実行も行います（`strata_cli/update_cmd.py:174-180`; `strata_control/updater.py:249-270`）。
- 以前の engine が存在しない、またはすでにその engine が選択中なら変更せず終了コード 2 です。以前の engine の manifest / 署名 / ファイル検証に失敗した場合は終了コード 5 です。検証後にこの PC の条件で以前の engine が選ばれなければ pin を取り消して state を保存し、終了コード 5 で失敗します（`strata_control/updater.py:1040-1066`）。
- 成功時、engine ファイル自体は移動・削除せず state の pin を更新します。engine の identity が変わる場合に限り tuning の再確認マーカーを記録します。既存 preset は変更・削除しません。以前の recheck marker がある場合は新しい identity への変更に合わせて集約され、元の identity に戻る場合は marker が解消されます（`strata_control/updater.py:1055-1078`; `strata_control/preset_marks.py:72-96`）。
- ディレクトリ作成・state 保存・ロック作成などのファイル書き込みは指定したコンポーネントフォルダーに対して行われます。recheck marker の保存先はコンポーネントフォルダーとは別の tuning state 配下です（`strata_control/updater.py:129-152,193-204,1057-1078`; `strata_control/preset_marks.py:35-36,55-66`）。

## 出力とエラー

- 成功時は human 出力なら rollback 前後の version を表示し、preset marker の有無と新しい engine を再試行する方法を案内します。`--output json` または `jsonl` では成功 payload を JSON で出力します（`strata_cli/update_cmd.py:185-196`）。
- `UpdateError` と署名・feed・acquisition エラーは human 出力では `strata: ...` を stderr に出し、machine 出力では error JSON を stdout に出して、それぞれ定義された終了コードを返します（`strata_cli/update_cmd.py:163-172,225-234`）。rollback 固有の主なコードは「previous なし／すでに rollback 済み」が 2、「previous engine が使えない／この PC で選べない」が 5、実行中 engine のため待てない場合が 7 です（`strata_control/updater.py:65-75,1036-1066`）。

## 根拠

- parser と共通オプション定義: `strata_cli/update_cmd.py:30-39,42-59`
- 既定値の選択と rollback 分岐: `strata_cli/update_cmd.py:163-196`
- rollback 前のハードウェア検出: `strata_control/updater.py:249-270`
- component folder の環境変数・OS 別既定値: `strata_control/engine_component.py:176-190`
- rollback の確認、pin、state 更新、副作用: `strata_control/updater.py:1033-1078`
- 待機と busy 判定: `strata_cli/update_cmd.py:237-252`; `strata_control/updater.py:300-311`
- tuning preset 再確認 marker: `strata_control/preset_marks.py:35-36,72-96`
