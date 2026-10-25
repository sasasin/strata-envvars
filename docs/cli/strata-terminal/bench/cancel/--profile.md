# `strata bench cancel --profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench cancel` |
| 値 | 保存済み serving profile 名 |
| 既定値 | なし（必須） |
| 別名 | なし |

## 役割

`--profile` はキャンセル要求を送る benchmark の profile を指定します。`strata bench cancel` はこの値と `--path` で特定した出力先に対応する、実行中の保存済み profile benchmark に停止を要求します。単に同じ profile 名で動いている別 run を止めるものではありません（`strata_cli/cli.py:335-338, 1175-1182`; `strata_control/benchmarking.py:105-135, 138-148`）。

## 使い方

```sh
strata bench cancel --profile work --path /absolute/path/to/benchmark-run
```

`work` は保存済み profile 名の例です。`--path` は絶対パスで、run ディレクトリ、またはその run の `results.json` / `progress.json` を指定できます。後者の場合は親ディレクトリが run の対象になります（`strata_cli/cli.py:336-338, 1177-1180`; `strata_control/benchmarking.py:138-141`）。

## 値と既定値

parser は `--profile` を `required=True` として定義し、値を文字列として受け取ります。option 自体に既定値や `choices` はありません（`strata_cli/cli.py:335-338`）。

実行時に `profiles.load(a.profile)` が呼ばれます。profile 名は小文字英字で始まり、続きは小文字英字・数字・`_`・`-`、最大64文字です。名前に対応する保存済み profile ファイルが必要で、読込後には profile 内容も検証されます（`strata_control/profiles.py:25, 48-55, 150-166`; 呼出箇所: `strata_cli/cli.py:1179`）。未保存 profile、形式不正の名前、壊れた profile は失敗します。

## 実行時の動作と相互作用

`--profile` は必須の `--path` と組み合わせて使われます。CLI はまず `--path` が絶対パスかを検査し、その後 profile を読み込み、`benchmarking.request_cancel(profile, path)` に渡します。相対パスは cancel 処理に入る前に終了コード 2 のエラーになります（`strata_cli/cli.py:336-338, 1175-1180`）。

キャンセル要求側では、profile 名に対応する lease ファイルのロック状態と記録済み run path の SHA-256 を照合します。同じ profile でも別 run の lease なら対象になりません。さらに progress の状態が `running` であることを確認してから、run ディレクトリに排他的作成で `cancel.request` を置きます。既存の有効な marker があれば再要求として扱い、現在の progress が `cancelled` ならその状態を返します（`strata_control/benchmarking.py:78-79, 105-135, 138-168`）。

実行中 benchmark は marker を検出して処理を中断し、最終 report と progress にキャンセル状態を記録します。キャンセル要求コマンド自身が benchmark 子プロセスを直接終了する処理は確認できません（`strata_cli/bench.py:848-888`; marker 読取: `strata_control/benchmarking.py:171-181`）。

## 適用条件と副作用

- `--profile` に対応する profile が保存されていることが必要です。`profiles.load()` は profile ファイルを読み、管理者実行により権限がロックされていた場合は読み取り時に一度修復します（`strata_control/profiles.py:150-166`）。
- run 出力ディレクトリはディレクトリであり、POSIX では owner-only 権限である必要があります。profile lease が現在ロック中かつ同じ run path を指し、progress が `running` の場合に限り要求を作成します（`strata_control/benchmarking.py:138-148`）。
- `cancel.request` は mode `0600` で排他的に作成され、内容 `1` を書いて `fsync` されます。既存 marker が通常ファイルでない、リンク数・サイズ・権限が要件を満たさない場合は拒否されます（`strata_control/benchmarking.py:149-163, 171-181`）。
- 引数解析前の `main()` は `private_files.adopt_user_defaults()` を実行します。Windows では作成ファイルの既定 owner / ACL を設定し、Windows 以外では何もしません（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-385`）。

## 出力と失敗

要求を受け付けると、`--output human`（既定）では「Cancellation requested; check the saved report for the final outcome.」を表示します。`--output json` では `schema_version`、`ok`、結果の `path` と `state` を含む JSON を出力します。成功時の終了コードは 0 です（`strata_cli/cli.py:338, 535-542, 1180-1182`）。`state` は `cancel_requested` または、要求時点ですでに完了処理へ進んでいる場合の `cancelled` です（`strata_control/benchmarking.py:164-168`）。

相対 `--path` は終了コード 2。profile が見つからない、profile が不正、run が owner-only でない、progress が読めない・不正、または marker が不正な場合は `ProfileError` を介して通常は終了コード 5。該当する profile/path の run が active でない、または最終 report がすでに保存されていれば終了コード 6 です。`--output json` の場合はエラーも JSON、それ以外は stderr に `strata:` 付きで出力されます（`strata_control/profiles.py:30-35, 150-166`; `strata_control/benchmarking.py:138-168`; `strata_cli/cli.py:527-532, 2166-2183`）。

## 根拠

- 索引上のコマンド階層と文書リンク: `docs/cli/README.md:643-650`（文書配置・scope: `docs/cli/README.md` 冒頭）
- parser 定義、必須値: `strata_cli/cli.py:335-338`
- cancel 分岐、絶対パス検査、profile 読込、委譲: `strata_cli/cli.py:1175-1182`
- profile 名の形式とファイル読込・検証: `strata_control/profiles.py:25, 48-55, 150-166`
- run lease と指定 path の照合、marker 作成・返却: `strata_control/benchmarking.py:78-79, 105-168`
- benchmark 側のキャンセル反映と最終 report 保存: `strata_cli/bench.py:848-888`
- 成功/エラー出力、終了コード変換: `strata_cli/cli.py:527-542, 2166-2183`
- 引数解析前の user defaults 処理: `strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-385`

調査範囲は指定 revision のソースコードです。同一 revision の CLI help 実行や Release 配布物との照合は行っていません。option の受理・必須性は parser 定義と照合しました。
