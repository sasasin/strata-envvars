# `strata ops result` の `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`  
調査日: 2026-10-25

## 概要

`strata ops result OPERATION_ID --profile PROFILE --json` は、指定した保存 profile の operation journal から記録を読み、機械処理向けの JSON 1行を標準出力へ出します。`ops result` は記録を読むだけで、operation を再実行・変更しません。索引上のスコープは `docs/cli/README.md` の `strata ops result` です。

## 値と既定値

- 値は取りません。parser は `store_true` の真偽値 option として登録します。省略時の値は `False` で、指定すると `True` になります。同じ parser 登録では `--output` の選択肢を `human` / `json`、既定値を `human` としています。(`strata_cli/cli.py` 255–267, 508–515行)
- `--json` は `ops` 配下の `result` を含む各 one-shot action parser に共通で追加されます。`strata ops result` 固有の引数は位置引数 `operation_id` と必須の `--profile` です。(`strata_cli/cli.py` 255–267, 508–515行)
- `main()` は `--json` が真なら `a.output = "json"` に設定します。したがって `--json` と `--output json` は同じ JSON 分岐を使います。両方を指定した場合も JSON です。`--json` を指定しつつ `--output human` と書いても、後段の正規化が JSON を選びます。値を伴う `--json=true` の形式は parser が受理しません。(`strata_cli/cli.py` 2217–2236行)

## 出力と処理

`--json` が有効な場合、CLI は `journal.load(profile, operation_id)` の戻り値を `record` に格納し、`{"schema_version":1,"ok":true,"record":...}` の JSON を出力して終了コード `0` を返します。JSON は `ensure_ascii=False`、`allow_nan=False` でシリアライズされます。(`strata_cli/cli.py` 1391–1411, 535–542行)

operation ID は小文字16進数32文字でなければなりません。不適合なら journal は `ProfileError` を送出します。読み込み先は profile の operation journal で、既定の profile ディレクトリは POSIX では `$XDG_CONFIG_HOME/strata/profiles`（未設定時は `~/.config/strata/profiles`）、Windows では `%APPDATA%/Strata/profiles`（未設定時はユーザーディレクトリ配下）です。`STRATA_PROFILE_DIR` が設定されていればそちらが使われます。profile は小文字英字で始まり、小文字英数字・`_`・`-` のみからなる最大64文字で、保存済み profile として読み込み可能である必要があります。(`strata_control/journal.py` 27, 47–63, 247–251行; `strata_control/profiles.py` 25, 30–50行; `strata_control/recipes.py` 32–51行)

記録が `running` 状態なら、journal は保存内容に `completion_unverified: true` を加えて返します。これは呼び出し元の中断後などに完了状態を確認できないという印で、operation が現在も実行中、または安全に停止済みであることを示すものではありません。完了済みなら保存記録をそのまま返します。(`strata_control/journal.py` 247–251, 1–5行)

この option 自体による書き込み・operation の実行はありません。`journal.load()` は指定パスを読み、record の形、サイズ（64 KiB 以下）、schema、profile、ID、状態、intent、events、result を検証します。POSIX では record と journal directory の owner-only 権限も検証します。(`strata_control/journal.py` 25–27, 47–57, 185–244, 247–251行)

## 失敗経路と相互作用

- operation ID が不正な場合、profile が見つからない場合、記録が存在しない場合、読み込み不能・形式不正の場合は失敗します。`journal.load()` 由来の `ProfileError` は `ValueError` として CLI の共通処理に入り、JSON モードでは標準出力に `{"schema_version":1,"ok":false,"error":{"code":N,"message":"..."}}` を出します。ID/profile の入力検証エラーは通常終了コード `2`、記録不在・破損などの journal エラーはソースで `5` と定義されています。(`strata_control/journal.py` 60–63, 185–217, 247–251行; `strata_control/profiles.py` 30–35行; `strata_cli/cli.py` 527–532, 2166–2173行)
- `--quiet` も one-shot parser に追加されますが、JSON/JSONL 出力時は quiet 用の stdout 抑制処理を通らないため、`--json --quiet` でも JSON は出力されます。(`strata_cli/cli.py` 508–515, 2232–2248行)
- `--json` のスキーマ・JSON 化以外に、`ops result` の記録内容や検索条件を変える処理はありません。`--profile` と `OPERATION_ID` は別途必須です。(`strata_cli/cli.py` 262–267, 1409–1411行)

調査範囲はこの checkout の Python Terminal CLI とローカル journal 実装です。異なる revision の配布バイナリや Windows ACL の実機挙動は確認していません。索引が案内する補助的な利用例は `docs/TERMINAL.md` 115, 122, 224行にありますが、上記の動作根拠は同一 checkout の parser と処理コードです。
