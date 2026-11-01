# `STRATA_UPDATE_TRUSTED_KEYS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の作業ツリーは `main...origin/main` で clean。外部ライブラリの環境変数の挙動は対象外。

## 役割

組み込みの `strata_control/update_keys.json` に登録された公開鍵に、追加の Ed25519 公開鍵を持つ JSON ファイルを加えます。主な用途はローカル feed やテスト用 feed の署名検証です。値はオン・オフ指定ではなくファイルパスです。追加鍵があれば feed と engine component の署名検証に使われます。

この名前は `signing.ENV_EXTRA_KEYS` として定義され、`load_trusted_keys()` が `os.environ.get()` 経由で値を読むため、候補一覧にあるだけの語ではなく Strata が実際に読む環境変数です。直接の読み取りと鍵読込: `strata_control/signing.py:31,194-216`。

## 値と判定

値は変換・正規化されず、真偽値として parse されません。空白の trim、大小文字変換、数値変換、範囲チェックもありません。`extra or environ.get(...)` のため、関数引数 `extra` に truthy な値を渡した場合は環境変数より優先し、空文字など falsy な値なら環境変数へ戻ります。通常の CLI 呼び出しは引数を渡さず環境変数を使います。

| 環境変数の状態 | Strata の扱い |
|---|---|
| 未設定 | 追加鍵ファイルを読まない。組み込み鍵は引き続き読み込む |
| 空文字 | `Path("")` としては扱われず、追加鍵なし。組み込み鍵だけを使う |
| 空白だけ、または他の非空文字列 | その文字列をパスとして使う。trim や真偽値判定はせず、該当パスを開く |
| 有効なパス | UTF-8-SIG で読み、JSON のルート配列、またはオブジェクトの `keys` 配列から公開鍵を追加 |
| 読めないパス、壊れた JSON、配列でない内容、不正な鍵 entry | `SignatureError`。無効な entry は読み飛ばさず、鍵ファイル全体の読込処理を失敗させる |

各 entry は `alg: "ed25519"`、32 byte 公開鍵の base64、公開鍵から計算した SHA-256 先頭 8 byte の hex と一致する `key_id` を必要とします。組み込み鍵と追加鍵は同じ辞書にまとめられ、辞書キーは `key_id` です。組み込みファイルが存在しない場合は組み込み鍵だけを読み飛ばしますが、指定された追加鍵ファイルを読めない場合はエラーになります。根拠: `strata_control/signing.py:184-216`。

## 有効になる条件

- `strata update` / `strata components update` は、acquisition の許可確認後に鍵を読み込み、その鍵で署名付き feed を検証します。`--feed` や `STRATA_UPDATE_FEED` は feed の場所を選びますが、信頼鍵ファイルのパスを上書きしません。`--check` も同じ鍵読込・feed 検証経路です。根拠: `strata_cli/update_cmd.py:97-106,229-245`。
- `strata components install-file` も `load_trusted_keys()` を呼び、engine component の署名検証に使います。root command と異なり、この経路では feed を読みません。根拠: `strata_cli/update_cmd.py:219-228`。
- テスト用の shell / PowerShell installer は、別変数 `STRATA_INSTALL_TEST_TRUST=1` のとき test feed から `test-trust.json` を取得し、この変数にそのファイルパスを設定して `strata update --check` を実行します。通常 installer でこの override を設定する分岐はありません。根拠: `packaging/install.sh:112-119`, `packaging/install.ps1:104-112`; ローカル feed 作成側は公開鍵ファイルの利用方法を表示します (`packaging/make_local_feed.py:116-118`)。
- DSV4.1 engine の install / upgrade は feed 用に同じ鍵を読みます。自動 upgrade は DeepSeek モデルで既存の同梱 `engine-dsv41` を使う場合に呼ばれ、`STRATA_DSV41_EXE` または `--dsv41-package` を選んだ場合や、feed に接続できない場合などはその経路を通りません。根拠: `strata_cli/launch/runner.py:2153-2190`, `strata_control/dsv41_engine.py:142-182,227-288`。
- engine component の一般的な署名検証では、署名付き component の初回検証時に verifier が未登録なら `ensure_component_verifier()` が鍵を読み込みます。呼び出し後の verifier は module 内に登録され、以後そのプロセスでは同じ verifier を再使用します。更新 CLI はロード済み `ctx.trusted` から verifier を登録する経路もあります。根拠: `strata_control/engine_component.py:348-375`, `strata_control/signing.py:248-272`, `strata_control/updater.py:690-692,1191-1193`。
- CUDA 12 driver floor の補助取得でも、呼び出し元が feed source を渡した場合に helper thread が鍵を読みます。feed 不在、鍵エラー、その他の例外はこの補助値の取得では `None` になります。根拠: `strata_control/driver_floor.py:64-93`。

