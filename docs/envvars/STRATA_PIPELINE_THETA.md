# `STRATA_PIPELINE_THETA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

パイプライン化された prompt/decode windows で、MTP の chain が予測する次 window の採用確率 `p_on` に対する投機実行ゲートを指定する testing 用の値。値が 0 以上なら `p_on >= theta` のとき次 window を投機的に進める。通常の生成 token の選択規則を直接変える値ではなく、パイプラインが使われない経路では効果がない。CUDA/HIP 共通コードと SYCL 実装に読み取り箇所がある（`engine/src/program/generate.cpp:20263-20266,21867-21870`、`engine/sycl/src/program/generate.cpp:11155-11158,12241-12243,12314-12318,12336-12338`）。

## 値と判定

どちらの実装も `pipe_dbg_env("STRATA_PIPELINE_THETA")` を通じ、値が得られた場合は C/C++ の `std::atof` で `float` に変換する。文字列全体の妥当性検証、clamp、範囲チェックはない。空文字や数値で始まらない文字列は `atof` の変換結果 0 になり、数値の後ろに文字がある場合は数値部分が使われる。したがって `0.5junk` は 0.5、`true` や `abc`、空文字は 0 として扱われる。空白・大文字小文字は環境変数名以外で検査されない。負値も拒否されず、backend ごとの別経路に入る。

| 実装 | unset（または debug 無効） | 設定値の扱い |
|---|---|---|
| CUDA/HIP (`engine/src/program/generate.cpp`) | debug gate が有効で THETA が unset、かつ `STRATA_PIPELINE_HIT_MIN` が未設定または変換値 `< 0` なら `theta=0.2`。HIT_MIN の変換値が `>= 0` なら `theta=-1` とし、hit-rate gate に切り替える。debug gate が無効なら THETA は unset として扱う。 | 空文字・`abc`・`0` は theta 0。`1` は `p_on >= 1` を要求し、範囲外を含む正値も clamp しない。負値は `theta < 0` の hit-rate gate に切り替える。 |
| SYCL (`engine/sycl/src/program/generate.cpp`) | `theta=0.2`。debug gate が無効なら THETA は unset として扱う。 | 空文字・`abc`・`0` は theta 0。`1` は `p_on >= 1` を要求し、範囲外を含む正値も clamp しない。負値は `p_on >= theta` 比較を通りやすくし、CUDA/HIP の hit-rate gate には切り替えない。 |

共通 helper は `STRATA_PIPELINE_DEBUG` が未設定、空、または先頭文字が `'0'` の場合に対象名を読まず、設定されていて先頭文字が `'0'` 以外なら読む。従って `STRATA_PIPELINE_DEBUG=0anything` は無効、`true`、`01`、` 0` は有効。debug 判定は helper 内の関数 static で初回呼び出し時に一度だけ評価される（`engine/src/program/generate.cpp:681-687`、`engine/sycl/src/program/generate.cpp:325-340`）。

