# `STRATA_VERIFY_PROFILE_EVERY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL verifier の GPU stage profile を、何 window 分ためて stderr に表示するかを指定します。対象は実験的な SYCL backend です。共有の `src/core/verify.cpp` にはこの名前の読み取りがなく、CUDA/HIP の同機能をこの変数が制御する根拠はありません。

この変数だけではプロファイルを有効にしません。`STRATA_VERIFY_PROFILE` が設定され、プロファイル用 device memory の確保にも成功している必要があります。値は出力間隔にだけ作用し、検証計算や生成値の選択を変更する処理はありません。

## 値と判定

両読み取り箇所とも `std::atoll()` で文字列を `long long` に変換し、結果が `> 0` の場合だけ出力条件になります。未設定は `0`、空文字や数値変換できない文字列も `atoll` の結果が `0` となるため無効です。符号付き整数の先頭部分を読み、後続の非数値部分は変換値に含めません（例: `32junk` は 32、`-2` は負値なので無効、`0` は無効）。全体一致や値域チェック、上限 clamp はありません。

| 値の例 | 変換後 | 間隔出力 |
|---|---:|---|
| unset / 空文字 / `true` / `0` | 0 | しない |
| `32` / `32junk` | 32 | 32 window 以上たまったときに出力 |
| `-2` | -2 | しない |

巨大値の `atoll` 変換について、Strata はエラー検査や別の fallback を行いません。

## 有効になる条件

- ビルドが `STRATA_ENABLE_SYCL=ON` で構成された実験的 SYCL backend であること。トップレベル CMake はこの設定時に SYCL サブプロジェクトへ分岐し、通常の CUDA/HIP 構成とは分けています（`CMakeLists.txt:12-21`）。SYCL engine のソース一覧には `sycl/src/core/verify.cpp` が含まれます（`sycl/CMakeLists.txt:253-260`）。
- `STRATA_VERIFY_PROFILE` が unset ではないこと。空文字を含め、存在すれば profile を有効化しようとします。
- profile buffer の `sycl::malloc_device` が成功すること。失敗時は `prof_on_` が false に戻され、interval 値による出力もありません。
- 集計された window 数が正の interval 以上であること。

CLI 引数や設定ファイルによる `STRATA_VERIFY_PROFILE_EVERY` の上書きは見つかりません。実行中に process environment を変更しても、各読み取り箇所の初回評価後は反映されません。

## 実行時の詳細

環境変数は次の2経路で読みます。

1. `collect_profile()` 内では `prof_S_ > 0`、つまり batch window の集計後に読みます。正の interval 以上の window がたまると、`verify stages batch window of ... rows (ms/window over ..., GPU clock):...` 形式の行を stderr に出し、flush します。`profile_report()` が集計値と window counter をゼロに戻すため、その後も同じ interval ごとに集計行が出ます（`sycl/src/core/verify.cpp:2050-2070, 2098-2105`）。
2. 通常の `run()` 完了時は `prof_on_ && G == 1` の場合に GPU stage stamps を集計します。`STRATA_VERIFY_EAGER` が unset なら、正の interval 以上で `verify stages T=... (ms/window over ..., GPU clock):...` を stderr に出して flush します。ここでも出力後に集計値と counter がリセットされます（`sycl/src/core/verify.cpp:2522-2540`, `1738-1761`）。`G != 1` の window はこの経路の出力条件を満たしません。

各箇所の interval は別々の関数内 `static const long long` です。それぞれ、その経路で初めて評価された値を process 内に保持します。したがって変数の変更が反映されるのは、まだ初回評価されていないもう一方の経路だけです。両経路は `prof_windows_` の累積値を使い、閾値判定は `>=` です。

`STRATA_VERIFY_EAGER` が設定されている場合（値が空でも存在判定）は通常 `run()` 経路が host-clock の `verify stages T=... (ms/window):...` を window ごとに出すため、そこでは `STRATA_VERIFY_PROFILE_EVERY` の判定を通りません（`sycl/src/core/verify.cpp:2523-2539`）。batch 経路の `collect_profile()` 内 interval 判定は別途存在します。

プロファイル自体の初期化は verifier 構築時に行われます。`STRATA_VERIFY_PROFILE` の存在で `prof_on_` を設定し、device buffer を確保できた場合に stamp 用領域と host 側配列を初期化します（`sycl/src/core/verify.cpp:638-651`）。プロファイル出力は診断用であり、出力頻度によるログ以外の終了・失敗経路はこの変数からは発生しません。

## 根拠

- `sycl/src/core/verify.cpp:2050-2070` — batch profile の集計、interval の読み取り、stderr 出力。
- `sycl/src/core/verify.cpp:1738-1761,2098-2105` — profile report が平均を作って集計を reset し、window counter が増える処理。
- `sycl/src/core/verify.cpp:2522-2540` — 通常 window の出力条件、`STRATA_VERIFY_EAGER` 分岐、interval の読み取りと stderr 出力。
- `sycl/src/core/verify.cpp:638-651` — `STRATA_VERIFY_PROFILE` によるプロファイル有効化と buffer 確保。
- `CMakeLists.txt:12-21`; `sycl/CMakeLists.txt:253-260` — SYCL が別 backend として構成され、その engine に verifier 実装が入ること。
- `docs/DETAILS.md:303-305` — 既存資料は `STRATA_VERIFY_PROFILE` による GPU 側 profile を説明していますが、`STRATA_VERIFY_PROFILE_EVERY` の interval 仕様は説明していません。