値を読む処理自体には OS、GPU backend、build macro、モデル状態による条件分岐はありません。どの署名検証経路まで進むかは上記の CLI / launch 条件に依存します。外部の暗号ライブラリや driver の環境変数としては使われていません。

## 実行時の詳細

`load_trusted_keys()` は呼び出されるたびに `os.environ`（または明示された mapping）から値を取得し、鍵ファイルを読み直します。通常の updater は `strata update` 実行時に一度ロードして `ctx.trusted` に保持し、その context を使って feed を検証します。読み込み後に環境変数を書き換えても、その context の鍵辞書には反映されません。プロセス起動時の一律読み込みではありません。

一方 `extra_keys_in_effect()` は値が非空かどうかだけを `bool(environ.get(...))` で判定します。通常 CLI の人間向け出力では、非空なら stderr に `note: trusting the extra keys in <path> (a test setup)` を出します。`--output json` / `jsonl` ではこの注記を出しません。`--check` の JSON 報告では `trusted_by` が `test key file` または `built-in keys` になります。根拠: `strata_control/signing.py:219-221`, `strata_cli/update_cmd.py:183-192,229-240`, `strata_control/updater.py:631-639`。

追加鍵ファイルの読込失敗は通常 CLI では `SignatureError` として捕捉され、stderr（または機械出力の JSON error）へ表示されて終了コード 5 になります。鍵辞書が空なら feed の取得前に `FeedError` となり、「this build trusts no update key ... so no update can be verified; nothing was downloaded」と報告します。署名不一致や未知の key id も feed を信頼しないエラーとなり、feed を受け入れません。根拠: `strata_cli/update_cmd.py:187-192,257-262`, `strata_control/feed.py:335-362,376-396`。

通常の launch による DSV4.1 自動更新では、feed を読めない場合は静かに現在の engine を使い続け、鍵や署名などの検証失敗時は理由を示して更新を見送ります。追加鍵ファイルのパスが壊れていても launch 全体は止めず、外側の例外処理も現在の engine を返します。根拠: `strata_cli/launch/runner.py:2171-2190`, `strata_control/dsv41_engine.py:245-258,278-290`。

## 根拠

- `strata_control/signing.py:31,194-221` — 変数名、ファイルパスとしての読み込み、追加鍵の解析、非空判定。
- `strata_control/signing.py:184-216` — JSON 形式、鍵 entry の検証、読み込みエラー。
- `strata_cli/update_cmd.py:219-245,257-264` — CLI からのロード、注記、feed 更新・失敗終了。
- `strata_control/feed.py:335-362,376-396` — feed の鍵検証と無効・鍵なし時の拒否。
- `strata_control/engine_component.py:348-375`, `strata_control/signing.py:248-272` — component 検証の遅延ロードと verifier 登録。
- `strata_cli/launch/runner.py:2153-2190`, `strata_control/dsv41_engine.py:142-182,227-290` — DSV4.1 自動更新の適用範囲と失敗時の継続。
- `strata_control/driver_floor.py:64-93` — 補助的な feed 読込経路。
- `packaging/UPDATES.md:65-74,119-123` — 文書上の説明も、追加鍵ファイルを test/local feed 用とし、feed 署名検証に使う点で実装と一致。
