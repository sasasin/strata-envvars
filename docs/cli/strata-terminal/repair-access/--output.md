# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata repair-access` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json`。既定値は `human` |

## 役割

修復結果の表示形式を人向けの件数表示または JSON に切り替えます。出力先ファイルは指定しません。このコマンドは、管理者権限で実行した Strata がロックした可能性のある Strata のユーザーデータへのアクセスを修復します（`strata_cli/cli.py:107-108`; `docs/cli/README.md:145-150`）。

## 使い方

```console
strata repair-access --output json
strata repair-access
```

省略時は `human` です。

## 値と検証

parser は `choices=("human", "json")`、既定値 `human` を定義します。別名 `--json` はこの parser に登録されず、one-shot parser へ alias を追加する parser 群にも含まれません（`strata_cli/cli.py:107-108,508-515`）。未対応値は argparse がコマンド処理前に拒否し、終了コード 2 になります。余分な引数も拒否されます（同 `:2223-2235`）。

## 実行時の動作と副作用

`_repair_access()` は表示形式にかかわらず `private_files.repair_known_roots()` を呼びます。`--output` は修復対象や修復動作を変えません（`strata_cli/cli.py:2107-2116`）。

走査対象は、存在する `%APPDATA%/Strata`、`%LOCALAPPDATA%/Strata`、`~/.strata` と、設定されている場合の `STRATA_HOME`、`STRATA_PROFILE_DIR`、`STRATA_RUNTIME_DIR`、`STRATA_STATE_DIR`、`STRATA_INSTALL_DIR` の各パスです。パスの重複は小文字化した文字列で除外します。既定では、走査済み件数が 20,000 件以上になると次のフォルダー走査を始めない条件があります（`strata_control/private_files.py:506-524,527-539`）。

Windows 以外では空の件数報告を返して修復しません。Windows では、アクセス拒否されたユーザーデータ内のファイルやフォルダーに対し、現在ユーザーの SID に対するアクセス権を設定し、所有権を取り戻す処理を試みます。必要な権限がない通常ユーザーでは失敗し得ます。また、ユーザー自身の領域外は修復対象として拒否されます（`strata_control/private_files.py:442-473,534-536`）。

走査はシンボリックリンクを辿らず、`models`、`node_modules`、`harness`、`python`、`host`、`node`、`control`、`__pycache__`、`.git` の各ディレクトリと、`.gguf`、`.part`、`.bin`、`.safetensors`、`.zip`、`.exe`、`.dll` で終わるファイルをスキップします。アクセス制御を変更し得るため、読み取り専用の診断ではありません（`strata_control/private_files.py:502-503,537-575`）。

## 出力と失敗

- `human`（既定）は標準出力に `checked <件数> entries, repaired <件数>, could not repair <件数>` を表示します。失敗件数があれば `ACCESS_MESSAGE` も標準出力に表示します（`strata_cli/cli.py:2110-2116`）。
- `json` は標準出力へ `ok`、`checked`、`repaired`、`failed` を含む JSON オブジェクトを出します。`ok` は `failed` が 0 かを表します（同 `:2110-2116`）。
- 修復失敗があれば終了コード 5、なければ 0 です。Windows 以外は空の報告のため、ソース上は 0 になります（`strata_cli/cli.py:2116`; `strata_control/private_files.py:534-536`）。走査中の一部の `OSError` は対象を飛ばし、権限拒否を修復できなかった場合は `failed` に計上します（`strata_control/private_files.py:527-555,569-575`）。

## 調査範囲

指定 revision の parser、実装、修復 helper を静的に確認しました。CLI help、Windows 上での実動作、各権限構成での挙動、配布 Release の実体は確認していません。

## 根拠

- `strata_cli/cli.py:107-108` — parser、値の選択肢、既定値。
- `strata_cli/cli.py:508-515` — `--json` alias を追加する parser 群。repair-access は対象外。
- `strata_cli/cli.py:2107-2116` — 修復呼び出し、出力、終了コード。
- `strata_cli/cli.py:2217-2235` — 引数解析と余分な引数の拒否。
- `strata_control/private_files.py:442-473,506-575` — 修復条件・効果、対象ルート、走査制限と失敗集計。
- `docs/cli/README.md:145-150` — 索引上のコマンド階層とオプションスコープ。
