# `STRATA_INKLING_BUDGET_CAP`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（2026-11-26 時点）。

## 役割

Inkling-2-Mini を serve するサーバーで、Claude Code が `/v1/messages` に送る既定の thinking budget（`thinking.budget_tokens` がちょうど 31,999）を、そのリクエストの推論レベルの既定値まで引き下げるかどうかを決める。既定は引き下げる（cap 有効）。無効にすると 31,999 がそのまま使われる。判定は `Service.__init__` の `self.inkling_budget_cap`（`terminal/serve/server.py:4298`）と `Service.reasoning_budget` の分岐（`terminal/serve/server.py:4760-4770`）だけにある。

cap が効かないとき、サンプリング・prompt・生成される token の内容は変わらない。cap が効いたときも変わるのは thinking の打ち切り位置だけで、リクエストの他フィールドは書き換えない。

## 値と判定

読み取りは `os.environ.get("STRATA_INKLING_BUDGET_CAP", "").strip().lower() not in ("0", "false", "no", "off")`（`terminal/serve/server.py:4298`）。設定の有無ではなく、前後空白を除いて小文字化した**文字列全体**を 4 語と比較する。数値としては読まず、`atoi` も使わない。結果は真偽値 1 個。

| 値 | `inkling_budget_cap` | 意味 |
|---|---|---|
| 未設定 | `True` | cap 有効（既定） |
| `""`（空文字） | `True` | 未設定と同じ |
| `0` / `false` / `no` / `off` | `False` | cap 無効 |
| `FALSE` / ` 0 ` / `Off` | `False` | `strip().lower()` の後に一致 |
| `1` / `true` / `yes` / `on` | `True` | 有効 |
| `00` / `off2` / `noo` / `2` | `True` | 4 語と完全一致しないため有効 |

したがって無効化するのは 4 語の完全一致だけで、`STRATA_INKLING_BUDGET_CAP=`（空）や未知の文字列は「有効」に倒れる。この点は `STRATA_TOOL_MARKUP_RETRY` のような「既定 `1`、`0`/`off` 系で無効」という同型の判定と同じ形だが、既定文字列が空であるため未設定が有効になる。

run config に `inkling_budget_cap` がある場合は環境より優先される（`terminal/serve/server.py:9716-9719`、`Service` 生成後の上書き）。`true`/`false` 以外の型は起動時に `SystemExit` になる。

## 有効になる条件

値が有効（`True`）でも、次をすべて満たすリクエストだけが引き下げられる。

- エンジンが Inkling-2-Mini。`Service.inkling` は `engine.inkling_engine is True` から決まる（`terminal/serve/server.py:4406`）。他ファミリーや `MockEngine`（`--script` 等）では `False` になり、cap は評価されない。
- Anthropic `/v1/messages` 経由のリクエスト。`anthropic_to_messages` が `thinking.budget_tokens` を `reasoning_budget_tokens` へ写すとき、値が `CLIENT_DEFAULT_THINKING_BUDGET`（31,999、`terminal/serve/frontend.py:227`）と等しく、リクエスト自身の `reasoning_budget_tokens` が無い場合にだけ `strata_default_thinking_budget=True` を立てる（`terminal/serve/frontend.py:939-943`）。OpenAI Chat Completions / Responses 経路はこの印を立てないため、同じ 31,999 を送っても対象外（`terminal/serve/server.py:4760`）。
- 値が 31,999 ちょうど。`int` かつ `bool` でなく `> 0` が条件なので、`31999.0`（float）や `31998`、`32000`、`20000` は印が付かず対象外。
- 引き下げ先の既定値が 0 でないこと。`cap` が 0 のときは `if cap and value > cap` が成立せず、そのまま通る（`terminal/serve/server.py:4765`）。
- リクエストの値が cap より大きいこと。等しいか小さい場合は何も起きない。

cap の値は `Service.inkling_default_budget`（`terminal/serve/server.py:4726-4738`）が返す。優先順位は次のとおり。

