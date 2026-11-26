# `STRATA_PIPELINE_SNAP_OVERLAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--pipeline-windows 2` の decode 中、投機 window が使う GDN state snapshot を window の実行と並行して取得するかを選びます。既定の overlap 経路は snapshot 用の二つ目の device buffer、side stream、event を使って snapshot を window の実行中に取り、commit 時に待ち合わせます。無効にすると snapshot 用 buffer は一つとなり、window の commit 前に同じ stream 上で snapshot をコピーします。生成結果の選択を変える設定ではなく、snapshot の取得と復元の実行経路を切り替えます（CUDA 実装: `engine/src/program/generate.cpp:13714-13727, 22171-22185, 22328-22347`、SYCL 実装: `engine/sycl/src/program/generate.cpp:7991-8009, 12160-12183, 12336-12364`）。

この名前はパイプラインの診断・調整用 helper `pipe_dbg_env` 経由で読み取られます。`STRATA_PIPELINE_DEBUG` が有効でないと helper はこの変数を参照せず、既定値が使われます（CUDA: `engine/src/program/generate.cpp:681-687`、SYCL: `engine/sycl/src/program/generate.cpp:325-340`）。

## 値と判定

両 backend とも `std::atoi(v) != 0` で判定し、helper が `nullptr` を返す（環境変数が未設定、または debug gate が無効）場合も有効扱いです。`atoi` は先頭の整数部分を変換し、数値としての文字列全体の妥当性検査はありません。

| 実装・条件 | unset / helper が `nullptr` | overlap が有効 | overlap が無効 |
|---|---|---|---|
| CUDA/HIP (`engine/src`) および SYCL。`pipe && o.pipeline_windows >= 2` の初期化時 | 有効 | `1`, `-1`, `2tail` など、`atoi` 結果が 0 以外 | 空文字、`0`, `0tail`, `true`, `false`, `tail` など、`atoi` 結果が 0 |

空白や符号は `atoi` の整数変換に従うため、たとえば `  +1tail` は有効、`  -0x` は無効です。大文字小文字の比較はありません。`STRATA_PIPELINE_DEBUG` 自体は未設定・空文字・先頭文字が `0` なら gate 無効、それ以外（例: `1`, `true`, ` 0`）なら有効です。したがって `STRATA_PIPELINE_DEBUG=0` では対象変数の `=0` も読み取られず、overlap は既定で有効です（各 backend の `pipe_dbg_env` 定義: 上記行）。

## 有効になる条件

- 2 window 以上のパイプラインが実際に選択されていること。対象箇所の初期化は `pipe && o.pipeline_windows >= 2` の場合だけです。それ以外ではこの環境変数による分岐はありません（CUDA: `engine/src/program/generate.cpp:13722-13728`、SYCL: `engine/sycl/src/program/generate.cpp:7992-8009`）。
- パイプライン自体は serve の multi-GPU layer split 経路です。実行時チェックでは serve、別 GPU に分けた layer split、MTP drafter と `--spec` 2 以上が必要で、helper cache、`--peer-device`、通常の batch slots などとの組み合わせでは無効化されます（`engine/src/program/generate.cpp:6532-6537, 6584-6604`）。設定により単独 request の経路を残す batch 例外があります。
- CUDA/HIP 側では、二つ目の snapshot buffer、side stream、event の確保に失敗した場合、`pl_snap_overlap` は false になり、snapshot はクリティカルパス上で取得されます。SYCL 側でも二つ目の buffer・queue・event の作成結果が overlap の成否を決めます（CUDA: `engine/src/program/generate.cpp:13743-13753`、SYCL: `engine/sycl/src/program/generate.cpp:8009-8032`）。
- 最初の snapshot buffer を確保できない場合、CUDA は `--pipeline-windows 2: the GDN snapshot of stage %d (%.1f MiB) does not fit; the decode stays serial` を stderr に出し、snapshot が使用可能でない状態にします。SYCL は `--pipeline-windows 2: the GDN snapshot (%.1f MiB) does not fit; the decode stays serial` を出します（CUDA: `engine/src/program/generate.cpp:13735-13741`、SYCL: `engine/sycl/src/program/generate.cpp:7998-8008`）。

## 実行時の詳細

各 backend の `pipe_dbg_env` は `STRATA_PIPELINE_DEBUG` の有効性を関数内 static 値として最初の呼び出し時に cache します。対象変数はパイプライン用 snapshot 資源の初期化時に一度評価され、CUDA は `pl_snap_overlap` に、SYCL は条件式の結果に保存されます。初期化後に環境を書き換えてもこの実行の判定は変わりません（CUDA: `engine/src/program/generate.cpp:684-687, 13725-13728`、SYCL: `engine/sycl/src/program/generate.cpp:337-340, 7997-8009`）。

overlap が有効なら、各 window の偶奇に対応する buffer へ side stream から GDN state をコピーし、event を記録します。commit 側は対応 event を待ってから window の commit と次の window の起動を進めます。誤った投機 window を戻す際は対応する snapshot を GDN state に復元します（CUDA: `engine/src/program/generate.cpp:21873-21885, 22171-22185, 22328-22347`、SYCL: `engine/sycl/src/program/generate.cpp:11820-11860, 12160-12183, 12336-12364`）。

無効の場合は overlap 用の追加資源を確保せず、一つの buffer を使います。window の commit 前に同じ処理 stream / queue で GDN state をコピーし、投機 window の復元にもその buffer を使います。初期化時の serve ログは、snapshot が利用可能なら有効時に ` (decode too; the GDN snapshots beside the window)`、無効時に ` (decode too; the GDN snapshot on the critical path)` を付けます（CUDA: `engine/src/program/generate.cpp:13735-13760, 22335-22339`、SYCL: `engine/sycl/src/program/generate.cpp:8000-8039, 12340-12358`）。

## ログと測定値

通常の初期化ログは `strata serve: --pipeline-windows %d: two verifiers per stage, %d stages overlap across windows...` で、末尾は前節のとおり snapshot の経路を示します。snapshot buffer が確保できない場合の stderr 文言も前節に記載しました。値の parse 自体について警告・エラーを出す処理はありません。`docs/DETAILS.md` にこの変数の測定値は見つからず、ここでは性能差を記載しません。

## 根拠

- helper と debug gate: `engine/src/program/generate.cpp:681-687`; `engine/sycl/src/program/generate.cpp:325-340`
- CUDA/HIP 側の値判定、snapshot 資源、ログ: `engine/src/program/generate.cpp:13714-13760`
- CUDA/HIP 側の snapshot 取得、commit、復元: `engine/src/program/generate.cpp:21873-21885, 22171-22185, 22328-22347`
- SYCL 側の値判定、snapshot 資源、ログ: `engine/sycl/src/program/generate.cpp:7991-8039`
- SYCL 側の snapshot 取得、commit、復元: `engine/sycl/src/program/generate.cpp:11820-11860, 12160-12183, 12336-12364`
- パイプラインの適用条件: `engine/src/program/generate.cpp:6532-6537, 6584-6604`
