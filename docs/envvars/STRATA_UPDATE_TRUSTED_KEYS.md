# `STRATA_UPDATE_TRUSTED_KEYS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`strata_control/signing.py` の `load_trusted_keys()` が、同梱の `update_keys.json` に加えて信頼する公開鍵 JSON ファイルを指定する。値は鍵そのものや `1` のような有効化フラグではなく、追加鍵ファイルのパスである。読み込んだ鍵は更新 feed の署名検証と、署名付き engine component の検証に使われる。環境変数だけで署名検証を必須にはせず、署名検証が行われる経路に検証鍵を追加する（`terminal/strata_control/signing.py:194-216,248-259`）。

## 値と判定

`load_trusted_keys()` は、引数 `environ` が省略された場合は `os.environ` を参照し、`extra or environ.get("STRATA_UPDATE_TRUSTED_KEYS")` を鍵ファイルの候補として使う。環境変数の文字列全体をパスとして `Path` に渡す。真偽判定や数値・真偽値への変換、空白の trim、`~` の展開はしない（`terminal/strata_control/signing.py:194-205`）。

| 条件 | 判定・結果 | 例 |
|---|---|---|
| 未設定 | 追加ファイルなし。同梱鍵ファイルがあればその鍵を使う | unset |
| 空文字 | 空文字は `if not path` でスキップ。同梱鍵ファイルの読み込みは続く | `""` |
| 空でない値 | 指定されたパスの JSON を読み、同梱鍵に追加する | `"/tmp/trust.json"` |
| 内容が不正・読めない | `SignatureError`。同梱鍵だけで続行する fallback はしない | 存在しないパス、空白だけの文字列、壊れた JSON |
| 値が `0` / `1` / `true` / `false` / `0anything` | いずれも特別な意味はなく、その文字列をファイルパスとして扱う | `"1"` は `1` というパス |

追加鍵ファイルは UTF-8-SIG として読み、トップレベルが `{"keys": [...]}` のオブジェクト、または鍵エントリーの配列である必要がある。各エントリーは `alg` が `ed25519`、32 byte の公開鍵を表す Base64、公開鍵に対応する `key_id` を満たさなければならない。ファイルを読めない場合は `the key file <path> cannot be read (<例外型>)`、配列がない場合は `the key file <path> has no list of keys`、各鍵が不正なら該当理由の `SignatureError` となる（`terminal/strata_control/signing.py:184-215`）。

## 有効になる条件

- `update_keys.json` の鍵は常に先に読み込まれ、指定ファイルの鍵はその辞書に加えられる。同じ `key_id` が重複すれば後から読んだ鍵で辞書値が置き換わる（`terminal/strata_control/signing.py:32,199-216`）。
- `strata update` / `strata components update` の feed 確認・適用では、`load_trusted_keys()` の結果が feed 検証に渡される。`--feed` や `STRATA_UPDATE_FEED` は feed の場所を選び、信頼鍵の選択は別に行われる（`terminal/strata_cli/update_cmd.py:33-36,355-372`）。
- `strata components install-file` も同じ関数で鍵を読み込む（`terminal/strata_cli/update_cmd.py:345-354`）。
- モデル feed の取得、driver floor の feed 参照、engine update の feed check なども `load_trusted_keys()` を呼ぶ。鍵を使った取得に失敗しても、モデル一覧取得はキャッシュへ戻るか空の結果を返す場合があり、driver floor の取得失敗は `None` として扱われる（`terminal/strata_control/feed_models.py:110-137`; `terminal/strata_control/driver_floor.py:64-81`; `terminal/strata_control/engine_update.py:117-131,428-435`）。
- 署名付き engine component の検証時、verifier が未登録なら `ensure_component_verifier()` が同梱鍵とこの環境変数の追加鍵を読み、verifier を登録する。component が未署名ならこの変数による鍵読み込みは行われない。verifier 登録後は同じプロセスで再読込せず、環境変数の変更や追加ファイルの変更はその登録済み verifier に反映されない（`terminal/strata_control/engine_component.py:386-413`; `terminal/strata_control/signing.py:248-272`）。
- 同梱鍵も追加鍵も無く verifier を登録できない場合、component は「未検証」となり、`STRATA_REQUIRE_SIGNED_COMPONENTS` が有効なら `this build cannot check signatures yet` で拒否される。この別変数が無効なら署名を確認できない状態でも `unverified` として返る（`terminal/strata_control/signing.py:262-272`; `terminal/strata_control/engine_component.py:386-406`）。
- 通常の `strata update` ではコマンド実行中に鍵を読み込む。`load_trusted_keys()` 自体にキャッシュはないため、通常の各呼び出しでファイルを再読込する（`terminal/strata_cli/update_cmd.py:355-360`; `terminal/strata_control/signing.py:194-216`）。
- パッケージング用 `tools/packaging/feed_tool.py verify-feed` は `load_trusted_keys(a.pub, environ={})` と明示し、環境変数を見ず `--pub` 相当の引数から鍵ファイルを指定する（`tools/packaging/feed_tool.py:547-549`）。

