# `--preset`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--preset` |
| 別名 | なし |
| 値 | 保存済み launch preset の名前（`NAME`）。parser に型・選択肢の制約はない |

## 役割

`strata launch` の設定を保存済み launch preset から読み込みます。ほかの launch option を同時に指定すると、preset の値を基にしつつ指定した値を重ねて起動します。preset は `strata connect --preset` にも同じ名前の別スコープの option がありますが、この文書は `strata launch` 用です（parser: `strata_cli/launch/cmd.py:83-85`, `strata_cli/launch/cmd.py:148-160`）。

## 使い方

```sh
strata launch --preset "Office" --no-tui
```

`--no-tui` を省略すると、対話端末では monitor を開く launch 画面経由で起動します。非対話環境では `--no-tui` などにより画面を開かず起動できます（`strata_cli/launch/cmd.py:16-30`, `strata_cli/launch/cmd.py:688-710`）。

## 値と既定値

- 値は必須の `NAME`。`argparse` 定義に `type`、choices、別名、明示的な default はなく、省略時は `None` です（`strata_cli/launch/cmd.py:83-85`）。
- 保存先では `NAME` を小文字化し、英小文字・数字・`-`・`_` 以外を `-` に変換、前後の `-`・`_` を除去し、空なら `launch`、先頭が英字以外なら `l` を前置し、48文字に切り詰めた文字列を JSON ファイル名に使います。したがって異なる名前が同じファイルに対応することがあります（`strata_cli/launch/settings.py:310-315`, `strata_cli/launch/store.py:35-37`）。
- 空文字列は parser では拒否されませんが、実行側で偽値として扱われ preset を読み込みません。名前を省略した場合と同様、通常の launch 選択がないと対話画面に進むか、非対話環境ではエラーになります（`strata_cli/launch/cmd.py:197-203`, `strata_cli/launch/cmd.py:688-700`）。

## 実行時の動作

1. `--preset` が空でなければ `store.load(NAME)` を呼び、読み込んだ設定を初期値にします。保存データに名前がなければ `NAME` を補います（`strata_cli/launch/cmd.py:197-203`, `strata_cli/launch/store.py:88-103`）。
2. 同時指定された option は、設定オブジェクト内の対応項目を上書きします。たとえば `--model`, `--context`, `--access`, `--port`, `--set` などが該当します。指定されていない項目は preset の値が残ります（`strata_cli/launch/cmd.py:204-281`）。
3. `--plan` と併用すると、preset を読み込み設定を組み立てて計画を表示し、通常の起動処理へ進まず「変更なし」として終了します（`strata_cli/launch/cmd.py:733-760`）。
4. 非 TUI 経路では launch が成功した後、`--save-preset` があればその名前で設定を保存し、なければ指定 preset の `last_used` を更新します。従って `--preset NAME --set ... --no-tui` の変更は通常保存されず、`--save-preset NAME` を付けると保存されます（`strata_cli/launch/cmd.py:788-792`, `strata_cli/launch/store.py:75-85`, `strata_cli/launch/store.py:139-143`）。
5. 対話 TUI 経路では挙動が異なります。実行後、同名の preset が既に存在すれば `--save-preset` の有無にかかわらず、起動時設定をその preset に保存し直し `last_used` も更新します。TUI で `--preset` と上書き option を使うと、変更が保存され得ます（`strata_cli/launch/cmd.py:780-783`, `strata_cli/launch/app.py:350-377`）。

管理系 option との併用では通常の preset 起動をしません。`--stop` は preset slug から対象 profile 名を組み立てて停止対象を絞り、`--show-key` はその preset の launch 情報から API key を取得します。これらの分岐は通常の preset 設定読込より先に処理されます（`strata_cli/launch/cmd.py:643-677`）。

保存ファイルは既定で profiles ディレクトリの隣の `launch-presets/` に置かれ、`STRATA_LAUNCH_PRESET_DIR` が設定されている場合はそのディレクトリが使われます。ファイルには API key を含み得るため、保存処理は POSIX で mode `0600` を設定し、Windows では利用可能なら現在ユーザーだけに制限します（`strata_cli/launch/store.py:27-32`, `strata_cli/launch/store.py:39-60`）。

## 適用条件と副作用

- preset が見つからない場合は読み込みに失敗します。読めない JSON 等は破損・読取エラーとして扱われ、削除して保存し直す案内が出ます（`strata_cli/launch/store.py:88-103`）。
- launch 実行時にはモデル、エンジン、ネットワーク共有など、読み込んだ設定に従う通常の `strata launch` の副作用が発生します。`--plan` ではその起動処理を行いません（`strata_cli/launch/cmd.py:715-760`, `strata_cli/launch/cmd.py:784-800`）。
- preset の JSON は小文字化・slug 化したファイル名で参照されますが、保存済みデータ内の表示名は別に保持されます（`strata_cli/launch/store.py:35-37`, `strata_cli/launch/store.py:101-103`）。

## 出力とエラー

- preset が存在しない場合は「There is no saved preset called ...」と、利用可能な preset または近い名前が示されます。破損・読取不能時は削除して再保存する案内が出ます（`strata_cli/launch/store.py:88-112`）。
- これらの `PresetError` は終了コード `2` になります。人間向け出力では `strata: ...` を stderr に出し、`--output json` では `ok: false` とエラー情報を JSON で stdout に出します（`strata_cli/launch/cmd.py:630-641`, `strata_cli/launch/cmd.py:832-837`）。
- 対話画面を使えない非対話環境で選択肢もない場合は終了コード `2` で、`--preset NAME` または `--model NAME` の指定を促します（`strata_cli/launch/cmd.py:697-700`）。

## 根拠

- parser 定義と `connect` とのスコープ差: `strata_cli/launch/cmd.py:75-85`, `strata_cli/launch/cmd.py:148-160`
- preset の読込・option 上書き: `strata_cli/launch/cmd.py:197-281`
- plan、対話/非対話分岐、成功後の保存: `strata_cli/launch/cmd.py:688-710`, `strata_cli/launch/cmd.py:733-792`
- TUI 実行後の既存 preset 保存: `strata_cli/launch/app.py:350-377`
- 保存パス、読込失敗、権限、更新日時: `strata_cli/launch/store.py:27-60`, `strata_cli/launch/store.py:75-103`, `strata_cli/launch/store.py:139-143`
- 名前の slug 化: `strata_cli/launch/settings.py:310-315`

索引: [`strata launch` の `--preset`](../../README.md#strata-launch-launch)（option の専用リンクは索引内）。
