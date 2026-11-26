# `STRATA_PIPELINE_SPEC_DEPTH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--pipeline-windows 2` のデコードで、次のウィンドウ B を先行して投機実行する前段（最後の段を除く）の数を制限します。未設定時の既定値は実質全前段です。設定値を `k` とすると B は先頭 `k` 段まで進み、それより先の前段では A の進捗を待ちます。B の予測が外れた際の復元・再実行や、最後の段で A を検証する経路そのものはこの値では変更しません。読み取りは `engine/src/program/generate.cpp` の `pipe_dbg_env` を経由するデコードループ内です（同ファイル:681-687, 21802-21821, 22321-22330）。

この調整値はデバッグ用ゲート `STRATA_PIPELINE_DEBUG` が有効な場合に限り読み取られます。ゲートが無効なら、設定しても値は未設定として扱われます（同ファイル:681-687）。

## 値と判定

`pipe_dbg_env("STRATA_PIPELINE_SPEC_DEPTH")` が返す文字列を `std::atoi` で整数化し、`std::max(1, ...)` で 1 未満を 1 にします。整数文字列全体の検証はありません。`atoi` の変換規則により、先頭の空白と符号は認められ、数字の後ろの文字は変換結果に影響しません。数字で始まらない文字列と空文字は 0 となり 1 に丸められます（同ファイル:22323-22327）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・丸められる値 |
|---|---|---|---|
| `STRATA_PIPELINE_DEBUG` が有効 | `1 << 20`（1,048,576。実際の前段数を超えるため全前段で投機可能） | `1` 以上の整数。例: `1`, `2`, `3`, `2tail` はそれぞれ 1, 2, 3, 2 | `0`, `-2`, 空文字, `true`, `0anything` はいずれも `atoi` の結果を 1 以上に丸め、深さ 1 |
| `STRATA_PIPELINE_DEBUG` が未設定、空文字、または先頭文字が `0` | `1 << 20`（ゲートが閉じていても helper は対象値を未設定として返す） | 対象変数は読まれず、設定値は効果なし | 同左 |

デバッグゲートは `STRATA_PIPELINE_DEBUG` の空でない値で先頭文字が `0` 以外なら有効です。したがって `1`, `true`, `2anything` は有効、空文字・`0`・`0anything` は無効です。大文字小文字の判定や全体の真偽値 parse はありません（同ファイル:684-686）。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が空でなく、先頭文字が `0` 以外であること。これを満たさない場合、対象変数は helper から `nullptr` として返り、既定深さになります（`engine/src/program/generate.cpp:684-686, 22323-22327`）。
- パイプラインデコードが選択され、実行されること。対象ループは `pl_want = pipe && pl_pw >= 2 && pl_snap_ok` の場合に進みます。キャンセル中または出力上限到達時も実行しません（同ファイル:21810-21822）。
- `--pipeline-windows 2` の利用には `--serve`、GPU ごとに段を置くレイヤー分割、MTP ドラフターと `--spec` 2 以上が必要です。明示指定時はこれらの条件で検査され、自動選択時はさらに HIP build の `decode_defaults_arch_ok()` が必要です。自動選択の最小段数は既定で 3（ドラフト層を先頭 GPU に置く既定構成なら 2）で、`STRATA_PIPELINE_AUTO_MIN_STAGES` は `atoi` 後に最低 2 へ丸めて変更できます。`STRATA_PIPELINE_AUTO=0` は自動選択を止めます。`STRATA_MTP_FULL_HEAD=1` はドラフト層を先頭 GPU に置く条件を無効にし、`STRATA_MTP_STAGE0` は明示指定時の配置を決めます。非対応理由は `strata generate: --pipeline-windows ... is off: ...` と stderr に出てオプションが無効化されます（同ファイル:6540-6546, 6560-6582, 6584-6616）。
- `--batch` は既定でパイプラインを止めます。`STRATA_PW_WITH_BATCH=1` はソロ経路だけに維持し、バッチ窓自体では使いません。`--peer-device`、helper cache、複数段での `--adapt-async`、一部の DFlash2 構成も適用を妨げます（同ファイル:6555-6559, 6577-6579, 6584-6598）。
- `--pipeline-windows 1` は深さ設定に関係なくデコードの投機ループを実行しません。深さが有効になるのは `pl_pw >= 2` の経路です（同ファイル:21810-21821）。
- 同じ名前の読み取りは CUDA/HIP 共通エンジンの `engine/src/program/generate.cpp` に 1 箇所です。`engine/sycl/src/program/generate.cpp` と Metal 実装にこの名前の読み取りはなく、そこでは本設定による効果を確認できません。

## 実行時の詳細

デバッグ用の pipeline 環境変数は `pipe_dbg_env` で一括ゲートされます。ゲート判定は関数内 `static const bool` で初回呼び出し時に一度だけ行われ、深さもデコードループ内の `static const int` で初回到達時に一度だけ読み取られます。そのため、いずれかの読み取り後にプロセス環境を変更しても、このプロセスの判定には反映されません（`engine/src/program/generate.cpp:684-686, 22324-22327`）。

実行中は前段番号 `B.fr` が `pl_spec_depth` 未満で、A がその段を通過済みの場合に限り、その段で A を commit した後に B を launch します。条件を満たさなくなると B はそこで進まず、既存ループの検証・確定を待ちます。未設定の大きな既定値は `B.fr < pl_nf`（`pl_nf` は最後以外の段数）の条件で実際の前段数に制限されます（同ファイル:13722-13725, 22328-22355）。

## ログと測定値

対象変数の値を表示するログ、無効値の警告、専用の終了経路はありません。パイプラインの一般的な非対応理由は `strata generate: --pipeline-windows %d is off: %s` と stderr に出ます（`engine/src/program/generate.cpp:6599-6601`）。投機ループ内で GDN snapshot や GPU 処理が失敗した場合は共通の `die` 経路に入り、`strata serve: pipelined decode: %s` を stderr に出し、`ERR %s` を stdout に出して 1 を返します。これは深さ値自体の検証エラーではありません（同ファイル:21917-21928, 22315-22316, 22336-22347）。

`docs/DETAILS.md` に本変数の説明や測定値は見つかりませんでした。この設定の効果を比較した測定値も、調査対象ソースからは確認できません。

## 根拠

- `engine/src/program/generate.cpp:681-687` — pipeline debug 環境変数に共通のゲート。
- `engine/src/program/generate.cpp:6532-6601` — `--pipeline-windows` の自動選択、前提条件、無効化ログ。
- `engine/src/program/generate.cpp:13722-13727` — 前段数とパイプライン準備。
- `engine/src/program/generate.cpp:21802-21822` — 投機デコードループの開始条件。
- `engine/src/program/generate.cpp:22321-22355` — 深さの読み取りと各段での B 投機実行。
