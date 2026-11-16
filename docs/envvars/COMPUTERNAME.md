# `COMPUTERNAME`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。調査対象リポジトリの作業状態は `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Strata Control の OS 情報 helper `strata_control.sysinfo.node()` が、Windows で `socket.gethostname()` に失敗した場合にコンピューター名を補うために読みます。これは通常の優先経路ではなく、例外時だけの fallback です。リポジトリ内では `sysinfo.node()` の呼び出し元を確認できなかったため、現行の Control / CLI の処理からこの fallback に到達する経路は見つかっていません（`strata_control/sysinfo.py:92-99`）。

別経路では、Web profile の DeepSeek Harness を起動するとき、ホスト環境から子プロセスへ渡す環境変数の allowlist に `COMPUTERNAME` が含まれます。Strata はその値を解釈せず、候補環境に存在すれば値をコピーします（`apps/host/server/agent/harness-runtime.mjs:20-36,75-83`）。

## 値と判定

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `sysinfo.node()` を Windows 上で呼び、`socket.gethostname()` が `OSError` を送出 | `""` | 設定値をそのまま返す（例: `DESKTOP-A`） | 値の形式による無効値はない。空文字も `""` を返す |
| それ以外（Windows で hostname 取得成功、または Windows 以外） | 参照しない | 該当なし | 該当なし |
| Harness 子プロセス環境の生成 | `externalEnvironment()` が選ぶ元環境にキーがなければ渡さない | キー名は大文字小文字を区別しない allowlist（例: `COMPUTERNAME`）に一致し、値があれば同じ値を渡す | `SECRET_NAME` の除外条件には一致しないため、値内容による無効判定はない。キーが元環境にない場合は渡さない |

Python 側は `os.environ.get("COMPUTERNAME", "")` で読むため、未設定と明示的な空文字はどちらも空文字になります。空白除去、大小文字変換、形式検査、数値変換、範囲制限はありません。CLI 引数や他の設定との優先順位はありません。hostname 取得が成功した場合はその結果が優先され、環境変数は読まれません（`strata_control/sysinfo.py:92-99`）。

Harness 側では `KEEP.test(k)` により名前を判定し、元の値を `out[k]` に代入します。正規表現に `i` フラグがあるため名前の大小文字は区別しません。`agentEnvironment()` の `extra` はコピー後に展開されるため、同じキーがあれば `extra` の値が優先します（`apps/host/server/agent/harness-runtime.mjs:20-36`）。AppImage 内では元環境の記録があればそれを選び、なければ AppImage 用の値を除去した環境を使います（`apps/host/server/external-env.mjs:28-40,43-70`）。

## 有効になる条件

- fallback 読み取りは `sys.platform.startswith("win")` が真で、`socket.gethostname()` が `OSError` を送出した場合に限ります。それ以外の例外型を捕捉するコードはありません（`strata_control/sysinfo.py:24-25,92-99`）。
- この関数を呼ぶリポジトリ内の呼び出し元は見つかりませんでした。したがって、上記は関数が呼ばれた場合の実装動作です。
- Harness への転送は `agentEnvironment()` を経由する Harness 起動で適用されます。候補環境のキーが allowlist に合致し、値が `undefined` でないことが条件です。追加環境 `extra` が同名キーを渡した場合はその値で上書きされます（`apps/host/server/agent/harness-runtime.mjs:25-36,75-83`）。
- CUDA / HIP / SYCL backend、GPU、build macro、モデル状態による条件はありません。

## 実行時の詳細

Python helper は `node()` 呼び出しごとに `socket.gethostname()` を実行し、`OSError` のときだけその場で `os.environ.get()` を評価します。環境値を static cache するコードはなく、呼び出し間の値変更を妨げる cache はありません。hostname 成功時や非 Windows では環境値を読みません（`strata_control/sysinfo.py:92-99`）。

Harness の環境は Harness 起動ごとに構築され、親プロセスの環境を `externalEnvironment()` で選び直してから allowlist で絞り、`spawn()` の `env` に渡されます。Strata 内で COMPUTERNAME の値を加工したり、別途ログへ記録したりする処理はありません（`apps/host/server/agent/harness-runtime.mjs:25-36,75-83`; `apps/host/server/external-env.mjs:63-71`）。

## ログと測定値

`COMPUTERNAME` の値や fallback の選択について、Strata 独自のログ、警告、終了・失敗処理はありません。`socket.gethostname()` の `OSError` は `node()` 内で捕捉され、環境値（未設定なら空文字）を返します（`strata_control/sysinfo.py:94-99`）。Harness への転送にもこの変数に関するログはありません。該当する測定値はありません。

## 根拠

- `strata_control/sysinfo.py:24-25,92-99` — Windows 判定、hostname 取得と例外時の `COMPUTERNAME` 読み取り。
- `apps/host/server/agent/harness-runtime.mjs:20-36,75-83` — allowlist、値のコピー、子プロセス環境としての利用。
- `apps/host/server/external-env.mjs:28-40,43-70` — AppImage 起動元環境の復元と、外部プロセス向け環境の選択。
- `docs/envvars/000_envvers.md:78` — 候補一覧への掲載。候補一覧のみでは実装根拠にしていません。
