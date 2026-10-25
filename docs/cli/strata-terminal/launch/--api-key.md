# `--api-key`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--api-key` |
| 別名 | なし |
| 値 | 必須の1引数 `KEY`。parser での形式・長さ検証はない |

## 役割

起動する Strata サーバーに設定する API キーです。クライアントは `/v1/*` のリクエストで `Authorization: Bearer <key>` または `x-api-key: <key>` を送ります。サーバーにキーを設定すると、キーがない、または一致しないリクエストは HTTP 401 になります（`serve/server.py:6352-6360`）。

## 使い方

キーをシェル履歴や引数一覧に直接書かず、先に `STRATA_LAUNCH_KEY` を設定して渡す例です。

```sh
strata launch --model q2_0 --access lan --api-key-env STRATA_LAUNCH_KEY --no-tui
```

`--api-key-env` は `strata launch` の別オプションで、指定した環境変数から値を読みます。`--api-key` 自体を使う場合は `strata launch --model q2_0 --access lan --api-key "$STRATA_LAUNCH_KEY" --no-tui` の形式です。parser 宣言は `strata_cli/launch/cmd.py:119-126` にあります。

## 値と既定値

- 値は1引数です。`argparse` が値の省略を構文エラーにしますが、`--api-key` に型変換や独自の長さ・文字種検証は指定されていません（`strata_cli/launch/cmd.py:123`）。
- オプションを省略した場合、保存済み preset があればそのキーを引き継ぎます。新たなキー生成は `access` が `local` 以外で、既存キーも `--no-api-key` もない場合に限られ、以前のキーを再利用し、なければ新規作成します（`strata_cli/launch/cmd.py:197-203, 341-350`; `strata_cli/launch/access.py:307-309, 320-350`）。
- `--api-key` の後に空文字を明示すると値が falsy のため設定値として採用されません。remote access の自動生成条件に該当すればキーが生成されます（`strata_cli/launch/cmd.py:256-269, 341-350`）。
- 値 `none` は大文字小文字を問わず予約され、文字列キーではなく認証なしを意味します。前後の空白を除いた値が `none` ならサーバー側でキーを無効化します（`serve/server.py:7649-7652, 8295-8303`）。
- サーバーは文字列中のカンマを複数キーの区切りとして解釈し、項目ごとの前後空白を除去します。空項目は除かれ、カンマだけ・空白だけのキーは `serve/server.py` の起動前検証で「API key was given but it is empty」として拒否され、その server 側処理は終了コード 2 を返します。`strata launch` は server 起動をランタイム経由で管理するため、この場合の Terminal CLI 側の最終終了コードはここで確認した parser/server 経路からは特定できません。カンマを含む単一キーを CLI 文字列として渡す方法も確認できません（`serve/server.py:7638-7646, 7665-7679, 8299-8303`）。

## 実行時の動作

`settings_from_args` はまず preset を読み、`--api-key` が truthy なら値を設定します。その後 `--api-key-env NAME` があれば環境変数値で上書きします。指定した環境変数が未設定または空なら `ValueError` になり、通常出力では stderr に `strata: ...`、JSON 出力ではエラー JSON を出して終了コード 2 になります（`strata_cli/launch/cmd.py:197-203, 256-269, 634-641, 832-835`）。

続けて `--no-api-key` が指定されている場合、明示的な `--api-key` または `--api-key-env` もあればキーを保持し、警告を記録します。どちらもなければ preset のキーを消して、意図的な認証なし設定にします。キーが残る場合は `no_key` を解除します（`strata_cli/launch/cmd.py:263-269`）。したがって、明示キーと `--api-key-env` の両方を指定した場合は環境変数側が優先し、そのうえで `--no-api-key` を併記してもキーが残ります。

