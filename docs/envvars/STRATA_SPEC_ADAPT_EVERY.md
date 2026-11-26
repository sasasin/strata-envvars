# `STRATA_SPEC_ADAPT_EVERY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`--spec` が 2 以上の speculative decode で、adaptive VRAM expert tier が通常の会話に追いつくまでの warm-up 期間に、expert 入れ替えを何回の verify round ごとに行うかを指定する。通常間隔 `--adapt-every` より短い間隔にできる。`generate.cpp` はこの値を `adapt_warm_every` に保存し、warm-up 期間後は `adapt_every` に戻す。環境変数は適応 tier 自体を有効化せず、生成 token や draft 数も直接変更しない。実際の tier が動くには adaptive tier の有効条件も必要である（`engine/src/program/generate.cpp:1045-1051,5100-5109,22055-22060`）。

## 値と判定

直接の読み取りは speculative decode 設定時に一度行い、`std::getenv` の文字列を `std::atoi` で整数化する。文字列全体の検証や変換結果の範囲検査はしない。未設定は `0` 相当、空文字も `atoi("") == 0` となり採用されない。先頭の空白や符号は `atoi` の変換規則に従い、数値の後ろの文字列は検査されない。採用には整数 `n > 0` かつ現在の `adapt_every` より小さいことが必要。したがって既定値 `4` の状態なら `1`、`2`、`3` が候補で、`0`、負数、`4` 以上は無効。例えば `2junk` は `2` として扱われ、`0anything` は `0`、`true` は `0` となる（`engine/src/program/generate.cpp:1047-1051,5104-5109`）。

| 条件 | 未設定時 | 採用される値の例 | 採用されない値の例 |
|---|---|---|---|
| 通常。`--adapt-every` の明示なし、現在の既定間隔が 4 | `n=0`。warm interval は設定しない | `1`, `2`, `3`（ただし `STRATA_SPEC_ADAPT_WARM` が正数） | 空文字、`0`, `-1`, `4`, `true` |
| CUDA の同一 compute capability の可視 GPU が sm_86、`STRATA_SPEC_ADAPT_SM86` の先頭文字が `1`、`STRATA_SM86_PERF` が `0` で始まらない | 未設定なら `STRATA_SPEC_ADAPT_EVERY=2` をプロセス環境へ設定 | 未設定時の `2`、または利用者が設定した `1`（warm 回数が正数で、現在間隔より小さい場合） | 利用者が空文字や無効値を設定した場合、その設定が保持され `2` の補完はされない |

sm_86 の自動設定は環境変数の「未設定」を `getenv(...) == nullptr` で判定するため、空文字を含む何らかの設定があれば利用者設定を保持する。opt-in の `STRATA_SPEC_ADAPT_SM86` は先頭文字が `'1'` かだけを見ており、`1anything` でも通る。`STRATA_SM86_PERF` は共通 helper が先頭文字 `'0'` の場合に無効扱いする。デフォルト関数は `EVERY` と `WARM` を個別に補い、両方ともすでに設定されていれば上書きしない（`engine/src/core/nv_defaults.cpp:15-18,328-347`）。

`--adapt-every` をコマンドラインで指定すると `adapt_every_given` が立ち、環境変数は後段で読み取られない。CLI の値そのものは `atoi` で設定される。既定の `adapt_every` は `4`（Metal 以外）だが、適応カバレッジ規則などが後で interval を変更する経路もある（`engine/src/program/generate.cpp:1045-1051,4058,5104-5109,24563-24568`）。

## 有効になる条件