1. `STRATA_INKLING_THINKING_BUDGET`、または run config の `inkling_thinking_budget`（全レベル共通の 1 値、`0` は既定なし）
2. リクエストのレベル `strata_effort` に対応する `INKLING_BUDGET_BY_EFFORT`（`terminal/serve/server_parts/base.py:107`）: `none`/`minimal` 1,024、`low` 2,048、`medium` 4,096、`high` 8,192、`xhigh`/`max` 16,384
3. レベル不明時は `low` の 2,048

31,999 は `budget_effort` により `high` に対応する（`terminal/serve/frontend.py:230-237`）ので、通常は 8,192 まで下がる。`strata_effort` は `Service.prepare` が kwargs から設定する（`terminal/serve/server.py:5845-5848`）。

run config の `reasoning_budget_tokens`（既定の budget）は cap の対象外で、`reasoning_budget` がリクエストに値が無いときだけ読む（`terminal/serve/server.py:4751-4755`）。`inkling_budget_cap` は `runconfig.EDITABLE` に含まれないため Settings 画面の `POST /config` では変更できず、ファイルを直して次回起動するしかない（`terminal/serve/runconfig.py:21-43`）。

## 実行時の詳細

読み取りは `Service.__init__` の 1 回だけ（`terminal/serve/server.py:4298`）。`Service` は起動時に 1 個作られ（`terminal/serve/server.py:9675`）、その後 run config の値で上書きされる（`9716-9719`）。起動後に `os.environ` を変更しても反映されず、エンジンの `restart()` でも `Service` は作り直されない。子プロセスには `child_env` が `os.environ` をコピーするため同名の環境変数がエンジンにも渡る（`terminal/serve/server.py:4110`）が、Strata のエンジン側にこの名前を読む箇所は無い。

判定はリクエストごとに `reasoning_budget` 内で行われる。`announce=True` で呼ぶのは `run()` の 1 箇所だけ（`terminal/serve/server.py:6038`）で、そこでは `prepare` 済みの `sampling`（`strata_effort` と印を含む）が渡る。事前検証の呼び出し（`terminal/serve/server.py:8395`、`8631`、`8697`）は `announce` を省くため、400 判定だけを行いログも出さない。引き下げは `value = cap` の代入のみで、その後の `max_tokens` との兼ね合い（`terminal/serve/server.py:6050-6058`）や wrap-up は通常の budget と同じ経路を通る。

## ログと測定値

cap が実際に値を下げた最初の 1 回だけ、stdout に次を出す（`terminal/serve/server.py:4766-4769`）。

```
[strata] the client's default thinking budget of {value} tokens is held to {cap} for Inkling at this level (inkling_budget_cap false in the run config, or STRATA_INKLING_BUDGET_CAP=0, keeps the full budget)
```

出力は `inkling_budget_cap_said` でプロセス内 1 回に抑えられる（`terminal/serve/server.py:4299`、`4767`）。cap が無効、値が cap 以下、印の無いリクエスト、`announce=False` の検証呼び出しでは出ない。

`docs/DETAILS.md:538` と `docs/MODELS.md:331-335` は config 既定 `true`・31,999 → 8,192（`high`）・無効化は config `false` か `STRATA_INKLING_BUDGET_CAP=0`・最初の 1 回だけログ、と説明しており、上記コードと一致する。資料に性能測定値の記載は無い。

## 根拠

- `terminal/serve/server.py:4298` — 環境変数の読み取りと真偽判定
- `terminal/serve/server.py:4726-4738` — cap になるレベル既定値の決定
- `terminal/serve/server.py:4760-4771` — 印・Inkling・cap 有効・値の大小の条件と代入
- `terminal/serve/frontend.py:227`、`939-943` — 31,999 の印付け（Anthropic 経路のみ）
- `terminal/serve/server.py:9716-9719` — run config による上書きと型検査
- `terminal/serve/server.py:4406` — `Service.inkling` の決定
- `terminal/serve/server_parts/base.py:107` — レベル別既定 budget
- `terminal/serve/server.py:6038`、`6050-6058` — 実行時の呼び出しと budget の使用