## 実行時の詳細

通常の更新コマンドは `load_trusted_keys()` で鍵を読み、結果を `updater.Context.trusted` に渡して feed の確認・更新に使う（`terminal/strata_cli/update_cmd.py:355-372`）。

## ログと測定値

通常の更新コマンドは追加鍵が非空で、JSON/JSONL モードでない場合、stderr に `note: trusting the extra keys in <値> (a test setup)` を出す。この注記は設定の有無を示すもので、ファイルの有効性を保証しない（`terminal/strata_cli/update_cmd.py:355-360`）。

有効な鍵辞書が空の場合、feed の検証は `this build trusts no update key (update_keys.json is empty and STRATA_UPDATE_TRUSTED_KEYS is not set), so no update can be verified; nothing was downloaded` で失敗する。feed が追加鍵で信頼されない場合は署名検証理由を含む `the update feed is not trusted: ...` となる（`terminal/strata_control/feed.py:650-677,691-716`）。通常 CLI は `FeedError` を人間向け実行では `strata: <理由>` と stderr に出し、その exit code を返す。更新コマンドの署名エラーは exit code 5（`terminal/strata_cli/update_cmd.py:311-316,378-390`）。

追加鍵ファイルの読み込みエラーは `SignatureError` であり、通常の更新コマンドでは `strata: <理由>` と stderr に出て exit code 5 になる。署名付き engine component の検証で鍵ファイルを読めない場合は `this PC's update keys cannot be read (<理由>)` の `IntegrityProblem` に変換される（`terminal/strata_cli/update_cmd.py:385-386`; `terminal/strata_control/engine_component.py:395-413`; `terminal/strata_control/signing.py:206-215`）。

## 根拠

- `terminal/strata_control/signing.py:31-32,184-221` — 環境変数名、値の読み取り、追加鍵ファイルとエントリーの検証。
- `terminal/strata_control/signing.py:248-272` — component verifier 登録と登録後の再利用。
- `terminal/strata_control/feed.py:650-677,691-717` — feed 署名検証と鍵不足・不信頼時の失敗。
- `terminal/strata_cli/update_cmd.py:345-372,378-390` — CLI からの読み取り、注記、失敗の表示と終了コード。
- `terminal/strata_control/engine_component.py:386-413` — 署名付き component の検証時に verifier を初期化する経路。
- `terminal/strata_control/feed_models.py:110-137`, `terminal/strata_control/driver_floor.py:64-81`, `terminal/strata_control/engine_update.py:117-131,428-435` — その他の Strata 所有呼び出し元。
- `tools/packaging/feed_tool.py:547-549` — 環境変数を参照せず明示引数で鍵を渡す例外経路。
