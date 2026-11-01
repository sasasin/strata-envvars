# `STRATA_MMVQ_IL_Q3K`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の interleaved small-batch matvec（MMVQ_IL）で、Q3_K（ggml type 11）用の行テーブルを通常の 2〜4 列経路と 5〜8 列経路で選べるようにするスイッチです。無効なら該当テーブル選択を 0 行にし、呼び出し側は標準 `native_mmvq` カーネルへ進みます。値は真偽値として parse されず、`il_env_on()` の先頭文字判定に使われます（`src/kernels/cuda/native_mmvq.cu:3768-3773,3832-3840,3852-3860`）。

## 値と判定

| 環境値 | 判定 | 備考 |
|---|---|---|
| 未設定 | 有効 | helper は `getenv()` が null のとき true を返す。既定で Q3_K の interleaved 行テーブルを許可する。 |
| 空文字 | 有効 | 設定値の先頭文字は `\0` であり `'0'` ではない。 |
| 先頭文字が `0` | 無効 | `0`, `0anything` など。数値変換ではない。 |
| それ以外 | 有効 | `1`, `true`, `false`, `anything` など。先頭文字だけを見るため `false` も有効。 |

空白除去、大文字小文字変換、文字列全体の検査、数値 parse、範囲検査はありません。無効値に対する警告や parse error もありません。`il_q3k_on()` の `static const bool` に結果を保存するため、初回評価後にプロセス環境を変更しても再読込しません（`src/kernels/cuda/native_mmvq.cu:3768-3773`）。

## 有効になる条件

値が有効でも、MMVQ_IL の全経路を有効化する変数ではありません。通常の呼び出しでは、CUDA ビルドであること、GPU アーキテクチャが対応すること、`g_multi_exact` が true であること、出力型がサポート対象であること、テーブルが shape に対して非ゼロを返すことが必要です。`native_mmvq_il_supported()` はこれらを確認し、type 11 も含む型集合に限定します。HIP 側は stub が常に unsupported を返し、通常の `native_mmvq` に委譲します（`src/kernels/cuda/native_mmvq.cu:3914-3927,3930-3934,3960-3973`）。

Q3_K の列数による差は次のとおりです。

- 2〜4 列: アーキテクチャ別または共有テーブルを使う通常経路で、この変数が無効なら type 11 は 0 行になります。候補テーブルは GPU compute capability に応じて選び、該当専用表がなければ共有表を使います。Q3_K の非ゼロ行がある表には少なくとも sm_61 と sm_86 の表が含まれます（`src/kernels/cuda/native_mmvq.cu:3641-3647,3651-3657,3852-3860`）。
- 5〜8 列: `STRATA_MMVQ_IL_WIDE` も有効（未設定または先頭文字が `0` 以外）であり、該当 compute capability に wide テーブルがあることが必要です。その上で本変数が無効なら Q3_K は 0 行です（`src/kernels/cuda/native_mmvq.cu:3832-3840`）。
- 1 列: 通常は専用の one-column 表を使い、本変数による type 11 の拒否判定を通りません。`STRATA_MMVQ_IL_T1` と対応アーキテクチャ表などが別途条件になります（`src/kernels/cuda/native_mmvq.cu:3844-3851`）。

優先関係として、共通の `STRATA_MMVQ_IL` が先に呼び出し側で MMVQ_IL 利用を抑止できます（未設定なら有効、先頭文字が `0` なら無効。`src/core/verify.cpp:175,1508-1517,1551-1560`）。また `STRATA_MMVQ_IL_ROWS` は 1〜4 列の表検索より先に適用されるため、type 11 の override 行があれば `STRATA_MMVQ_IL_Q3K=0` でもその行が選ばれます。5〜8 列では override を使わず wide 表へ進みます（`src/kernels/cuda/native_mmvq.cu:3795-3824,3832-3843`）。CLI 引数や設定ファイルによる値の上書きは、この変数の読み取り箇所にはありません。

## 実行時の詳細

`verify.cpp` の verify 経路が `native_mmvq_il_supported()` を shape / type ごとに問い合わせます。対応しない場合、通常の matvec 呼び出しにフォールバックします。interleaved カーネルを直接呼ばれた場合にも、関数冒頭で unsupported を再確認して `native_mmvq()` に委譲します。対応時のみ `IlQ3K` の行カーネルを launch し、launch check を行います（`src/core/verify.cpp:1499-1517,1551-1560,1791-1798,2452-2462`; `src/kernels/cuda/native_mmvq.cu:3936-3957`）。

この変数単独によるログ、警告、終了コード変更の経路はありません。テーブルが 0 行になった場合は unsupported として標準 `native_mmvq` にフォールバックします。カーネル launch の失敗は通常の `launch_check()` 経路ですが、本変数の無効値に由来する専用エラーではありません（`src/kernels/cuda/native_mmvq.cu:3938-3940,3950-3957`）。

## 根拠

- `src/kernels/cuda/native_mmvq.cu:3768-3773` — 環境値の取得、既定値、先頭文字判定、static cache。
- `src/kernels/cuda/native_mmvq.cu:3830-3860` — 列数別のテーブル検索と Q3_K 制御。
- `src/kernels/cuda/native_mmvq.cu:3930-3957,3960-3973` — 対応判定、interleaved launch、fallback、HIP stub。
- `src/core/verify.cpp:175,1499-1517,1551-1560,1791-1798,2452-2462` — verify 呼び出し側と共通 `STRATA_MMVQ_IL` gate。
- 候補索引 `docs/envvars/000_envvers.md:1089` に名前があります。索引の候補記載に加え、上記の Strata 所有ソースで環境からの読み取りを確認しました。