CUDA/HIP では通常、`STRATA_PIPELINE_HIT_MIN` の空文字は明示的に無効値として `-1` に変換され、非空なら `atof` される（`engine/src/program/generate.cpp:20259-20266`）。値が `>= 0` なら THETA が unset のとき hit-rate gate が選ばれる。THETA が明示されて `>= 0` なら数値ゲートを使い、`< 0` なら hit-rate gate を使う。hit-rate gate は `p_on` の区分ごとの履歴比率と `hit_min` を比べる実装である（`engine/src/program/generate.cpp:21860-21870`）。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が helper の初回評価時に有効であること。無効なら THETA は読まれず、上表の unset 時の既定経路になる（`engine/src/program/generate.cpp:684-686`、`engine/sycl/src/program/generate.cpp:337-339`）。
- `--pipeline-windows` のパイプライン経路に入ること。これはサーバーの layer split と MTP (`--mtp`, `--spec >= 2`) を使う経路であり、条件を満たさない場合は pipeline が無効化される（CUDA/HIP: `engine/src/program/generate.cpp:6584-6601`; SYCL: `engine/sycl/src/program/generate.cpp:3590-3634`）。
- 自動有効化の条件は backend で異なる。HIP 共通コードは `STRATA_PIPELINE_AUTO`、stage 数、モデル/ドラフト、batch 等を条件にする一方、SYCL は2枚の Arc B-series GPU で既定有効化する。明示的な `--pipeline-windows` と、各実装が後段で検証する条件はそれぞれの上記行にある（`engine/src/program/generate.cpp:6560-6582`、`engine/sycl/src/program/generate.cpp:3590-3618`）。
- CUDA/HIP 実装では `STRATA_PIPELINE_HIT_MIN` が未設定・負値なら通常の未設定既定値 0.2 を選ぶ。非負値なら THETA 未設定時に count-based gate に切り替わる（`engine/src/program/generate.cpp:20259-20266,21867-21870`）。
- `STRATA_PIPELINE_SWITCH=<file>` が debug gate 経由で設定され、pipeline が有効でファイルを開ける場合、リクエストごとにファイルを読み、`theta=<f>` があれば環境変数由来の値を上書きする。CUDA/HIP では `hit=<f>` があり `theta=` がない場合、`theta=-1` として hit-rate gate を選ぶ。SYCL switch は `theta=` を上書きするが `hit=` は処理しない（CUDA/HIP: `engine/src/program/generate.cpp:20284-20294`; SYCL: `engine/sycl/src/program/generate.cpp:11163-11172`）。

## 実行時の詳細

CUDA/HIP 実装は各リクエストの prompt 読み取り準備中に `pl_theta` を設定し、SYCL 実装も各リクエストの同じ段階で設定する。THETA の getenv/変換結果自体は関数 static に保存されないため、後続リクエストで環境が変更されていれば読み直される。ただし `STRATA_PIPELINE_DEBUG` の有効/無効だけは helper の関数 static にキャッシュされ、プロセス中には再評価されない（CUDA/HIP: `engine/src/program/generate.cpp:20259-20266`; SYCL: `engine/sycl/src/program/generate.cpp:11151-11161`）。

CUDA/HIP の投機 window は `theta >= 0` なら `p_on >= theta`、負値なら `pl_cal` の hit-rate 条件で可否を決める（`engine/src/program/generate.cpp:21850-21870,21967-21983,22095-22101`）。SYCL は chain の各段階で `pa < theta` による投機候補の打ち切りを行い、次 window の stage 0 投機実行は `B.p_on >= theta` のときに限る。したがって負の値は確率が 0 以上の候補を通しやすくする。その他の一致条件、window 長、context 上限、pipeline の状態判定は別途残る（`engine/sycl/src/program/generate.cpp:12216-12248,12328-12338`）。

## ログと測定値

THETA を環境から読み取ったこと自体を示す専用ログはない。CUDA/HIP では `dec_timing` が有効な場合に pipeline 集計ログへ `theta %.2f` または `hit %.2f` とゲート種別を出す（`engine/src/program/generate.cpp:22584-22594`）。switch ファイルが正常に開けた場合は `strata pipeline switch: ... theta=...` を stderr に出す（`engine/src/program/generate.cpp:20284-20301`、SYCL: `engine/sycl/src/program/generate.cpp:11163-11174`）。

`docs/DETAILS.md` にこの変数の挙動や条件付き測定値の記載は見当たらない。ここではソースコメント中の過去の測定値を一般的な性能値として転記していない。

## 根拠

- CUDA/HIP の debug gate、THETA と HIT_MIN の既定・優先順位: `engine/src/program/generate.cpp:681-687,20259-20266`
- CUDA/HIP の pipeline 条件: `engine/src/program/generate.cpp:6532-6537,6560-6601`
- CUDA/HIP のゲート判定、switch の上書きと観測ログ: `engine/src/program/generate.cpp:20245-20301,21850-21870,22584-22594`
- SYCL の debug gate、THETA 読み取りと switch の上書き: `engine/sycl/src/program/generate.cpp:325-340,11151-11174`
- SYCL の自動有効化・無効化条件とゲート結果: `engine/sycl/src/program/generate.cpp:3590-3634,12216-12248,12328-12338`
