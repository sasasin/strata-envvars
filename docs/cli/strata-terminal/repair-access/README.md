# `strata repair-access`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata repair-access` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/private_files.py` |

## 役割

管理者権限で Strata を実行した後などに、自分の Strata データファイルへ通常ユーザーからアクセスできなくなった場合、既知のユーザーデータ領域を走査してアクセス権を修復します。parser の説明にも Windows での用途と記載されています。通常起動時にアクセス拒否を検出した場合も、CLI は同じ修復処理を一度試してコマンドを再実行します。

## 基本的な使い方

```sh
# 既知の Strata データ領域を修復して結果を表示
strata repair-access

# 同じ結果を JSON で取得
strata repair-access --output json
```

`--output` は `human` または `json` を受け取り、省略時は `human` です。詳細は [`--output`](--output.md)、全コマンドの一覧は [CLI 索引](../../README.md)を参照してください。

## 実行時の動作と副作用

- 走査対象は存在する `APPDATA/Strata`、`LOCALAPPDATA/Strata`、`~/.strata` と、設定されている `STRATA_HOME`、`STRATA_PROFILE_DIR`、`STRATA_RUNTIME_DIR`、`STRATA_STATE_DIR`、`STRATA_INSTALL_DIR` です。大文字小文字を区別しない文字列比較で重複を除きます。
- Windows 以外では修復対象を走査せず、件数 0 の成功レポートを返します。Windows では対象ディレクトリをたどり、アクセス拒否で開けないディレクトリやファイルについて現在のユーザーのアクセス権を設定します。対象外のパスを修復する機能ではありません。
- `models`、`node_modules`、`harness`、`python`、`host`、`node`、`control`、`__pycache__`、`.git` という名前のディレクトリは再帰走査しません。シンボリックリンクと `.gguf`、`.part`、`.bin`、`.safetensors`、`.zip`、`.exe`、`.dll` で終わるファイルも検査対象から除外します。
- 走査は `checked` が 20,000 に達するまでです。上限到達後に未処理項目が残っても、レポートに「上限到達」を示すフィールドはありません。修復は Windows ACL と所有者を変更する操作を含み、現在のプロセス権限で変更できない項目は失敗として数えられます。
- 人間向け出力は `checked N entries, repaired N, could not repair N` の形式です。失敗があれば続けてアクセス修復を案内する文を表示し、終了コード 5 を返します。失敗がなければ 0 です。JSON は `ok` と `checked`、`repaired`、`failed` を含みます。

## 起動時の自動修復

コマンド実行中に `PermissionError`（または文字列表現に `PermissionError` を含む例外）が発生し、`strata_control.private_files` を読み込める場合、CLI は一度だけ再試行します。通常のアクセス拒否では既知のルートを修復して元のコマンドを再実行します。Windows の共有違反（WinError 32/33 と判定されるもの）では修復せず 1.5 秒待って再実行します。再試行後も同様の例外が出るとエラー終了コード 5 を返します。この共通処理は `repair-access` 自身の走査上限や表示形式を変えるものではありません。

## 注意点

- このコマンドは Windows のアクセス制御修復を主目的とします。POSIX では成功扱いでも何も修復しません。
- 標準ユーザーが変更できない ACL や所有者の項目は修復に失敗することがあります。ソースは昇格済みセッションなら全項目を修復できる場合があると説明していますが、CLI 自身は権限昇格を行いません。
- 対象ルート内でも、除外ディレクトリや拡張子は走査しません。20,000 件の上限もあるため、このコマンドの成功表示だけで全ファイルのアクセス状態を保証するものではありません。

## 根拠

- Strata `strata_cli/cli.py:107-108` — サブコマンド説明、`--output` の選択肢と既定値。
- Strata `strata_cli/cli.py:2107-2116,2121-2126` — コマンドの処理、出力形式、終了コードと dispatch。
- Strata `strata_cli/cli.py:2085-2104,2166-2183` — 共通のアクセス拒否・共有違反時の再試行とエラー処理。
- Strata `strata_control/private_files.py:415-439,442-473` — ユーザールートの判定、Windows のみの修復、現在のユーザーの権限設定と再帰条件。
- Strata `strata_control/private_files.py:502-576` — 走査ルート、除外対象、20,000 件上限、個々の失敗の計上。
- Strata `strata_control/private_files.py:487-500` — 通常のアクセス拒否と共有違反の案内文・判定。
