# `STRATA_REQUIRE_SIGNED_COMPONENTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata Control が engine component の manifest 署名検証で、署名なし・検証不能の package を許すかを制御します。主にインストール済み engine component の解決時に、署名なしを許さず `IntegrityProblem` にするための設定です。GPU engine 自身が読む変数ではありません。

更新でダウンロードした package、ユーザーが選んだ package、および DeepSeek engine package の導入では、呼び出し側がこの値を `"1"` に上書きして `verify_signature()` に渡すため、プロセス環境での設定値にかかわらず署名が必須です。

## 値と判定

`strata_control/engine_component.py` の `verify_signature()` は、明示された `environ` がなければ呼び出し時点の `os.environ` を使い、値に `.strip().lower()` を適用して文字列全体を `("1", "true", "yes", "on")` と照合します（`strata_control/engine_component.py:348-356`）。

| 入力値 | 署名必須 | 判定 |
|---|---:|---|
| 未設定 | いいえ | 空文字列を既定値にして判定 |
| 空文字列または空白だけ | いいえ | `.strip()` 後に空文字列 |
| `1`, `true`, `yes`, `on` | はい | 大文字小文字を問わず、前後の空白を除いた全体一致 |
| 上記以外（例: `0`, `false`, `2`, `true-more`） | いいえ | truthy/falsy 変換や数値変換はしない |

したがって、値が無効な文字列でもエラーにはならず、署名を必須にしない側へ進みます。パッケージに署名があれば、必須設定の有無にかかわらず、登録済み verifier がある場合は検証されます（同 `:353-375`）。

## 有効になる条件

- 通常の component 解決では、`resolve()` が対象 PC に適合する package を検査するとき `verify_signature(item)` を呼び、既定の `os.environ` を使用します。バックエンド、platform、GPU architecture、driver、runtime の条件で package をその検査より前に除外する場合は、その package について署名判定に進みません（`strata_control/engine_component.py:909-963`）。
- `strata update` の取得 package とローカル package 導入は `ctx.environ` をコピーした辞書に `STRATA_REQUIRE_SIGNED_COMPONENTS: "1"` を設定して検証します（`strata_control/updater.py:688-695,1189-1196`）。
- DeepSeek engine の手動導入も `os.environ` のコピーに `"1"` を設定し（`strata_control/dsv41_engine.py:113-120`）、`docker/fetch-engines.py` はこの変数だけを含む辞書で `"1"` を渡します（`docker/fetch-engines.py:86-95`）。

この判定に OS、GPU backend、build macro、CLI 引数による追加条件はありません。通常解決時の設定は呼び出しごとに評価され、環境値をプロセス内でキャッシュするコードはありません。明示的な `environ` が渡されたときはその辞書だけを参照します（`strata_control/engine_component.py:348-352`）。

## 実行時の詳細

署名がない package で必須判定が真なら、`IntegrityProblem("the package is not signed and this PC requires signed components")` を送出します。署名付きでも verifier が用意できず、信頼鍵の読み込み後も verifier がない場合は、必須時に `IntegrityProblem("the package is signed but this build cannot check signatures yet")` となります。信頼鍵を読めない場合や署名不一致も別の `IntegrityProblem` です（`strata_control/engine_component.py:353-375`）。

通常の `resolve()` はこの問題を package ごとの理由に加え、適合する package がすべて integrity check に失敗した場合は `EngineIntegrityError` として送出します。例外メッセージは「The engine package failed its integrity check, so it was not started: ...」で始まり、その engine は起動されません（`strata_control/engine_component.py:91-107,961-972`）。

更新経路では `UpdateError` に包まれ、取得 package は `the package failed its check: ...`、ローカル package は `this file did not pass the security check, so it was not used (...)` として拒否されます（`strata_control/updater.py:692-695,1193-1196`）。DeepSeek engine の手動導入は理由を `emit()` に出し、導入せず `None` を返します（`strata_control/dsv41_engine.py:116-120`）。Docker fetch は `SystemExit` にして `fetch-engines: <folder> failed its check: ...` を表示します（`docker/fetch-engines.py:89-92`）。

## 根拠

- `strata_control/engine_component.py:61,348-375` — 名前定数、環境値の取得・parse、未署名／未検証／署名不一致の処理。
- `strata_control/engine_component.py:909-986` — 通常の engine 解決時の署名検査と失敗の集約。
- `strata_control/updater.py:663-702,1162-1198` — 更新 package とローカル archive の検査で値を `"1"` に固定し、失敗時に拒否。
- `strata_control/dsv41_engine.py:74-122` — DeepSeek engine 手動導入で `"1"` を設定し、失敗時は導入しない。
- `docker/fetch-engines.py:74-95` — 同梱 fetch tool の検査で `"1"` を渡し、失敗時に終了。
- `packaging/ENGINE-COMPONENT.md:24-34` — package 検査の説明。ここでは `=1` と略記されていますが、実装は `1/true/yes/on`（前後空白除去・大文字小文字無視）を受け付けます。
