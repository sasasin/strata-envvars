# `STRATA_ROCBLAS_TUNING`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。調査対象リポジトリの作業ツリーには未追跡の `nohup.out` があるが、以下は HEAD に含まれるソースに基づく。

## 役割

HIP ビルドで、プロンプト処理中の FP16 入力・FP16 出力 GEMM が使う rocBLAS solution index を、指定したチューニング表から選びます。値は表ファイルそのもの、または表を格納したディレクトリです。変数を有効にしても GEMM 全般のカーネル選択が変わるわけではなく、HIP の `Gemm::f16_inplace()` が呼ばれたとき、表に合う行がある形状だけで指定 solution を試します。該当行がなければ通常の GEMM に進みます。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | チューニング状態を作らず、既定 GEMM を使う。 |
| 空文字 | `create_rocblas_state()` が `! *path` で終了し、未設定時と同じく既定 GEMM を使う。 |
| 空でない文字列 | 文字列をパスとして扱う。数値・真偽値への変換や前後空白の除去はしない。 |

指定先がディレクトリなら、現在の HIP device の arch と実行中 rocBLAS の version string から `<arch>-rocblas-<version>.txt` を組み立てます。version 末尾の `.` はすべて落としてからファイル名に使います。ファイルなら指定したパスをそのまま開きます。

表の先頭の有効行は `STRATA_ROCBLAS_TUNING_V1 <arch> <version>` 形式でなければなりません。arch と version は実行環境と完全一致が必要です。以降の行は `f16o N K ldy T_bucket <solution>` 形式で、数値条件・列数・重複キーなどが検査されます。`solution` は `default` または、10進整数全体を `strtol` で変換でき `int` の範囲に収まる値です。空行と `#` 以降は無視されます。不正な表、開けないパス、ヘッダー不一致では表を使わず、既定 GEMM に戻ります。

## 有効になる条件

- Strata が `__HIPCC__` かつ `STRATA_ROCBLAS_AVAILABLE` の条件でビルドされていること。CUDA 専用ビルドにはこの読み込み・適用経路がありません。
- HIP device と rocBLAS のバージョン取得、および rocBLAS handle 作成、表の読み込みが成功すること。
- 表を実際の GEMM に適用するには、プロンプトの `prompt_f16()` が有効で `Gemm::f16()` が `beta == 0.0f` となり、`f16_inplace()` に進む必要があります。`prompt_f16()` 自体は `STRATA_HIP_PROMPT_F16` による別の opt-in です。FP16 出力経路でない GEMM、`beta != 0` の GEMM、その他の backend ではこの表は使われません。
- `f16_inplace()` の形状 `(N, K, ldy, T)` に対応する表行があり、その行が `default` ではなく solution index を持つこと。形状ごとに最も近い `T_bucket` の行を使い、距離が同じ場合は小さい bucket を選びます。

表の行を選べても、rocBLAS が solution の実行を拒むことがあります。拒否された呼び出しでは既定 GEMM に fallback します。同一形状で拒否が3回に達すると、その形状は以後この状態内で tuned 扱いから外れます。

## 実行時の詳細

変数は `Gemm::init()` または `Gemm::init_external()` の呼び出し中に `create_rocblas_state()` が読みます。値はプロセス全体の static cache ではなく、作られた `Gemm` ごとの state として保持され、同じ state の間は環境変数を変更しても表を読み直しません。表を読み込めた時点で stderr に `prefill gemm: rocBLAS tuning enabled (...` が出ます。環境変数未設定・空文字なら診断は出ません。初期化や表検証に失敗した場合は、原因を含む `prefill gemm: ...; rocBLAS's default kernels run` 形式の stderr が出ます。

形状ごとに選んだ解や `default kernel; no row` のログ、および終了時の `tuned_launches=... fallbacks=...` 集計は、別変数 `STRATA_ROCBLAS_VERBOSE` が設定されている場合に stderr へ出ます（値が空文字でも設定されていれば有効）。1つの solution が3回拒否された場合の fallback 通知は verbose の有無にかかわらず出ます。

同梱 `setup.py` は、検出した GPU arch 用の `tools/hip/<arch>-rocblas-*.txt` がある場合、実行設定の `env` に `STRATA_ROCBLAS_TUNING` をそのディレクトリで設定します。エンジン側が実際の rocBLAS version に一致する表を選びます（`setup.py:7040-7047`）。表の生成・測定ツールは `tools/hip/tune_rocblas.cpp` ですが、そのベンチマーク結果自体は実装動作の根拠にしていません。

## 資料との照合

`docs/AMD_HIP.md:577-599,814-839` は、この表が `STRATA_HIP_PROMPT_F16=1` の FP16 prompt GEMM 向けであること、ファイルまたはディレクトリを指定できること、arch と rocBLAS build が一致しない表は拒否されること、未登録形状と実行拒否時は既定カーネルに戻ることを説明しています。実装と一致します。同資料には特定の RX 6900 XT 環境での prompt 処理時間も掲載されていますが、ハードウェア・入力条件に依存する測定値のため、この変数の一般的な性能効果としては扱いません。

## 根拠

- `src/prefill/gemm.cu:403-479`: HIP/rocBLAS ビルド条件、環境値の読み取り、空値判定、ファイル/ディレクトリ解決、arch/version 照合と初期化ログ。
- `src/prefill/rocblas_tuning.hpp:31-100,102-117`: 表形式の検査、行の重複確認、最寄り bucket（同距離なら小さい bucket）の選択。
- `src/prefill/gemm.cu:481-531,583-605,622-645`: 形状別 solution のキャッシュ、失敗時の既定カーネル fallback、GEMM state の作成箇所、拒否3回後の動作とログ。
- `src/prefill/gemm.cu:1049-1066,1202-1213`: `f16_io_ && beta == 0.0f` の経路でのみ `f16_inplace()` が呼ばれ、失敗・非該当時に通常の FP16 GEMM が走ること。
- `src/prefill/prefill.cpp:1381-1387,2173-2175`: prompt の FP16 I/O 判定と各 stage device 上での設定。
- `setup.py:7040-7047`: 対応する同梱表がある GPU arch で、実行設定へ表ディレクトリを設定する処理。
- `docs/AMD_HIP.md:577-599,814-839`: Strata の設計説明および記載された測定条件。
