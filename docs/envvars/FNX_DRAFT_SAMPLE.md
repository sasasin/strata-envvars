# `FNX_DRAFT_SAMPLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

温度サンプリング時に、通常の MTP draft head が提案 token を自分の分布からサンプルするか、argmax に固定するかを切り替える。未設定時は有効（`1` 相当）。`0` にすると draft token は argmax になるが、検証側は固定提案として扱い、対象モデルの出力分布から受理・棄却後の token を選ぶ処理を続ける。したがって、この変数は draft の提案方法を変えるもので、検証後の出力 sampler を greedy に切り替えるものではない（`engine/src/split/src/session.cpp:403-411,440-450,490-524`）。

単一 lane の `Session::generate` と、複数 lane 用 `BatchDecoder` の双方で読み取る。対象は Strata の split engine（`engine/src/split/src/`）であり、一般の全 engine 共通設定ではない。通常の MTP draft head を使う経路に効く。lookup の後続固定 draft 自体や DFlash2 の提案方法をこの変数がサンプル化するわけではない（`engine/src/split/src/session.cpp:595-619`; `engine/src/split/src/batch.cpp:262-288,330-379`）。

## 値と判定

共通 helper `env_int` が `getenv` で値を得て、符号付き base-10 `long long` として文字列全体を parse する。先頭の `+` / `-` は許されるが、空文字、空白、末尾文字、数値範囲外は無効で、`std::runtime_error` を投げる。整数を `!= 0` で bool 化するため、`0` のみ無効、0 以外の全整数が有効。clamp や値域検査はない（`engine/src/split/src/env.hpp:15-21,33-40`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `Session::generate` で温度 `> 0` | `1`（有効） | `1`, `-1`, `+2`, `01` | `0`, `+0`; 空文字、`true`, `0anything`, ` 1`, `1 ` は整数 parse エラー |
| `Session::generate` で温度 `<= 0` | helper を呼ばず、この変数を読まない | ― | 値が不正でも、この経路では本変数による parse エラーは起きない |
| `BatchDecoder` の構築 | `1`（有効） | `1`, `-1`, `+2`, `01` | `0`, `+0`; 空文字、`true`, `0anything`, ` 1`, `1 ` は整数 parse エラー |

helper に CLI 引数や設定ファイルからの上書きはなく、既定値は単一 lane・batch とも `1`。batch では lane ごとの温度判定と AND され、各 lane の温度が `0` ならその lane の draft はサンプリングされない（`engine/src/split/src/batch.cpp:65-87,105-118`）。

## 有効になる条件

- `Session::generate` は `temperature > 0` のときだけ `FNX_DRAFT_SAMPLE` を読み、`sample && env_int(...) != 0` を draft sampling の条件にする。温度 `0` の greedy 生成では設定値によらずこの変数を読まない（`engine/src/split/src/session.cpp:398-411`）。
- MTP の通常 draft head の候補を使う場合に効く。`1` では draft head の候補から `Sampling`（temperature、top-k / top-p / min-p）に従い draw し、その分布 `q` を検証に渡す。`0` では draft head の argmax を固定提案として渡す（`engine/src/split/src/session.cpp:440-450,490-524`; `engine/src/split/src/batch.cpp:105-118`）。
- `Session::generate` が DFlash2 (`e_.df2_on()`) 経路に入ると draft head の `draft_one` を通らず、この設定による proposal sampling は行われない（`engine/src/split/src/session.cpp:453-456,565-593`）。
- Batched decoding では `BatchDecoder` が構築される必要がある。`FNX_BATCH_DRAFTS=0` なら batch drafts は off で decoder は作れず、`lookup` モードは lookup draft のみを供給するため MTP draft head のサンプリング設定は使わない。`FNX_BATCH_DRAFTS` の未設定または `1` の MTP mode では batch decoder が本変数を使う（`engine/src/split/src/engine_common.cu:1044-1052`; `engine/src/split/src/batch.cpp:65-78,262-288`）。
- penalty 適用は別条件で、`FNX_DRAFT_PEN` と request の penalty 設定により決まる。本変数は draft token の選び方を制御し、draft logits への penalty 適用を単独では有効化しない（`engine/src/split/src/session.cpp:406-411,440-445`; `engine/src/split/src/batch.cpp:70-77,105-110`）。
- OS / CUDA・HIP build macro による本変数自体の分岐は、読み取り箇所にはない。batch draft 実行形態には別途 `FNX_HIP` 分岐があるが、`samp_drafts_` の値判定は共通（`engine/src/split/src/batch.cpp:72-77`）。

