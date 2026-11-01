# `STRATA_SELECT_LONG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `## main...origin/main` で、表示された未コミット変更はありません。外部ライブラリの環境変数は対象外。

## 役割

Verifier の QSA 検索で、コンテキスト位置がしきい値以上の window に長文脈用 select variant を選べるようにします。通常 variant の代わりに `qsa_block_scores_long` と `qsa_block_topk_long` を window graph に記録します。環境変数を有効にすると verifier は通常用と長文脈用の二組の window graph を用意し、各 window の `pos0 + T` によって選択します。値が有効でも、しきい値未満の window は通常 variant です。

これは CUDA の `STRATA_EXPERIMENTAL_SM60` build に含まれる機能です。該当する multi-CTA scratch がない build では警告を出して switch を無視します。

## 値と判定

`src/core/verify.cpp` は `std::getenv("STRATA_SELECT_LONG")` の戻り値が null でなく、先頭文字が `'1'` のときだけ有効とします。文字列全体の parse や比較は行いません。

| 値 | switch の判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF（値は設定済みだが、先頭文字が `'1'` ではない） |
| `1`, `10`, `1anything` | ON（先頭文字が `'1'`） |
| `0`, `true`, ` 1`, その他 `1` 以外で始まる文字列 | OFF |

数値変換、範囲検査、clamp、無効値の fallback はありません。判定結果は `select_long_on()` の関数内 `static const bool` にキャッシュされます。最初の呼び出し後にプロセス環境を書き換えても再判定されません。根拠: `src/core/verify.cpp:181-193`。

## 有効になる条件

- CUDA の `STRATA_EXPERIMENTAL_SM60` build であること。`qsa_topk_multi_scratch_ints()` は `!__HIPCC__ && STRATA_EXPERIMENTAL_SM60` のときだけ正の scratch サイズを返し、それ以外は 0 を返します。CMake のこの option は既定 OFF です（`CMakeLists.txt:236,280-284`; `src/kernels/cuda/qsa_select.cu:3077-3084`）。
- `STRATA_SELECT_LONG` が上表の ON 判定であること。
- window end position `pos0 + T` が `STRATA_SELECT_LONG_AT` 以上であること。`STRATA_SELECT_LONG_AT` は別環境変数で、未設定または空文字なら 65,536、空でない値は `std::atoll` で変換します。したがって `0` は常に該当し、負値もそのまま比較に使われます。文字列の先頭が数値として読めなければ `atoll` の結果 0 です。しきい値との比較は `>=` です（`src/core/verify.cpp:194-200,3013-3018,3076-3078`）。
- `capture_all()` は switch 有効時に `sel_long_` 0 と 1 の両方の window graph を capture します。通常の run、prelaunch、pipelined launch は window 位置から同じ variant を選びます（`src/core/verify.cpp:4815-4823,3013-3018,3076-3084,4870-4902`）。

HIP では scratch サイズが 0 のため、値が `1` で始まる場合でも `select_long_on()` は stderr に `strata verify: STRATA_SELECT_LONG=1 needs the CUDA build with STRATA_EXPERIMENTAL_SM60; ignored` を一度出して OFF をキャッシュします。通常の CUDA build でも同じ経路です。Metal の engine stub には「Metal では到達しない」と記載されています（`src/core/verify.cpp:183-192`; `metal/src/engine/stubs_0145.cpp:155`）。

## 実行時の詳細

Verifier の通常 window graph は、長文脈 variant の場合 `qsa_block_scores_long(...)` と `qsa_block_topk_long(...)` を呼び、そうでなければ `qsa_block_scores(...)` と `qsa_block_topk(...)` を呼びます。選択された long wrapper は適用条件を満たさない場合に通常 kernel 呼び出しへ fallback できます。scratch は switch 有効かつ scratch サイズ正の場合だけ arena に確保されます（`src/core/verify.cpp:965-968,1775-1787`; `src/kernels/cuda/qsa_select.cu:3086-3113`）。

長文脈 wrapper 内の実 kernel 選択は別環境変数にも依存します。`STRATA_TOPK_MULTI` は未設定・空文字なら compute capability major 6 で自動選択し、それ以外の GPU では OFF、非ゼロ値なら任意の CUDA card で ON、0 なら OFF です。`STRATA_TOPK_OLD` が設定されている場合や形状・capacity 条件に合わない場合も通常 top-k に fallback します（`src/kernels/cuda/qsa_select.cu:3031-3052,3086-3101`）。長文脈 score wrapper は `STRATA_SCORES_DX` が 0 なら DX kernel を使わず通常 scorer に fallback し、未設定時は compute capability 6.x、正値なら任意カードで DX を許可します。加えて形状と query 数の条件を満たす必要があります（同 `:2966-2989,3104-3113`）。従って `STRATA_SELECT_LONG=1` は二つの long wrapper を選択しますが、内部の各最適化 kernel が必ず実行されることまでは保証しません。

`select_long_on()` と `select_long_at()` はそれぞれ static cache されます。しきい値は最初の `select_long_at()` 呼び出し時に一度 `atoll` で評価され、window position 自体は run ごとに比較されます。CLI 引数による上書きはこの読み取り箇所にはありません。batch rows 用の記録経路は明示的に `sel_long_ = 0` とし、long variant を選びません（`src/core/verify.cpp:3755-3757`）。

ビルド条件を満たさない場合に Strata が出すのは上記の警告で、その後は通常 variant を使います。graph capture / launch の失敗時には verifier の既存エラー経路（例: `verify: begin capture failed`、`verify: launch: ...`）がありますが、これはこの環境変数専用の失敗ではありません（`src/core/verify.cpp:2590-2603,3134-3143`）。

## 根拠

- 候補一覧の名前は実装でも環境から読み取られています: `src/core/verify.cpp:181-193`。
- CUDA build option と macro 定義: `CMakeLists.txt:236,280-284`。
- scratch の build/backend 条件と long wrapper 内の fallback: `src/kernels/cuda/qsa_select.cu:2966-2989,3031-3101,3104-3113,3077-3084`。
- 既存資料 `docs/OLDER_GPUS.md:178-185` も CUDA `STRATA_EXPERIMENTAL_SM60`、既定しきい値 65,536、別変数による score/top-k 内部経路の制御、非対応 build での警告を説明しています。上記の値判定と分岐の詳細は調査対象 commit の実装を根拠にしています。
