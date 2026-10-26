# `DS4_GG_IQ256`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek-V4.1 の GGUF expert を CPU lane で処理するとき、i-quant の行積に ggml-cpu の実装を使うか、Strata の複数 token 向け AVX2 行カーネルを使うかを制御します。既定では CPU 機能と token 数に応じて選びます。コード上の `IQ256` は AVX2 カーネルの名称ですが、別変数 `DS4_GG_IQ512` の条件がそろうと AVX-512 カーネルが先に選ばれる経路もあります。

## 値と判定

初回に `use_iq256()` が `getenv()` で読み、`std::atoi()` の結果でモードを決めます。文字列全体の検証はなく、`atoi` が読み取る符号付き10進整数の接頭部分が 0 かどうかで判定します（例: `1abc` は有効、`0abc`、空文字、整数で始まらない文字列は無効）。

| 条件 | 選択モード |
|---|---|
| unset | 自動選択（モード2）。ただし ggml-cpu が AVX2、FMA、F16C のすべてを報告しない場合は無効（モード0） |
| 設定値の `atoi()` が 0 | 無効（モード0） |
| 設定値の `atoi()` が 0 以外 | 明示有効（モード1）。ただし上記 CPU 機能が不足する場合は無効 |

空文字は「未設定」ではなく、`atoi("") == 0` として無効になります。負の整数も 0 以外なので明示有効です。

## 有効になる条件

- DeepSeek-V4.1 実行ファイルが `STRATA_NATIVE_EXPERTS` 有効でビルドされ、ggml-cpu lane が組み込まれていること。無効ビルドでは `gg_cpu_fmt()` が失敗し、環境変数を読む実装もコンパイルされません。
- 対象が ggml block type の CPU expert 経路であり、かつ `iq256x_supported()` が対応する型（内部 type ID 16, 17, 18, 21, 22, 29）であること。
- カーネルを使う前に `own_ok()` がその型について ggml-cpu の結果との一致を確認できること。不一致なら ggml-cpu の dot に戻ります。
- 自動モードでは、IQ3_S（type 21）と IQ1_M（type 29）は1 token 以上、それ以外の対応型は2 token 以上で AVX2 行カーネルを選びます。明示有効モードではこの token 数しきい値を適用しません。

AVX-512 経路は `DS4_GG_IQ512` と CPU 機能の判定に従い、この変数が0の場合を除いて AVX2 より先に確認されます。従って `DS4_GG_IQ256=1` でも、対応 CPU・型なら AVX-512 が選ばれることがあります。

## 実行時の詳細

`gg_cpu_gate_up()` と `gg_cpu_down()` は `dots()` を呼び、token 数が正のときに `use_iq256()` の結果で AVX-512 行、AVX2 行、または ggml-cpu の `vec_dot` を選びます。環境値から作るモードは `g_iq256` に保存され、プロセス内の最初の対象 dot 呼び出しで一度だけ確定します。その後の環境変更は反映されません。カーネル選択前の `own_ok()` も型・実装ごとに一度だけ実行し、複数 token 数を含むテスト入力で ggml-cpu の結果と比較します。不一致時は ggml-cpu を使い、`DS4_DBG_GG` または `DS4_GG_VERBOSE` が設定されていれば stderr に `ds4: CPU lane type %d: AVX2 rows differ from ggml-cpu's dot at %d tokens, not used` を出します。

`docs/DETAILS.md` にこの環境変数固有の利用条件や測定結果は見当たりません。ソースコメントには AVX2 行カーネルの比較測定と結果が変わらない旨の説明がありますが、同ファイルには測定環境の詳細がなく、この調査でも実測はしていません。

## 根拠

- `src/dsv41/ds4_gg_cpu.cpp:87-98,203-215` — モードの説明、既定の token 数しきい値、環境値の読み取りとモード判定。
- `src/dsv41/ds4_gg_cpu.cpp:99-148,217-232` — ggml-cpu との一致確認、失敗時のログと fallback、実行時のカーネル選択。
- `src/kernels/cpu/iq_avx2.cpp:538-553` — AVX2 行カーネルの対応型。
- `src/dsv41/ds4_gg_cpu.cpp:179-200`、`src/kernels/cpu/iq_avx512.cpp:603-617` — `DS4_GG_IQ512` の優先判定と AVX-512 対応型。
- `src/dsv41/ds4_gg_cpu.cpp:284-295`、`CMakeLists.txt:809-835` — ggml-cpu lane の無効ビルド時の stub と `STRATA_NATIVE_EXPERTS` による組み込み条件。
