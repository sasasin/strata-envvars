# `STRATA_NO_REPAIR_ACCESS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 所有コードを対象とし、外部ライブラリの環境変数動作は含めない。

## 役割

Windows の Strata Host 起動時に自動実行する `strata repair-access` を抑止します。これは Node.js の Host が直接読む環境変数です。C++ engine の動作を制御する変数ではありません。

## 値と判定

Host は `!process.env.STRATA_NO_REPAIR_ACCESS` で JavaScript の truthy 判定をします。文字列の parse、数値変換、trim、大小文字変換はありません。

| 値 | 自動修復呼び出し |
|---|---|
| 未設定 | 続行（条件を満たせば呼ぶ） |
| 空文字 `""` | 続行（未設定と同じ） |
| 空でない文字列 | 抑止。`"0"`、`"false"`、空白だけの文字列も抑止 |

## 有効になる条件

自動呼び出しは、Control が見つかり、実行 OS が Windows（`process.platform === 'win32'`）で、かつ本変数が未設定または空文字の場合だけ行われます。Control が見つからない場合や他 OS では、本変数の値にかかわらずこの分岐は実行されません。Control の候補は `STRATA_CONTROL_DIR`、Host の隣の `control`、更新済み Control で、完全な候補のうち新しい版が選ばれます (`apps/host/server/control-runtime.mjs:53-75`)。

この変数は Host 起動時の自動呼び出しだけを止めます。明示的な `strata repair-access` CLI の処理 (`strata_cli/cli.py:107-108,2107-2116`) や、別経路で実行中の engine 起動がアクセスエラーになった際に `native-control` が修復を試す処理 (`apps/host/server/native-control.mjs:369`) を、この変数が抑止する参照はありません。

## 実行時の詳細

Host モジュールの初期化時に環境を読み、その場で分岐します (`apps/host/server/index.mjs:123-126`)。以後の環境変更を再評価する cache や watcher はありません。分岐を通ると Control の `repair-access --output json` を 60 秒 timeout で実行します (`apps/host/server/control-runtime.mjs:296-303`)。Control のプロセス環境は親環境を複製して一部の Python/Strata 設定を除く方式で、本変数自体は除外されず子にも渡ります (`apps/host/server/control-runtime.mjs:88-103,124-130`)。ただし、この名前を読む Strata コードは Host の分岐一か所だけです。

この CLI は Windows で、`APPDATA/Strata`、`LOCALAPPDATA/Strata`、`~/.strata` と設定された Strata data root を最大 20,000 entry まで走査し、アクセスできない entry の修復を試みます。走査対象外の directory 名・拡張子があり、修復できなかった件数は JSON の `failed` に含まれます (`strata_control/private_files.py:505-527,530-579`)。個別の修復はユーザー自身の data folder 内に限り、権限が足りない場合は `False` を返します (`strata_control/private_files.py:436-476`)。

自動呼び出しは `void` で結果を待たず、失敗結果も利用しません (`apps/host/server/index.mjs:126`)。`repairAccess()` は起動失敗や timeout を含む例外を `{ok:false, error:...}` に変換して返し、呼び出し側には伝播させません (`apps/host/server/control-runtime.mjs:297-303`)。CLI は JSON 結果を stdout に出し、修復失敗がある場合は終了コード 5 を返します (`strata_cli/cli.py:2107-2116`)。この自動呼び出し経路で Host が結果・失敗をログ出力する処理は確認できません。起動時コメントは「best effort, never blocks」としています (`apps/host/server/index.mjs:125`)。

## 根拠

- 唯一の完全一致参照と Windows / Control 条件: `apps/host/server/index.mjs:123-126`。
- Control の検出条件と候補: `apps/host/server/control-runtime.mjs:53-75`。
- 子プロセス環境と起動・timeout・stderr / 終了コードの収集: `apps/host/server/control-runtime.mjs:88-103,124-162`。
- 自動修復の CLI 呼び出しと失敗の戻り値化: `apps/host/server/control-runtime.mjs:296-303`。
- CLI サブコマンドの JSON / human 出力と失敗時終了コード: `strata_cli/cli.py:107-108,2107-2116`。
- 修復対象 root、走査上限、除外対象、個別修復条件: `strata_control/private_files.py:418-476,505-579`。
- 同じ名前の全参照検索では上記 Host の一か所のみ。`docs/DETAILS.md` にこの変数の説明は見つからなかった。
