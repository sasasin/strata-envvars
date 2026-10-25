# `--aux-cpus`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されなかった。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ `strata` エンジン（`strata generate` 相当の引数 parser） |
| オプション | `--aux-cpus` |
| 別名 | なし |
| 値 | `off`、`auto`、または論理 CPU 番号リスト（例: `24,26`、`24-27`） |

## 役割

CPU pool の worker と host thread 以外のエンジンスレッドを、指定 CPU に配置する。対象例は adaptive tier の job thread、prefill helper、CUDA driver の既存スレッドなど。スレッド配置だけを変更し、生成結果は変えない。既定値は `off` で、作成時の配置を維持する（`src/program/generate.cpp:1046-1052`、`include/strata/platform/aux_cpus.hpp:1-19`）。

## 使い方

```sh
strata --model model.gguf --aux-cpus auto --serve
strata --model model.gguf --aux-cpus 24,26 --serve
strata --model model.gguf --aux-cpus off --serve
```

CPU 番号はプロセスが利用できる論理 CPU 番号を指定する。明示リストから host CPU、pool worker CPU、プロセスに許可されていない CPU は除かれる（`include/strata/platform/aux_cpus.hpp:118-127, 375-396`）。

## 値と既定値

- 省略時は `off`。`off` は大文字小文字を区別する完全一致で認識される（`include/strata/platform/aux_cpus.hpp:130-149`）。
- `auto` は host の物理 core に属する SMT sibling を先に選び、その後 worker が使わない物理 core の CPU を選ぶ。worker と同じ物理 core の CPU、および topology を特定できない CPU は選ばない（`include/strata/platform/aux_cpus.hpp:84-115`）。
- CPU リストは数字、カンマ区切り、昇順の範囲で指定する。重複は除去され、昇順に並べられる。負数、文字、空項目、逆順範囲、100000 を超える番号は parser が拒否する（`include/strata/platform/aux_cpus.hpp:50-82`）。範囲の上限も同じ数値上限の対象。
- 無効値は `strata generate: --aux-cpus takes off, auto or a CPU list ...` を stderr に出して終了コード 2 で拒否する。値を省略した場合は `--aux-cpus needs a value` を stderr に出し、終了コード 2 で終了する（`src/program/generate.cpp:2418-2420, 2530-2537`、`include/strata/platform/aux_cpus.hpp:137-149`）。
- 同じオプションを複数回指定すると、各値は順に検証され、最後に代入された値が使われる（`src/program/generate.cpp:2416-2421, 2530-2537`）。空文字列は parser 上 `off` と同じだが、環境変数への fallback 条件も空文字列なので、空の CLI 値を渡すと `STRATA_AUX_CPUS` が設定されていればその値が使われる（`include/strata/platform/aux_cpus.hpp:137-141`、`src/program/generate.cpp:2912-2920`）。

## 実行時の動作

明示した CLI 値が空でなければ `STRATA_AUX_CPUS` より優先される。CLI 値が空の場合に限り環境変数を読み、どちらも未指定なら空値（`off`）で初期化する。環境変数の値も同じ `parse_spec` で検証され、不正なら `strata generate: STRATA_AUX_CPUS: ...` を stderr に出して終了コード 2 となる（`src/program/generate.cpp:2912-2921`）。

Linux では pool 構築前にプロセスが使用できる CPU 集合を記録し、pool worker と host CPU が確定した後に配置先を作る。`auto` は sysfs の package/core 情報を使い、明示リストは許可 CPU から host と worker の CPU を除く。配置先が空なら機能は有効にならず、起動ログに `none spare ...` と出る（`include/strata/platform/aux_cpus.hpp:218-233, 351-405`、`src/program/generate.cpp:6004-6010`）。

機能が有効なら、起動済みで pool/host 所有として登録されていないプロセススレッドを走査して配置し、新しく作られる対象スレッドも作成時に配置する。pool worker と host thread は移動対象外。affinity の変更に失敗したスレッドはその場で移動されず、失敗自体を示す個別エラーは出さない（`include/strata/platform/aux_cpus.hpp:179-192, 236-263`）。

serve の各リクエストでは `strata_tune` の `aux_cpus=0|1` が起動時設定を上書きできる。`0` は移動済みスレッドの元の affinity を復元し、`1` は利用可能な配置計画がある場合に有効化する。明示値がないリクエストは起動時の状態を使う。切り替え時は stderr に `strata serve: aux cpus ON/off for this request` が出る。空の計画があると `1` を要求しても有効にならない（`src/program/generate.cpp:12315-12319, 12325-12354, 13954-13963`、`include/strata/platform/aux_cpus.hpp:265-287`）。

## 適用条件と副作用

- 実際の CPU affinity 配置は Linux の実装だけにある。他 OS では値の形式検査は行うが、配置関数は何もせず、起動時の案内は `strata aux cpus: not available on this system` となる（`include/strata/platform/aux_cpus.hpp:407-423`）。
- Qwen3.5 専用エンジンへ振り分けられた場合、このオプションは専用 parser に渡る。専用 parser は通常実行時に未対応オプションとして usage と終了コード 2 を出し、`--serve` 時は値を伴う未対応引数を警告して読み飛ばす。従ってこの経路では CPU 配置を行わない（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3742-3795`）。
- 実装は `sched_getaffinity` / `sched_setaffinity` と `/proc/self/task`、CPU topology の sysfs 情報に依存する。スレッド配置を変更・復元する副作用があり、出力結果は変えない（`include/strata/platform/aux_cpus.hpp:34-39, 179-207, 358-372`）。

## 出力とエラー

起動時に pool の配置案内とともに、stderr へ `strata aux cpus: threads that are neither pool workers nor the host go to CPUs ...` を出す。配置先がない場合は理由を示して `none spare ...`、無効時は `(off at start; a request's aux_cpus=1 turns it on)`、有効時は移動したスレッド数を含む `(on; N threads placed so far)` が付く（`src/program/generate.cpp:5998-6010`、`include/strata/platform/aux_cpus.hpp:375-405`）。

## 根拠

- parser と CLI エラー: `src/program/generate.cpp:2416-2421, 2530-2537`
- help 表示と説明: `src/program/generate.cpp:1046-1052`
- 値の構文と validation: `include/strata/platform/aux_cpus.hpp:50-82, 130-149`
- 環境変数 fallback、初期設定: `src/program/generate.cpp:2912-2921`
- CPU 集合・配置計画・起動ログ: `include/strata/platform/aux_cpus.hpp:218-233, 351-405`; 呼び出し箇所 `src/program/generate.cpp:6004-6010`
- request ごとの上書き: `src/program/generate.cpp:12315-12319, 12325-12354, 13954-13963`
- Qwen3.5 専用 parser への分岐と未対応時の処理: `src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3742-3795`
- 非 Linux 実装: `include/strata/platform/aux_cpus.hpp:407-423`
