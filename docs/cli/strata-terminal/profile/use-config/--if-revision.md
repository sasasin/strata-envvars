# `--if-revision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile use-config` |
| オプション | `--if-revision` |
| 別名 | なし |
| 値 | `REVISION` を1つ取る。保存 profile の revision 文字列と完全一致する必要がある |

## 役割

確認した profile revision を指定し、別の run config を選択する時点で profile がその revision のままかを確認します。`--plan` と保存実行のどちらでも判定されるため、preview 後に別の編集が入った状態で古い選択を適用するのを防げます。option を省略した場合は、この明示的な preview revision 照合を行いません。

## 使い方

まず preview の JSON に含まれる `revision` を確認し、その値を選択実行へ渡します。

```sh
strata profile use-config four-gpu --from-config /absolute/path/next-model.json --plan --output json
strata profile use-config four-gpu --from-config /absolute/path/next-model.json --if-revision PROFILE_REVISION --output json
```

この操作は保存 profile の参照先を変更します。稼働中の instance はこのコマンドでは変更されず、必要なら別途 restart します。

## 値と既定値

- parser は `--if-revision REVISION` を任意引数として定義し、既定値は `None`（未指定）です。必須指定ではありません。
- CLI 側で値の形式や長さを個別に検証する処理はありません。値は読み込んだ profile の revision と文字列として完全一致するか比較されます。一致しない値（空文字を含む）は revision 不一致になります。
- revision は profile JSON の保存 bytes に対する SHA-256 の先頭16桁です。生成形式は16文字の小文字16進数ですが、このオプションの値には形式 validation をかけず、等値比較で確認します。
- parser は `argparse` の既定 action を使うため、複数回指定した場合は最後の値が比較に使われます。

## 実行時の動作

`use-config` は先に保存 profile を読み、指定された run config を解決・検証します。その後、source の preview が読んだ revision が最初に読み込んだ revision と一致するかを確認し、さらに `--if-revision` があればそれとも照合します。`--plan` の場合は source の変更案・revision・`would_save` などを出力して保存せずに終了します。通常実行では、確認した revision を保存時の `expected_revision` として渡します。

`--if-revision` がない場合でも、profile の load/propose 間の不一致と、保存時点での profile 変更は拒否されます。明示指定の役割は、利用者が preview で見た revision を選択実行時に照合することです。設定ファイルの内容自体を pin するオプションではありません。

run config は既存ファイルとして解決され、regular file であり、JSON の `args` が文字列配列、`exe` と `tokenizer` が空でない文字列であることを確認します。profile の source path が変わる保存では、旧 profile の履歴を作り、新しい profile を atomic replace で保存します。同じ source path を指定して結果が現行 profile と同一なら、保存は変更されず revision も変わりません。稼働中 instance は変わりません。

## 適用条件と副作用

- `strata profile use-config` の parser にだけ属する option です。
- 指定値が現在の profile revision と一致しなければ、保存・plan の分岐より前に失敗します。
- `--plan` は保存しません。通常実行では profile の保存ファイルと revision 履歴に書き込みますが、選択元の run config ファイルはこの操作では書き換えません。
- この option は run config の SHA-256 を確認しません。preview 後の run config 内容の固定や、稼働 instance の切り替えは別の runtime restart 操作の対象です。

## 出力とエラー

- 不一致時は `profile changed after preview; plan it again before selecting a config` で失敗し、終了コードは `6` です。比較は `--plan` の有無より前に行われます。
- option がなくても、preview 中に profile revision が変わった場合や保存ロック取得後に revision が変わった場合は保存を拒否します。保存競合時のエラーは `profile changed during edit; reload it before saving`、終了コードは `6` です。
- 保存 profile がない、または run config が利用できない場合も失敗します。profile 不在と run config 不在は終了コード `5`、run config の必須 JSON 構造が不正な場合は `2` です。
- `--output json` では失敗は `{"schema_version":1,"ok":false,"error":{"code":6,"message":"..."}}` 形式、human 出力では `strata: ...` を stderr に出します。
- `--plan --output json` の成功結果には `profile`、`revision`、`source_config` の before/after、候補 config の `model_name`、`would_save` が含まれます。通常の JSON 成功結果には保存 profile、`previous_revision`、新しい `revision`、source の before/after が含まれます。

## 根拠

- `strata_cli/cli.py:89-95` — `use-config` の parser、必須の `--from-config`、任意の `--if-revision`、`--plan`、出力形式。
- `strata_cli/cli.py:968-985` — profile の読み込み、preview revision と指定値の比較、plan 出力、保存呼び出し、稼働 instance が変わらない旨の出力。
- `strata_control/profiles.py:62-63,150-166` — revision の生成、profile 読み込みと revision の算出。
- `strata_control/profiles.py:252-263` — run config の path 解決、regular file 検査、構造確認、source の提案。
- `strata_control/profiles.py:135-147` — run config JSON の必須構造と読み取り失敗。
- `strata_control/profiles.py:266-295` — 保存時の revision 再確認、履歴作成、atomic 保存、無変更時の扱い。
- `strata_cli/cli.py:527-541,2166-2173` — human/JSON 成功・失敗出力と `ProfileError` を含む `ValueError` の終了コード処理。
- `docs/TERMINAL.md:78-84` — profile source を切り替える利用者向け例と、restart を別途行う手順。

調査範囲は上記 checkout のソースと同一 revision の CLI 実装です。`--help` は補助実行しておらず、Release 配布物や OS ごとの配布 CLI は確認していません。
