# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile set` |
| オプション | `--json` |
| 別名 | なし（`--output json` も指定可能） |
| 値 | 値を取らない真偽フラグ。既定は `false` |

## 役割

成功・失敗の結果を1行の JSON として標準出力へ出します。`--json` は parser では `store_true` として定義され、`main()` が `a.output = "json"` に変換します。プロファイルの設定値を変更するオプションではなく、変更処理の結果表現を選びます（`strata_cli/cli.py:508-515`, `strata_cli/cli.py:2217-2237`）。

## 使い方

```sh
strata profile set four-gpu parallel=8 --json
strata profile set four-gpu parallel=8 --plan --json
```

`name` と1つ以上の `KEY=VALUE` は必須です。`--plan` を付けると変更を保存せず、保存した場合の差分を JSON で返します（`strata_cli/cli.py:84-88`, `strata_cli/cli.py:986-997`）。

## 値と既定値

`--json` 自体は値を取りません。省略時は `--output human` 相当で、`--json` を指定すると `--output` の値にかかわらず最終的に `json` になります。従って `--json --output human` の組み合わせも JSON 出力です。`--output` は `human` または `json` のみを受理します（`strata_cli/cli.py:84-88`, `strata_cli/cli.py:508-515`, `strata_cli/cli.py:2232-2237`）。

`--json` は `profile set` を含む one-shot parser 群へ共通ループから追加されています。別名はなく、`--output json` は同じ機械可読出力を直接選ぶ方法です（`strata_cli/cli.py:508-515`）。

## 実行時の動作

`profile set` は変更案を作成し、`--plan` の有無で保存の有無を分けます。JSON 出力では成功時に `schema_version: 1` と `ok: true` が付きます（`strata_cli/cli.py:535-542`, `strata_cli/cli.py:986-997`）。

- `--plan` 指定時: `profile`（名前）、現在の `revision`、変更されたキーごとの `before` / `after` を持つ `changes`、および差分があるかを示す `would_save` を返します。ファイル保存は行いません（`strata_cli/cli.py:990-992`）。
- `--plan` なし: `profile`（保存済みプロファイル全体）、`previous_revision`、新しい `revision`、`changes` を返します（`strata_cli/cli.py:993-997`）。値が既に同じ場合は `save()` が現在の profile と revision を返して書き込みを省略します。差分がある保存では、旧 profile を `.history/<name>/<revision>.json` に保存してから新 profile を atomic replace します（`strata_control/profiles.py:266-295`）。
- `--json` と `--plan` の組み合わせも1回限りの JSON 出力です。プロファイル編集は保存済み override を更新するだけで、実行中 server の再起動や再調整は行いません。server への適用は別操作です（`strata_cli/cli.py:986-997`; 利用者向け説明: `docs/TERMINAL.md:156`, `docs/TERMINAL_QUICKSTART.md:53-62`）。

`--json` は値の型付け・検証を変更しません。`set` の assignments は `KEY=VALUE` 形式で、`host`, `port`, `parallel`, `batch_groups`, `max_queue`, `queue_timeout`, `offline`, `batch_telemetry` を受け付けます。各型・範囲の検証は `strata_control/profiles.py:66-117`、複数指定の統合（同一キーの重複は後の値が残る）は `strata_control/profiles.py:304-309` にあります。

## 適用条件と副作用

`profile set` でのみこのオプションが登録されるのではなく、`profile_set` を含む共通の one-shot parser 群に登録されます。profile の保存先は Windows では `%APPDATA%/Strata/profiles`（`APPDATA` がなければ home 配下）、Unix 系では `${XDG_CONFIG_HOME:-~/.config}/strata/profiles` で、`STRATA_PROFILE_DIR` が優先されます（`strata_control/profiles.py:38-45`）。

`--json` 自体はファイル・ネットワーク・プロセスに副作用を起こしません。副作用は `--plan` の有無で異なります。`--plan` は profile を保存しません。通常実行で内容に差分があれば profile ファイルと履歴ファイルを書き換えます。これは実行中の server には反映されず、再起動も行いません（`strata_cli/cli.py:990-997`, `strata_control/profiles.py:266-295`）。

profile 読み込みは `read_bytes_repairing()` を経由します。管理者権限で作られた profile の権限を読み込み時に修復する場合があり、この動作は `--json` の有無によらず起こり得ます（`strata_control/profiles.py:150-166`）。

`--quiet` も同時に指定でき、`--output json` へ正規化された後は標準出力の捕捉・抑制経路に入らず JSON をそのまま出力します（`strata_cli/cli.py:514-515`, `strata_cli/cli.py:2232-2244`）。

## 出力とエラー

成功時は JSON オブジェクトを1行で標準出力へ出し、終了コード `0` です。JSON は `ensure_ascii=False`、`allow_nan=False` でシリアライズされます（`strata_cli/cli.py:535-542`）。

`profile set` 内で発生する `ValueError`（`ProfileError` を含む）は `--json` を機械出力判定に含めて捕捉され、標準出力に `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` を出します。profile 不在・形式不正などのコードは通常 `5` または `2`、編集中の revision 競合は `6` です（`strata_cli/cli.py:2166-2173`, `strata_cli/cli.py:527-532`, `strata_control/profiles.py:30-35`, `strata_control/profiles.py:150-166`, `strata_control/profiles.py:266-295`）。OS ファイル操作エラーは `_file_words()` で説明を整形し、JSON 指定時には JSON エラーとして終了コード `6` で返します（`strata_cli/cli.py:2176-2183`）。

引数 parser 自体の構文エラーや未知引数は `_run()` の例外処理に入る前に処理されるため、`--json` 指定時でも argparse の usage/error が標準エラーに出て終了します（`strata_cli/cli.py:2223-2235`）。

## 根拠

- Parser 定義と `--output` の選択肢: `strata_cli/cli.py:84-88`
- one-shot コマンドへの `--json` 追加: `strata_cli/cli.py:508-515`
- フラグから `output=json` への変換と quiet 経路: `strata_cli/cli.py:2217-2244`
- profile set の plan・保存分岐: `strata_cli/cli.py:958-997`
- JSON 成功・失敗の形式: `strata_cli/cli.py:527-542`
- override の型・値検証と保存の原子性・履歴: `strata_control/profiles.py:66-117`, `strata_control/profiles.py:266-309`
- profile 保存場所: `strata_control/profiles.py:38-45`
- 実行中 server への反映が別操作である旨: `docs/TERMINAL.md:156`, `docs/TERMINAL_QUICKSTART.md:53-62`

## 調査範囲

対象は上記 commit の Terminal CLI parser、profile handler、`strata_control.profiles` の profile 読み書き処理です。CLI を実行して help や実環境での JSON 出力は確認していません。OS ごとのファイルシステム挙動、実際の保存先権限・競合状態は checkout のソースだけでは再現確認していません。
