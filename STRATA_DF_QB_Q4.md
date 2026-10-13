# `STRATA_DF_QB_Q4`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

QSA 層の decode verification で、Q4_0 KV cache 使用時にもクエリ側を複数行まとめて処理する経路を許可します。既定では Q4_0 の場合にこのバッチ経路を避け、トークンごとの処理になります。Q4_0 以外の KV 形式ではこの変数にかかわらず同経路の条件判定が進みます。

この変数は計測・診断ログ用ではなく、`Verifier` の QSA 層における実際の計算経路を切り替えます。実装上の読み取りは `src/core/verify.cpp` の1箇所です。

## 値と判定

`std::getenv()` が返す文字列に `std::atoi()` を適用し、結果が0以外なら opt-in とします（`src/core/verify.cpp:1219-1222`）。

| 設定 | `qb_q4` |
|---|---:|
| unset | false |
| 空文字、数値変換できない文字列、数値部分が0 | false |
| 数値部分が0以外（例: `1`, `-1`, `1suffix`） | true |

文字列全体の一致や値域の検証はありません。`atoi` のため、先頭の空白と符号は整数変換の規則に従い、数字の後ろにある文字列は判定に使われません。数値として範囲外の文字列に対する挙動は、この実装から保証できません。

## 有効になる条件

`qb_q4` が true でも、実際にバッチ処理する `qb` は次のすべてを満たす必要があります（`src/core/verify.cpp:1223`）。

- `STRATA_DEC_BATCH` が有効。これは別の関数内 static 値で、未設定なら有効、設定時は `atoi(value) != 0` です（同 `:845`）。
- 対象 window の行数 `n` が1より大きい。
- native QSA と native RoPE が有効。
- Q4_0 KV cache でないか、`STRATA_DF_QB_Q4` の変換結果が0以外。

そのため、単一行 window、native kernel が無効な構成、または `STRATA_DEC_BATCH=0` では、この変数を設定しても効果はありません。Q4_0 以外では `(!st.kv_q4 || qb_q4)` が常に true となるため、本変数は追加の制約になりません。

## 実行時の詳細

環境値は `verify.cpp` の QSA 層処理に入った際に関数内 `static const bool` として初回評価されます。同じプロセスで後から環境を書き換えても再評価されません。別プロセスへの転送・上書き処理は、この変数について確認できません。

`qb` が true の場合、indexer key の GEMV、K/V の norm・RoPE、query の GEMV と norm・RoPE などを複数行向けの関数で処理し、QSA attention の batched decode へ渡します（`src/core/verify.cpp:1230-1248,1325-1393`）。`qb` が false の場合、これらの query/indexer 計算はトークン単位のループを通ります（同 `:1241-1243,1328-1364`）。Q4_0 cache の追加条件がある理由として、実装コメントは query の回転を含む per-token 処理と、行単位で実行する batched path を挙げています（同 `:1217-1218`）。

KV の append 自体は別条件 `dec_batch && !g_no_batch_kv && !batch_rec_` によって batched append され、`STRATA_DF_QB_Q4` の値では直接切り替わりません（同 `:1265-1309`）。この変数を使った際の出力同一性や性能値は、対象ソース・参照資料からは確認できません。

## 根拠

- `src/core/verify.cpp:1217-1223` — opt-in の読み取り、`atoi` 判定、Q4_0 と batched query の条件。
- `src/core/verify.cpp:1230-1248,1325-1404` — バッチ／逐次の query 計算と後続 attention 処理。
- `src/core/verify.cpp:1265-1309` — 環境変数とは独立した KV append 分岐。
- `docs/DETAILS.md` — `STRATA_DF_QB_Q4` の説明・測定は確認できませんでした。
