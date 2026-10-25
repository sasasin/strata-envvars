# `--if-instance-id`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--if-instance-id INSTANCE_ID` |
| 別名 | なし |
| 値 | 32 文字の小文字 16 進 instance ID |

## 役割

`--plan` で確認した実行中 instance がそのまま対象であることを条件にして、保存済み profile の restart を行います。instance ID だけでなく、同じ plan に表示される owner ID も `--if-owner-id` で指定する必要があります。実行前に状態が変わっていた場合は、別の instance を誤って停止・置換しないよう restart を拒否します。

## 使い方

```sh
strata runtime restart --profile my-profile --plan
strata runtime restart --profile my-profile \
  --if-owner-id 0123456789abcdef0123456789abcdef \
  --if-instance-id fedcba9876543210fedcba9876543210
```

2 行目は実行例の形式です。ID は必ず対象環境で `--plan` が返した値に置き換えてください。通常の実行では現行 server を drain して新しい設定で起動するため、plan の結果を確認してから実行します。

## 値と既定値

- 値は必須です。parser は `INSTANCE_ID` を受け取り、オプション自体を省略した場合の値は `None`（事前条件なし）です。
- `strata_control.management._optional_identity` は値を `[0-9a-f]{32}` に照合します。大文字、短い値、空文字、その他の文字は不正です。
- 実行時には `--if-owner-id` との片方だけを指定できません。片方のみの場合は `restart requires both reviewed owner and instance IDs` で失敗します。
- `--plan` と `--if-instance-id` は併用できません。plan 呼び出しには実行前提条件を含められず、指定すると `restart plan cannot include execution preconditions` で失敗します。

## 実行時の動作

1. parser は `strata runtime restart` の専用 parser にこの option を登録します。CLI は値を `management.runtime_action` に渡します。
2. 管理層で ID の形式を検証し、実行時には status から取得した owner ID と instance ID の両方が指定値に一致するか確認します。不一致なら `owner_changed_after_restart_plan` または `instance_changed_after_restart_plan` を返し、exit code 6 で終了します。
3. 照合後、期待 instance ID は owner プロセスへの restart 要求にも渡されます。owner は restart 前の status を確認し、candidate の preflight を行った後、drain 直前にも instance ID と ready 状態を再確認します。途中で instance が変わった場合も restart を行いません。
4. 事前条件が通れば、option 自体が停止を行うのではなく、`runtime restart` の通常処理が server を停止し、候補設定で起動します。新 instance の起動に失敗した場合は、旧設定で rollback 起動を試みます。

`--if-instance-id` を省略した場合は instance ID によるこの事前条件チェックは行われません。`--if-owner-id` を単独で使うこともできません。

## 適用条件と副作用

- instance ID は同じ profile の `strata runtime restart --plan` が返す `current_instance_id` を使います。`--plan` は状態を比較するだけで、restart のための ID 表示を含みます。
- この条件は現在動作中の instance に対して適用されます。profile の候補 revision や run-config 内容を固定する条件ではありません。これらも固定する場合は `--if-profile-revision` や `--if-source-sha256` を別途指定します。
- 条件に一致した後の restart は現行 server を停止する副作用があります。新 instance の起動に失敗しても旧設定で rollback する処理がありますが、その rollback も失敗した場合は `state: failed`、`rolled_back: false` となります。

## 出力とエラー

- 成功・失敗の詳細は `--output human`（既定）では profile、state、instance、URL、error 等を含む行として表示され、`--output json` では構造化結果として出力されます。
- instance ID の形式不正や owner ID との片方指定、plan との併用不可などの引数・前提条件エラーは、restart 実行前に拒否されます。
- plan 後の owner / instance 変更や restart 中の instance 変更は exit code 6 です。restart 自体の停止失敗、起動失敗、rollback 結果も管理層の結果に含まれます。

## 根拠

- `strata_cli/cli.py:238-254` — `runtime restart` parser と `--if-instance-id` の宣言、値名、help。
- `strata_cli/cli.py:1345-1373` — parser 値の管理層への引き渡し、human / JSON 出力、終了コード。
- `strata_control/management.py:142-147` — 32 桁小文字 hex の identity 検証。
- `strata_control/management.py:292-333` — restart の plan 制約、owner ID との併用条件、現行 status 比較、journal と runtime への値の転送。
- `strata_control/runtime.py:702-731` — restart RPC の引数検証と owner への転送。
- `strata_control/runtime.py:1043-1073` — owner 側の restart 前・drain 前の instance 照合と状態確認。
- `strata_control/runtime.py:1085-1130` — stop、再起動、失敗時の rollback と結果。
- `strata_control/runtime.py:1132-1164` — `--plan` が表示する `current_owner_id` / `current_instance_id` と restart 予定情報。
- 索引 `docs/cli/README.md:451-468` — `strata runtime restart` のコマンド階層と作成対象リンク。

調査は上記 commit の checkout ソースを対象としました。Release 配布物との照合は行っていません。
