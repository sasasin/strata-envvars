# `FNX_YARN_ORIG_CTX`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Flash-Next（sFNX）の YaRN RoPE scaling が使う「スケーリング元の学習済み context 長」を指定します。`FNX_ROPE_SCALE` またはモデル自身の YaRN 設定でスケーリングが有効な場合にだけ使えます。値は Engine 作成時に一度読み、RoPE 定数の計算と Engine が受け付ける最大 context の判定に使います。通常の Strata engine ではなく、`src/split` の `strata-split-*` / `sfnx` 系が対象です（`src/split/CMakeLists.txt:92-120`）。

## 値と判定

| 環境変数の状態 | 結果 |
| --- | --- |
| 未設定 | `env_orig = 0`。この変数による上書きはなく、モデルの `original_context_length`、なければ `context_length` を使う。 |
| 設定値が 1..2,147,483,647 の整数 | 学習済み長として候補にする。ただし下記のスケール有効条件とモデル metadata との整合性を満たす必要がある。 |
| 空文字、整数でない文字列、整数範囲を超える文字列 | 整数 parser が拒否し、`FNX_YARN_ORIG_CTX: '<値>' is not a whole number` 例外になる。 |
| 0、負数、2,147,483,647 超 | `FNX_YARN_ORIG_CTX: want a trained context length from 1 to 2147483647, got <値>` で拒否される。 |

変換は `env_int()` → `parse_whole()` → base 10 の `strtoll()` です。省略可能な `+` / `-` と数字列を受け付け、値全体を消費し、`long long` の overflow を拒否します。空白、末尾文字、空文字は受け付けません。たとえば `+65536` は整数として読まれ、`65536x` や ` 65536` は不正です。`getenv()` が非 null かを先に調べるので、空文字も「未設定」にはなりません（`src/split/src/engine.cu:41-47`, `src/split/src/env.hpp:15-22,33-40`）。

## 有効になる条件

- **YaRN scale が有効であること:** `FNX_ROPE_SCALE` が未設定で、モデルの `yarn_factor > 1` ならモデル側の scale を使います。環境変数が未設定のモデルでは `FNX_ROPE_SCALE` が必要です。scale が無効（未設定かつモデルに YaRN なし、または scale `1`）なのにこの変数が設定されていると、`FNX_YARN_ORIG_CTX is set without FNX_ROPE_SCALE, which it is for` で拒否されます（`src/split/src/rope.hpp:82-97`, `src/split/src/engine_common.cu:1001-1008`）。
- **モデル metadata との一致:** GGUF に正の `original_context_length` がある場合、指定値はそれと完全一致しなければなりません。異なる値は `the model's original_context_length is ...; FNX_YARN_ORIG_CTX ... disagrees (leave it unset)` で拒否されます。この場合、環境変数でモデル値を上書きできません。
- **metadata に元長がない場合:** `original_context_length` が正でなければ指定値が `context_length` 以下である必要があります。より大きい値は「past the model's trained ...」として拒否されます。未設定なら `context_length` が元長になります（`src/split/src/rope.hpp:99-110`）。
- **最大 context:** scale と元長から得た rotary limit より Engine の `max_ctx` が大きいと Engine 作成を拒否します。sFNX では `max_ctx` は `--max-context`（既定 262144）、`fnx_run` では `FNX_MAX_CTX`（既定 4096）です（`src/split/tools/sfnx.cpp:65-70,85,103`; `src/split/tools/fnx_run.cpp:984-988`; `src/split/src/engine.cu:48-53`; `src/split/src/rope.hpp:111-113`）。

`sfnx --rope-scale S` は `FNX_ROPE_SCALE` を設定する CLI 経路ですが、`FNX_YARN_ORIG_CTX` に対応する CLI 引数はありません。既存の `FNX_ROPE_SCALE` と CLI 値が異なれば引数解析で拒否し、一致または未設定なら scale を環境へ設定します（`src/split/tools/sfnx.cpp:91-96`）。

## 実行時の詳細

Engine constructor は `getenv()` で設定有無を調べ、設定時に `env_int()` で値を読みます。static cache はなく、プロセス内で Engine を新しく作るたびに評価されます。ただし各 Engine の `rope_` は constructor 中に確定し、その Engine の RoPE kernel 引数に使われます。稼働中 Engine の処理ごと・リクエストごとに環境を読み直す動作ではありません（`src/split/src/engine.cu:31,37-60`; `src/split/src/engine.hpp:218-221`）。

選択された元長 `orig` と scale `S` から rotary limit は `max(ctx_train, (long long)(orig * S))` になります。`yarn_rope()` は `orig` を周波数補間帯の上下端計算にも使用します。したがって値は単なる表示用 metadata ではなく、RoPE の角度計算と context 上限に影響します（`src/split/src/rope.hpp:47-66,99-113`）。

スケーリングが選択されると stderr に `fnx: rope scaling YaRN x...` の行が出て、`n_ctx_orig` と補間 pair 範囲などが表示されます。モデル metadata から scale を得た場合は `(the model's own)` も付きます。環境値がモデル値と不一致、scale がない、trained length を超える、または要求 context が limit を超える場合は例外になります。`sfnx` は Engine 初期化中の例外を `ERR <理由>` と stderr の `sfnx: failed: <理由>` に出し、終了コード 1 で終了します。CLI 引数解析で起きた例外は stderr の `sfnx: <理由>` と終了コード 2 です（`src/split/tools/sfnx.cpp:1030-1035,1040-1062`; Engine の拒否理由は `src/split/src/rope.hpp:94-108`, `src/split/src/engine.cu:44-53`）。`fnx_run` は例外を stderr の `fnx_run: <理由>` に出して終了コード 1 を返します（`src/split/tools/fnx_run.cpp:1364-1373`）。

## 補助ツールでの参照

`fnx_run` は実行 identity の build 行を組み立てる際、scale が有効なら値を `orig ...` として記録します。また `run_identity()` は名前が `FNX_` で始まる環境変数を列挙して identity の `env` 行へ記録し、exact 比較で base と現在の環境値の差を表示します（`src/split/tools/fnx_run.cpp:388-418,800-801`）。scale が有効な exact 比較では、llama.cpp 参照を作るための案内文字列にも値を含め、参照ファイル名へ反映します。この文字列は案内として出力されるもので、`fnx_run` が外部プロセスへ環境を転送・実行する動作ではありません（`src/split/tools/fnx_run.cpp:831-845,860-871`）。これらは試験・比較用ツールの記録や案内で、Engine の値判定を変える別経路ではありません。

## 根拠

- 実際の値読み取り・範囲検査・RoPE scale との引き渡し: `src/split/src/engine.cu:37-60`。
- 整数変換とエラー条件: `src/split/src/env.hpp:15-22,33-40`。
- scale の選択、metadata との優先関係、trained length と rotary limit: `src/split/src/rope.hpp:82-113`。
- scale 自体の環境値判定: `src/split/src/engine_common.cu:1001-1008`。
- sFNX CLI と Engine の初期化・失敗出力: `src/split/tools/sfnx.cpp:65-105,1030-1062`。
- 試験用 `fnx_run` の値記録・参照案内・例外出力: `src/split/tools/fnx_run.cpp:388-418,800-801,831-871,1364-1373`。
- CUDA/HIP split executable の構成: `src/split/CMakeLists.txt:92-120`。
