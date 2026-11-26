# `STRATA_PIPELINE_PRESTAGE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--pipeline-windows` の speculative decode で、次の B 窓を stage 0 で launch する前に入力を host 側で staging するかを切り替える診断・調整用変数。既定では先行 staging し、`0` にすると B の launch 時に通常の `pl_stage` が実行される。CUDA/HIP 共通実装と SYCL 実装の両方に読み取り箇所がある。`STRATA_PIPELINE_DEBUG` が有効でないとこの変数は helper から読まれず、既定の先行 staging が使われる（`engine/src/program/generate.cpp:681-686`、`engine/sycl/src/program/generate.cpp:337-339`、`docs/MULTI_GPU.md:203`）。名前は `terminal/data/settings-register.json` にも登録されているが、実行時の値読み取りは記載の engine helper 経由である（同ファイル:33981-33995）。

先行 staging は `Verifier::prestage` で B の入力を準備し、後続の `pl_launch` が T・位置・token 列（PLE が有効なら PLE 前状態も）が一致すると準備済み入力を再利用する仕組み。token の選択や受理判定そのものを変更する設定ではない（`engine/src/core/verify.cpp:5932-5960,5980-5985`、`engine/sycl/src/core/verify.cpp:4194-4222,4240-4245`）。

## 値と判定

読み取りは `pipe_dbg_env("STRATA_PIPELINE_PRESTAGE")` 経由で、値が得られた場合は `std::atoi(v) != 0`、得られない場合は `true`。文字列全体の検証はなく、`atoi` が数値として読める先頭部分で判定する。

| 条件 | unset | 有効になる値（先行 staging） | 無効になる値（launch 時 staging） |
|---|---|---|---|
| CUDA/HIP (`engine/src/program/generate.cpp:22120-22123`) | `true` | `1`, `2`, `-1`, `1anything`, ` 1` | `0`, `0anything`, `-0`, 空文字, `true`, `false`, 数字で始まらない文字列 |
| SYCL (`engine/sycl/src/program/generate.cpp:12124-12127`) | `true` | `1`, `2`, `-1`, `1anything`, ` 1` | `0`, `0anything`, `-0`, 空文字, `true`, `false`, 数字で始まらない文字列 |

`atoi` は先頭の空白と符号を許し、数値の後ろの文字列を無視する。整数として読めない先頭部分は 0 になる。整数型で表せない値の結果は C/C++ ライブラリ仕様上未定義で、実装は範囲検査・fallback を行わない。`STRATA_PIPELINE_DEBUG` の判定は別規則で、未設定・空文字・`0` で始まる文字列では helper が対象変数を読まず、非空で先頭文字が `0` 以外なら読める（`engine/src/program/generate.cpp:684-686`、`engine/sycl/src/program/generate.cpp:337-339`）。

## 有効になる条件

- `--pipeline-windows` の decode 経路が有効であること。パイプライン自体は serve 中の GPU layer split 等の条件に従い、要求の `--pipeline-windows` 値や既定選択で決まる（`engine/src/program/generate.cpp:6532-6537,6584-6601`）。
- pipeline loop が B 窓を準備し、その B が gate を通ること。CUDA/HIP では `B.ready && B.go`、SYCL では `B.ready && B.p_on >= theta` が条件である。`theta` は pipeline gate の値（`STRATA_PIPELINE_THETA` による診断調整を含む）であり、条件を満たさない B は先行 staging されない（`engine/src/program/generate.cpp:22288-22298`、`engine/sycl/src/program/generate.cpp:12308-12318`）。
- B の stage 0 verifier が in-flight でなく、rollback 対象の `doomed` 状態でもないこと。条件に合わなければこの分岐では staging しない（同上）。
- `STRATA_PIPELINE_DEBUG` が helper の有効判定を通ること。通らない場合、対象変数は未設定扱いになるため既定の `true` が使われる（`engine/src/program/generate.cpp:684-686,22120-22123`、`engine/sycl/src/program/generate.cpp:337-339,12124-12127`）。

## 実行時の詳細

各 backend の `pl_prestage` は関数内 `static const bool` で、pipeline loop が初めて評価した時に一度だけ決まる。`pipe_dbg_env` 内の `STRATA_PIPELINE_DEBUG` 判定も関数内 static で最初の呼び出し時に cache される。したがって、起動後に環境を変更しても、そのプロセス内の判定は更新されない（`engine/src/program/generate.cpp:684-686,22120-22123`、`engine/sycl/src/program/generate.cpp:337-339,12124-12127`）。

先行 staging が選ばれ、B の gate と状態条件を満たすと、A が判定された時点で `A` の token 列から次の PLE 前状態を作り、`VF(0, B).prestage(...)` / `V0(B).prestage(...)` を呼ぶ。これは `stage_inputs` を行い、PLE が ready かつ stage 対象なら PLE 行を準備してページを prefetch する。B の `pl_launch` は準備済み状態を一度消費し、T・位置・各 token が一致し、PLE が適用される場合は PLE 前状態も一致すると再利用する。一致しない場合は launch 時に改めて `pl_stage` を実行する（`engine/src/core/verify.cpp:5932-5960,5980-5985`、`engine/sycl/src/core/verify.cpp:4194-4222,4240-4245`）。

この変数を `0` にすると `prestage` 呼び出しを飛ばすため、B の `pl_launch` が必要な staging を行う。これは staging の時点を変えるもので、B を gate に通す条件や pipeline 自体の有効条件は変えない。`prestage` が失敗した場合、pipeline loop は `die(err)` を通り、stderr に `strata serve: pipelined decode: <理由>`、stdout に `ERR <理由>` を出して `1` を返す（`engine/src/program/generate.cpp:21917-21928,22295-22298`、`engine/sycl/src/program/generate.cpp:11894-11901,12314-12317`）。

## ログと測定値

この変数の値だけを示す専用ログは見つからない。pipeline 用ログ `STRATA_PIPELINE_LOG` は別設定で、B の chain 情報を出力する。先行 staging の失敗時は上記の pipeline decode エラーが出る（`engine/src/program/generate.cpp:21917-21928,22120-22123`、`engine/sycl/src/program/generate.cpp:11894-11901,12124-12127`）。Strata の資料にこの変数の性能測定値はない。

## 根拠

- `engine/src/program/generate.cpp:681-686,21802-21825,22120-22123,22288-22304`
- `engine/sycl/src/program/generate.cpp:337-339,12124-12131,12308-12323`
- `engine/src/core/verify.cpp:5932-5961,5980-5985`
- `engine/sycl/src/core/verify.cpp:4194-4223,4240-4245`
- `docs/MULTI_GPU.md:203`