実行設定では、キーがあれば `api_key` に保存し、意図的な認証なしなら `api_key: "none"` を保存、それ以外は継承元設定から `api_key` を削除します。実行設定は launch 専用 JSON に書かれ、POSIX ではモード `0600` を試み、Windows では現ユーザーだけに制限する処理を試みます（`strata_cli/launch/runner.py:371-382, 410-429, 1235-1243`）。`--save-preset` も使うと preset にキー値が保存されます。`--preset` に他のフラグを重ねただけなら、その起動時だけの変更です（`strata_cli/launch/store.py:75-85`; `strata_cli/launch/cmd.py:788-792`）。

remote access でキーが未指定なら、同名 launch の設定、preset、または最新の launch 設定から既存キーを保持し、見つからなければ新規作成します。キーのローテーションには `--new-key` を使います（`strata_cli/launch/cmd.py:341-350, 726-728`; `strata_cli/launch/access.py:320-350`）。local access では未指定時に自動生成されませんが、明示したキーは適用されます。`--access` が local 以外でキーなしの場合、認証なしの警告は出ますが、起動を拒否しません（`strata_cli/launch/settings.py:97-100, 183-190`; `strata_cli/launch/cmd.py:252-269`）。

## 適用条件と副作用

キーは `--access local|lan|cloudflare|tailscale` の別に関わらず launch の実行設定に入ります。認証はサーバーが受け付ける `/v1/*` リクエストに適用され、クライアントにはキーを別途設定する必要があります（`strata_cli/launch/cmd.py:119-126`; `serve/server.py:3842, 6352-6360`）。

通常のテキスト出力ではキー全体を表示せずマスクし、表示方法として `strata launch --show-key` を案内します。JSON 成功出力もキー値ではなく `"api_key": "set"` または `null` を返します（`strata_cli/launch/cmd.py:801-817`; `strata_cli/launch/settings.py:114-118`）。launch の設定・preset にはキー本体が保存されるため、それらのファイルは秘密情報として扱ってください（`strata_cli/launch/runner.py:371-382, 1235-1243`; `strata_cli/launch/store.py:75-85`）。

`none` または `--no-api-key` でネットワーク共有を認証なしにすると、到達できる利用者がモデルを使えます。サーバーは警告を出しますが、キーなしを強制的には拒否しません（`serve/server.py:7649-7662, 8295-8304, 8507-8509`; `strata_cli/launch/settings.py:183-190`）。

## 出力とエラー

- `--api-key-env NAME` の変数が未設定または空なら、設定処理がエラーになり終了コード 2 です（`strata_cli/launch/cmd.py:258-262, 832-835`）。
- 値 `none` は認証なしとして有効です。空白・カンマのみなど、サーバーの key parser が空と判定する値は server 側で stderr のエラーと終了コード 2 になり、`strata launch` 側で報告される最終終了コードは確認できていません（`serve/server.py:7665-7679, 8299-8303`）。
- 起動成功時、通常出力にはマスク済みキーと `--show-key` の案内が出ます。JSON 出力では設定有無だけを返します（`strata_cli/launch/cmd.py:801-817`）。
- 認証が有効なサーバーへ間違った値またはキーなしで `/v1/*` にアクセスすると、サーバーは HTTP 401 と `missing or wrong API key` を返します（`serve/server.py:6352-6360`）。

## 根拠

- parser とヘルプ文: `strata_cli/launch/cmd.py:119-126`。
- preset への読み込みと CLI 値の適用順: `strata_cli/launch/cmd.py:197-203, 256-269`。
- remote access 時のキー保持・生成: `strata_cli/launch/cmd.py:341-350`; `strata_cli/launch/access.py:307-350`。
- 実行設定への格納とファイル保護: `strata_cli/launch/runner.py:371-382, 410-429, 1235-1243`。
- server の複数キー、`none`、空値検証と認証: `serve/server.py:6348-6360, 7638-7679, 8290-8304`。
- 索引上の配置・scope: `docs/cli/README.md` の `strata launch` 節。調査基準: `docs/cli/001_investigation.md`。

調査範囲は上記 checkout のソースです。同一 revision の `--help` や Release 配布物との別途照合は行っていません。
