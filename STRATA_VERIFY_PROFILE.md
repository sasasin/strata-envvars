# `STRATA_VERIFY_PROFILE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。CUDA/HIP 実装と SYCL 実装を確認。外部ライブラリの環境変数動作は対象外。

## 役割

Verifier が GPU 上の decode window の各 stage に時刻 stamp を記録し、GDN/QSA 層、VRAM hit、router、head などの平均時間を集計する診断用フックです。通常の `--serve` では `STRATA_DECODE_TIMING` と併用すると、リクエストごとの `strata decode GPU stages (ms/window):` ログに表示されます。これは GPU stage の計時で、全体の request latency を分解するものではありません。実装は `src/core/verify.cpp`、SYCL 版は `sycl/src/core/verify.cpp` にあります。

## 値と判定

Verifier の `init()` 内で `std::getenv("STRATA_VERIFY_PROFILE") != nullptr` を判定します。値の文字列や数値は parse しません。

| 環境変数の状態 | 結果 |
|---|---|
| 未設定 | profile 用の GPU 記録領域を作らず、計時しない |
| `1`、`0`、`false` など任意の非空文字列 | 設定ありとして計時を有効化 |
| 空文字列（例: `STRATA_VERIFY_PROFILE=`） | 設定ありとして計時を有効化 |
| profile 用 GPU 領域の確保失敗 | `prof_on_` を false に戻し、計時しない。ここでは専用の警告ログは出さない |

値の大文字小文字、空白、数値としての妥当性、値の変更は判定に影響しません。`init()` を呼んだ時点の環境を読み、その Verifier の `prof_on_` に保存します。初期化後に環境を変更しても、そのインスタンスの設定は変わりません。CUDA/HIP と SYCL の各実装に同じ存在判定があります。

根拠: `src/core/verify.cpp:711-716`, `sycl/src/core/verify.cpp:636-649`。

## 有効になる条件

- GPU の stage 計時は `prof_on_` が有効な window 実行で記録されます。通常の CUDA/HIP window では stamp lambda が group 0 の stage 境界で GPU stamp を書きます。SYCL 版も同様に stage stamp を記録します。
- report の出力には別の呼び出し条件があります。通常の serve request は `STRATA_DECODE_TIMING` も設定され、decode window が1つ以上ある場合に限り `profile_report()` を呼びます。`STRATA_DECODE_TIMING` も値の内容ではなく設定有無を static bool に保存します。したがって `STRATA_VERIFY_PROFILE` 単独では通常の serve request の GPU stage 行は出ません。
- batch 実行経路には `STRATA_DECODE_TIMING` の条件外で `profile_report()` を呼ぶ箇所があり、batch 集計時に `strata batch GPU stages...` として出力されます。
- pipelined window では pinned host buffer の確保に失敗すると、その経路の `fl_prof_` が false になり、profile が集計されず report は空になります。
- 同梱ツール `tools/batch_test.py` は、自身の環境に `PROF` が設定されている場合、起動する Engine に `STRATA_VERIFY_PROFILE=1` を渡します。`PROF` の値自体も空文字でなければ設定ありとして扱います（`os.environ.get("PROF")` の真偽判定）。

CUDA/HIP の `STRATA_VERIFY_PROFILE` は計測位置を通常と変えるため、一部の別最適化を無効化します。コード上、profiler 有効時は `STRATA_DF_BRANCH` の side stream、`STRATA_FUSE_CONVAB`、`STRATA_SH_STREAM` の fork、`STRATA_FUSE_WAIT`、`STRATA_FUSE_HITS` による経路が使われません。よって profiling 中の時間は、これらの経路を使う通常実行の性能測定値として扱えません。資料も stage profiler は decode を少し遅くするため比較用途として使うよう記しています。

根拠: `src/core/verify.cpp:846-848,870-871,1126-1128,1424-1426,1599-1602,1642-1645,3201-3205,3265-3273`; `sycl/src/core/verify.cpp:831-832,1293,1497,3585-3588,3665`; `src/program/generate.cpp:11283-11284,12180-12199`; batch 出力は `src/program/generate.cpp:9643-9645,9782-9790`、SYCL 版は `sycl/src/program/generate.cpp:8987-8989,9105-9107,11342-11358`; `tools/batch_test.py:95-98`。

## 実行時の詳細

CUDA/HIP では各 Verifier の `init()` が profile 領域を GPU に確保してゼロ初期化し、host 側 stamp 配列も用意します。window 実行中に stage 境界を GPU stamp として記録し、完了時に host 側へ読み戻して stage ごとの累計へ加算します。報告は GDN layers と QSA layers に分け、正の時間だけを `ms/window` で表示します。`profile_report()` は集計対象 window がない場合は空文字列を返し、報告を作ると累計と window 数をゼロに戻します。SYCL 版も device 側領域を確保して同じ形式の集計を行います。

通常の serve 経路は `STRATA_DECODE_TIMING` が設定され、かつ decode window が存在すれば各 stage verifier の report を stderr に出します。出力行の先頭は `strata decode GPU stages (ms/window):`、複数 stage 時の後続カードは `strata decode GPU stages, stage N (ms/window):` です。batch 経路の出力には `strata batch GPU stages` が使われます。`docs/DETAILS.md` は serve 起動時に `STRATA_DECODE_TIMING=1` と GPU 側の `STRATA_VERIFY_PROFILE=1` を設定する手順を案内しています。

根拠: `src/core/verify.cpp:711-716,1801-1824,2070-2073,2086-2115`; `sycl/src/core/verify.cpp:636-649,1642-1665`; `include/strata/core/verify.hpp:312-316`; `src/program/generate.cpp:12180-12199`; `docs/DETAILS.md:299-306`。

## 根拠

- 読み取りと領域確保: `src/core/verify.cpp:711-716`、`sycl/src/core/verify.cpp:636-649`。
- stamp の書き込みと profiler による実行経路の条件: `src/core/verify.cpp:846-848,870-871,1126-1128,1424-1426,1599-1602,1642-1645`。
- 集計、表示値、report ごとの reset: `src/core/verify.cpp:1801-1824,2070-2115`。SYCL 版 report: `sycl/src/core/verify.cpp:1642-1665`。
- serve / batch での report 呼び出しとログ文字列: `src/program/generate.cpp:12180-12199,9643-9645,9782-9790`、SYCL 版 `sycl/src/program/generate.cpp:8987-8989,9105-9107,11342-11358`。
- 同梱 batch test ツールから Engine への転送: `tools/batch_test.py:95-98`。
- 利用方法と計時オーバーヘッドに関する説明: `docs/DETAILS.md:299-306`。