## 実行時の詳細

`Session::generate` は各 generate 呼び出しの冒頭で、サンプリング時に `env_int("FNX_DRAFT_SAMPLE", 1)` を評価する。`env_int` 自体には static cache がないため、呼び出しごとの環境値を読む。greedy 時は短絡評価で読み取りを省略する（`engine/src/split/src/session.cpp:398-411`; `engine/src/split/src/env.hpp:33-40`）。

`BatchDecoder` は構築時に一度値を読んで `samp_drafts_` に保持し、その decoder の各 lane と window で再利用する。既に構築された decoder では、後から環境値を変えてもこの bool は更新されない（`engine/src/split/src/batch.cpp:65-87,105-118,382-403`; `engine/src/split/src/batch.hpp:62-65`）。

有効値かつ温度サンプリングでは、MTP 提案を draft head の分布 `q` から draw し、検証時に対象モデル側の分布 `p` に対して `min(1, p/q)` の受理判定を行う。棄却時は正の部分 `max(0, p-q)` から置換 token を引く。無効値 `0` では draft argmax を `q` が空の固定提案として扱い、同じ検証で argmax が受理されるか、棄却時にモデル側の分布から補う（`engine/src/split/src/session.cpp:447-450,490-524`; `engine/src/split/src/batch.cpp:113-118,185-216`）。コードコメントは、いずれの場合も出力分布はモデル側のものとしている（`engine/src/split/src/session.cpp:407-409`）。

## ログと測定値

この変数専用の成功ログや値の表示はない。読み取り箇所で無効な整数を渡すと `env_int` が `NAME: 'VALUE' is not a whole number` 形式の例外を投げる（`engine/src/split/src/env.hpp:34-39`）。`fnx_run` は `fnx_run: <例外内容>` を stderr に出して終了コード `1` を返す。`sfnx` では例外が `fail()` に届くと `ERR <例外内容>` を stdout に、`sfnx: failed: <例外内容>` を stderr に出し、終了コード `1` で終了する。batch decoder は `--batch > 1` かつ batch drafts 有効時に `Server` 構築中に作られるため、その場合は不正値が起動時にこの経路へ届く（`engine/src/split/tools/fnx_run.cpp:1365-1373`; `engine/src/split/tools/sfnx.cpp:448-458,1097-1102,1107-1115`）。

## 根拠

- 整数 parse と未設定時 fallback: `engine/src/split/src/env.hpp:15-21,33-40`
- 単一 lane の温度 gate、draft 候補 draw、および検証: `engine/src/split/src/session.cpp:398-411,440-450,490-524`
- DFlash2 分岐と通常 MTP draft への移行: `engine/src/split/src/session.cpp:453-456,565-619`
- batch decoder の読み取り・保持と lane 温度 gate: `engine/src/split/src/batch.cpp:65-87,105-118,382-403`; `engine/src/split/src/batch.hpp:62-65`
- batch mode の既定値および off / lookup / MTP の区別: `engine/src/split/src/engine_common.cu:1044-1052`; `engine/src/split/src/batch.cpp:262-288`
- `fnx_run` / `sfnx` の例外出力: `engine/src/split/tools/fnx_run.cpp:1365-1373`; `engine/src/split/tools/sfnx.cpp:448-458,1097-1115`