- speculative decode の `o.spec >= 2` であること。`--spec` 未指定時は通常 `0`（Metal build は `2`）である（`engine/src/program/generate.cpp:1010-1017,5104`）。
- 明示的な `--adapt-every` がないこと。指定された場合、この環境変数に基づく warm interval の設定ブロックを通らない（`engine/src/program/generate.cpp:1048,4058,5104`）。
- 整数化後の値が `0 < n < o.adapt_every`、かつ `STRATA_SPEC_ADAPT_WARM` を `std::atoll` で整数化した値 `wr` が正数であること。warm 回数側も未設定なら `0` で、warm interval は有効化されない（`engine/src/program/generate.cpp:5105-5109`）。
- warm-up 間隔を自動設定する CUDA 経路は、HIP と Metal 以外のビルドで、CUDA device count が取得でき、全可視 GPU の compute capability が同一の場合に限られる。sm_86 の場合でも `STRATA_SPEC_ADAPT_SM86` の先頭が `1` でなければ補完しない。混在 compute capability の複数 GPU はこの default 処理を通らない（`engine/src/program/generate.cpp:4421-4450`; `engine/src/core/nv_defaults.cpp:328-347`）。
- warm interval は adaptive tier の前提条件を代替しない。通常間隔が正で、swap 数も正、GPU expert cache に載らない expert があり、usage 情報が用意される経路でなければ tier は動かない（`engine/src/program/generate.cpp:24563-24570,22055-22060`）。
- `STRATA_ADAPT_MID` と expert cache coverage により `adapt_every` が後から `2` になる経路では、自動設定された `n=2` は実行時 interval と同じ値になるため、間隔を短縮しない。明示的な CLI interval は同規則による上書き対象外（`engine/src/program/generate.cpp:24563-24568`; `engine/src/program/generate.cpp:1048`）。

## 実行時の詳細

CUDA の sm_86 default 補完は GPU 構成判定後、generate の引数処理後に呼ばれる。その後、speculative decode 条件を調べる箇所で `EVERY` と `WARM` を読み、warm 用フィールドに保存する。環境を実行中に変更しても、この読み取り済みの値は再評価されない。sm_86 の補完は `setenv`（Windows は `_putenv_s`）でプロセス環境にも設定され、既存値は変更しない（`engine/src/program/generate.cpp:4421-4450,5104-5109`; `engine/src/core/nv_defaults.cpp:328-347`）。

warm 間隔は `adapt_iv(rounds)` が `rounds < adapt_warm_rounds` の間だけ返し、それ以降は通常の `adapt_every` を返す。speculative decode の適応処理は、`rounds % adapt_iv(rounds) == 0` かつ pending swap がないときに usage snapshot を取り、adaptive tier の処理 thread を開始する。これは verify round 単位の間隔であり、wall-clock 秒数ではない（`engine/src/program/generate.cpp:1049-1051,22055-22060`）。

## ログと測定値

この変数を読み取る箇所や sm_86 default の設定箇所は、それ自体についてログを出さず、無効値による終了・失敗経路もない。通常の generate 終了時には adaptive tier が動いた場合に stdout へ `adaptive tier` の集計行を出すが、表示する interval は `o.adapt_every`（通常間隔）であり warm interval を示さない。Strata の `docs/DETAILS.md` は adaptive tier の一般説明を掲載するものの、この環境変数名や warm-up 設定の詳細は記載していない（`engine/src/program/generate.cpp:25314-25316`; `docs/DETAILS.md:274-276`）。

## 根拠

- `engine/src/program/generate.cpp:1045-1051` — 通常間隔・warm interval・round 判定。
- `engine/src/program/generate.cpp:4058` — `--adapt-every` と明示指定フラグ。
- `engine/src/program/generate.cpp:4421-4450` — CUDA build と GPU 構成判定後の per-card default 呼び出し。
- `engine/src/program/generate.cpp:5100-5109` — speculative 条件、環境値の読み取りと採用条件。
- `engine/src/core/nv_defaults.cpp:15-18,328-347` — `STRATA_SM86_PERF` 判定、sm_86 opt-in および未設定値の補完。
- `engine/src/program/generate.cpp:22055-22060,24563-24570,25314-25316` — 適応処理の実行条件、coverage による interval 変更、終了時の集計行。
- `docs/DETAILS.md:274-276` — adaptive tier の一般説明。
