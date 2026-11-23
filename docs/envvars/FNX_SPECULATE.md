# `FNX_SPECULATE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の split engine にある `fnx::Session` の逐次生成で、検証後の draft を次の複数行 window に持ち越すかを切り替える。未設定時は有効（既定値 `1`）。`0` では各 window を 1 行にし、MTP または DFlash2 の候補を次の検証に渡さない。通常の非 split engine にはこの変数の読み取り箇所がない。読み取りと状態の設定は `engine/src/split/src/session.cpp:140-146`、生成時の分岐は同 `:463-471, 565-619`。

ただし「draft 呼び出し自体が一切なくなる」わけではない。MTP 経路では `speculate == false` の分岐に達する前に `draft_one(...)` を一度呼び、その戻り値を後続 window に使わず消去する。DFlash2 経路は分岐が `df2_draft(...)` より前なので、無効時には DFlash2 の draft 呼び出しを行わない（同 `:565-599`）。

## 値と判定

`env_int("FNX_SPECULATE", 1)` は `std::getenv` で値を得て、`parse_whole` / `std::strtoll(..., 10)` で `long long` の整数全体として変換する。値が `0` なら無効、0 以外（負数を含む）なら有効。範囲制限や clamp はない。未設定だけが既定値 `1` になる。空文字、符号だけ、先頭・末尾の空白、数値の後ろに文字がある値、整数範囲外は parse error となる。10 進整数なので大文字小文字の規則は該当しない。根拠: `engine/src/split/src/session.cpp:142`、`engine/src/split/src/env.hpp:15-21, 33-40`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `Session` の逐次生成 | `1` として有効 | `1`, `-1`, `+2`, `00`（整数として 0 以外） | `0`, `-0`, `+0` |
| 同上、整数として不正 | 該当なし | 該当なし | 空文字、`true`, `0anything`, `1 `, ` 1`, `+`, `9223372036854775808` は無効値扱いではなく parse error |

## 有効になる条件

- split engine の `Session` が環境から値を読み、`Session::generate` を使う経路で適用される。sFNX サーバーの通常の `GEN` はこの経路を呼ぶ（`engine/src/split/tools/sfnx.cpp:806-815, 853-866`）。
- `--spec K` が指定されていても、値が `0` なら MTP / DFlash2 / lookup の候補を次の `Session` 検証 window に持ち越さない。`--draft mtp|dflash2` は候補の供給元を選ぶ設定であり、この変数の判定を上書きしない（`engine/src/split/tools/sfnx.cpp:67-114`、`engine/src/split/src/session.cpp:565-619`）。
- sFNX の複数 slot 一括生成で `BatchDecoder` が使われる経路は `Session::generate` を通らず、`FNX_SPECULATE` を参照しない。`BatchDecoder` の初期化・draft 計画には `FNX_SPECULATE` による抑止がない（`engine/src/split/tools/sfnx.cpp:451-458, 603-620, 659-680`、`engine/src/split/src/batch.cpp:65-87, 260-379`）。複数 slot サーバーでも単独 `GEN` は `Session::generate` を使う。`FNX_BATCH_DRAFTS=0` 等で一括 decoder がない場合の batch decode は `e.step` の 1 行経路であり、この変数による切り替えではない（`engine/src/split/tools/sfnx.cpp:701-732`）。
- 変数の読み取りは split engine の `session.cpp` にある。通常のレイヤー分割 engine や他の backend で同名環境変数が同じ効果を持つことは、このコードからは確認できない。split engine の対象構成と起動条件は `docs/SPLIT_ENGINE.md:1-5, 25-47, 67-75, 92-95` に記載されているが、環境変数の実行時判定自体は上記ソースの範囲に限る。

## 実行時の詳細

値は `Session` の構築時に一度読み、インスタンスの `speculate` bool に格納される。関数内 static cache ではない。既存インスタンスではプロセス実行中に環境を変えても反映されず、新たに構築された `Session` はその時点の環境値を読む（`engine/src/split/src/session.cpp:140-149`）。sFNX は server 構築時に slot 0 と設定済み slot の Session を作る（`engine/src/split/tools/sfnx.cpp:448-458`）。

`generate` は現在の `x` を含む行で `e_.verify(rows)` を行い、出力を commit する。`speculate == false` なら、次の window 用 draft 配列を空にしてループを続けるため、以後も `rows` は `x` の 1 行だけとなり、一度に受理・出力する token は 1 個になる（`engine/src/split/src/session.cpp:463-471, 486-527, 536-559, 565-619`）。通常の検証時の sampling 設定を変更する分岐はなく、ここから通常 engine との token 一致までは断定できない。

MTP では各 window の出力後に `draft_one` を呼んでから `!speculate` を調べるため、1 回の draft 計算と `draft_calls` の加算は残り、draft は次の window に使われない。DFlash2 では `!speculate` を先に調べるため、無効時には drafter 呼び出しを飛ばす。いずれも読み取り時の parse エラーを除いて、この変数専用の警告・理由ログ・fallback ログはない（同 `:439-451, 565-599`）。

## ログと測定値

有効・無効を示す専用ログはない。逐次 `GEN` の終了時には sFNX が `drafts <accepted> of <offered>` を stderr に出すため、候補を次の window に持ち越さない状態では通常 `drafts 0 of 0` となる。一方、MTP の単発 draft 呼び出し回数はこの要約に含まれない（`engine/src/split/tools/sfnx.cpp:860-866`、`engine/src/split/src/session.cpp:555-557, 596-599`）。

値が parse できないと `env_int` が `FNX_SPECULATE: '<値>' is not a whole number` を含む例外を投げる。sFNX の Session 初期化で捕捉されると stdout に `ERR <例外文>`、stderr に `sfnx: failed: <例外文>` を出し、終了コード 1 で終了する（`engine/src/split/src/env.hpp:33-40`、`engine/src/split/tools/sfnx.cpp:1097-1103, 1137-1167`）。

この変数単独の測定値は、参照したソースおよび `docs/DETAILS.md` に見当たらないため記載しない。

## 根拠

- `engine/src/split/src/env.hpp:15-21, 33-40` — 整数全体の parse、未設定時の既定値、不正値の例外。
- `engine/src/split/src/session.cpp:140-146, 463-471, 565-619` — 読み取り、Session 内の状態、逐次生成と MTP / DFlash2 の分岐。
- `engine/src/split/tools/sfnx.cpp:448-458, 806-866, 1097-1103, 1137-1167` — Session の生成・逐次要求・観測ログ・失敗時の終了。
- `engine/src/split/tools/sfnx.cpp:603-680, 701-732`、`engine/src/split/src/batch.cpp:65-87, 260-379` — batch decoder が別経路であること。
- `docs/SPLIT_ENGINE.md:83-85` — 文書上の説明は「one row a window, no drafts」。ただし現在の MTP 実装では単発の `draft_one` 呼び出しが残るため、上記のようにソースの実際の分岐を優先して記載した。
