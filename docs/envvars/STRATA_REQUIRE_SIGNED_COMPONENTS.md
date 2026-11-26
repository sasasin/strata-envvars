# `STRATA_REQUIRE_SIGNED_COMPONENTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Terminal 側のコンポーネント検査で、署名のないパッケージと、署名付きでもこのビルドで検証できないパッケージを受け入れるかを制御する。対象は `terminal/strata_control/engine_component.py` の `verify_signature()` で、Strata エンジンとモデル形状用エンジンのコンポーネント選択・起動検査に使われる。署名が存在し検証器が利用可能な場合は、変数の値にかかわらず署名を検証し、不正な署名を拒否する。`terminal/strata_control/updater.py` の取得・オフライン導入ではこの環境値をそのまま採用せず、検証時に必ず `"1"` を渡すため、未署名・検証不能パッケージは常に拒否される（`terminal/strata_control/engine_component.py:386-413,1265-1267`, `terminal/strata_control/updater.py:842-851,1687-1696`）。

## 値と判定

`verify_signature(component, environ=None)` は、`environ` が省略された場合 `os.environ` を使い、キーがなければ空文字を既定値として取得する。値の前後の空白を除去してから小文字化し、結果が `1`、`true`、`yes`、`on` のいずれかと完全一致するときだけ署名必須とする。数値変換ではなく文字列比較であり、大文字小文字は区別しない。設定後に環境値を読み直すたびに判定し、値を関数内に保存する cache はない（`terminal/strata_control/engine_component.py:386-390`）。

| 条件 | 未設定 | 有効になる値の例 | 無効になる値の例 |
| --- | --- | --- | --- |
| 通常のコンポーネント検査（`environ` 省略） | 空文字扱い、署名必須ではない | `1`, ` TRUE `, `yes`, `On` | 空文字, `0`, `false`, `0anything`, `truex`, `y`, `2` |
| updater の取得・導入検査 | この環境変数の値によらず署名必須 | updater が渡す `"1"` | 該当なし（呼び出し時に値を上書き） |
| `tools/docker/fetch-engines.py` のパッケージ確認 | この環境変数の値によらず署名必須 | 呼び出し側が渡す `"1"` | 該当なし（呼び出し時に値を上書き） |

値が有効な場合、署名なしなら `the package is not signed and this PC requires signed components`、署名付きだが検証器が得られない場合は `the package is signed but this build cannot check signatures yet` という `IntegrityProblem` を送出する。署名付きで検証器があれば通常どおり検証し、検証失敗は値が無効でも拒否する（`terminal/strata_control/engine_component.py:391-412`）。

## 有効になる条件

- `engine_component.resolve()` が環境を明示して `verify_signature()` を呼ばない場合に、現在のプロセス環境が使われる。適合するインストール済みパッケージの署名を確認し、設定が有効なら未署名・検証不能をその候補の失敗理由にする（`terminal/strata_control/engine_component.py:1209-1215,1235-1269`）。
- 起動時に run config が `component:` 参照を指定すると `expand()` がコンポーネントを解決する。通常エンジンとモデル形状用エンジンの双方がこの resolver を使う（`terminal/strata_control/engine_component.py:1319-1337`）。実行開始前の preflight も同じ参照を展開し、`EngineMissing` を起動エラーにする（`terminal/strata_control/runtime.py:511-527`）。
- `strata components add-build` が登録するローカルビルドには署名がなく、登録時はファイル整合性を確認するだけで署名検査を呼ばない。そのビルドはこの設定が有効な状態で後から選択・起動しようとすると拒否される（`terminal/strata_control/local_engine.py:127-173`, `terminal/strata_control/engine_component.py:1265-1276`）。
- この判定に OS、GPU backend、build macro、サーバーモード、CLI オプション、モデル状態による分岐はない。これらは resolver が候補コンポーネントを選ぶ条件にはなり得るが、署名必須の値規則は変えない。
- updater のダウンロード後の導入確認とローカルアーカイブ導入では、`ctx.environ` の内容をコピーした辞書に対象キーを `"1"` で上書きして渡す。したがって `"0"` や未設定を含む利用者環境の値で弱められない（`terminal/strata_control/updater.py:842-851,1687-1696`）。Docker 用 `fetch-engines.py` も明示的に `{ec.ENV_REQUIRE_SIGNED: "1"}` を渡す（`tools/docker/fetch-engines.py:109-118`）。
- CLI 引数や設定ファイルからこの値を上書きする処理は、確認した読み取り・呼び出し経路にはない。更新時の上書きは updater 内の固定値である。

## 実行時の詳細

環境値は `verify_signature()` の呼び出しごとに読み、変数自体の値は cache しない。署名検証器 `_verifier` は別のプロセス内状態で、署名付きコンポーネントに対して未登録なら `signing.ensure_component_verifier()` を呼ぶ。署名がなく署名必須でもない場合は検証器の確保を行わず `"unsigned"` を返す。署名付きで verifier がない場合、署名必須なら拒否し、そうでなければ `"unverified"` を返す。verifier があれば署名を検査し `"verified"` を返す（`terminal/strata_control/engine_component.py:391-413`）。

起動時の resolver は、OS・backend・runtime・GPU 世代・driver に適合する候補に対して署名確認とファイル検査を行う。不適合候補は署名検査まで進まず、候補の確認に失敗した場合は理由に加える。適合候補がすべて integrity check に失敗すると `EngineIntegrityError` になり、そのパッケージを起動しない（`terminal/strata_control/engine_component.py:1235-1277`）。`EngineIntegrityError` は exit code 5 の `EngineMissing` 系であり、エラー文には `The engine package failed its integrity check, so it was not started:` と修復案が含まれる（`terminal/strata_control/engine_component.py:70-105`）。

## ログと測定値

この変数単独で出す警告ログは確認できない。拒否時は上記の `IntegrityProblem` の理由が resolver のエラーに含まれ、起動 preflight では `ProfileError` に変換されて exit code 5 で起動を止める（`terminal/strata_control/engine_component.py:1265-1277`, `terminal/strata_control/runtime.py:524-527`）。updater の取得検査では `the package failed its check: ...` を含む `UpdateError`（exit code 5）、オフライン導入では `this file did not pass the security check, so it was not used (...)` を含む `UpdateError`（exit code 5）になる（`terminal/strata_control/updater.py:846-849,1691-1694`）。測定値は該当しない。

## 根拠

- `terminal/strata_control/engine_component.py:55-62,386-413` — 変数名、値の取得・判定、署名の分岐。
- `terminal/strata_control/engine_component.py:1209-1215,1235-1290,1319-1337` — 候補解決と起動参照での適用、拒否の伝播。
- `terminal/strata_control/engine_component.py:70-105` — integrity error の文言と exit code。
- `terminal/strata_control/runtime.py:511-527` — 起動前 preflight とエラー変換。
- `terminal/strata_control/updater.py:816-851,1660-1696` — ダウンロード・オフライン導入での署名必須の上書きと失敗。
- `tools/docker/fetch-engines.py:109-118` — Docker 用取得ツールでの固定値。
- `terminal/strata_control/engine_library.py:231-254,296-312` — エンジン切替時にも通常環境で署名検査する経路。
