# `STRATA_VERIFY_EAGER`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Intel GPU 向け SYCL backend の検証 window で command graph を使わず、window の処理本体を実行ごとに queue へ再投入する診断用スイッチです。主な用途は `STRATA_VERIFY_PROFILE` と組み合わせた段階別計時です。通常の graph 実行とは異なる経路であり、CUDA/HIP backend の環境変数処理には同名の読み取りがありません。

## 値と判定

値の parse はありません。`std::getenv("STRATA_VERIFY_EAGER") != nullptr`、すなわち環境変数が設定されているかだけを見ます。

| 状態 | 判定 |
|---|---|
| 未設定 | eager 無効。通常は graph の capture/replay 経路 |
| 空文字、`0`、`1`、その他の文字列 | eager 有効。値の内容・大文字小文字・数値形式は不問 |

環境変数は複数箇所で読み直されます。例外として `record_window()` 内の `static const bool eager` は初回呼び出し時の有無を保存し、以後再評価しません。capture と run 側の判定は関数呼び出しごとに `getenv()` を行うため、稼働中に環境を変更すると判定箇所間で不一致になり得ます。通常は起動前に設定してください。

根拠: `sycl/src/core/verify.cpp:826-833,1734-1742,1954-1959,2044-2045,2152-2155,2403-2406`。

## 有効になる条件

- Strata を Intel GPU 向け SYCL backend としてビルドし、その `Verifier` の通常の window 実行経路を通る場合に限られます。ルート CMake は `STRATA_ENABLE_SYCL` を別 backend として扱い、CUDA/HIP との同時有効化を拒否します（`CMakeLists.txt:12-21`）。
- `Verifier::capture()` では、変数が設定されていると graph capture を行わず成功を返します。`Verifier::run()` はその後、`record_window()` を通常 queue 上で実行します。変数が未設定なら graph を capture し、後続 window で graph を replay します（`sycl/src/core/verify.cpp:1734-1755,1996-2008,2152-2155`）。
- `STRATA_VERIFY_STEPPED` が有効な非 all-resident 経路では、通常は `capture_segments()` で層単位の graph segments を作り、run 中に段階的に投入します。EAGER が設定されると segment capture と stepped run を選ばず、window 全体を eager replay 経路に送ります（`sycl/src/core/verify.cpp:1734-1742,2041-2045,2152-2155`）。
- `run_slots()` / `run_slot_rows()` などのバッチ実行は別実装で、ここにある EAGER 分岐を通らず、事前 capture した `exec_bm_` を graph launch します（`sycl/src/core/verify.cpp:3098-3114`）。従って、その経路へ同じ効果を一般化できません。
- 段階別の時間表示は、別変数 `STRATA_VERIFY_PROFILE` が verifier 初期化時に設定され、計測領域の確保にも成功した場合に限られます。EAGER の stage stamp は各段階で queue を wait してホスト時計を記録し、window 完了時に `verify stages T=... (ms/window):...` を stderr に出します。PROFILE が無効ならこの計時・表示は行いません（`sycl/src/core/verify.cpp:636-650,826-833,2403-2406`）。

## 実行時の詳細

`record_window()` の eager 分岐では、PROFILE が有効で group 0 の場合、各 stage stamp 時に `cs->wait()` を行ってから `steady_clock` の時刻をホスト側配列 `prof_h_` に保存します。graph 経路の device stamp と異なり、段階ごとの待ちを含む計測になります。`collect_profile()` は EAGER 時には device 側 stamp のコピーを行わず、既に記録済みのホスト時計を集計します（`sycl/src/core/verify.cpp:826-833,1954-1959`）。

資料との照合では、`docs/INTEL.md:830-833` が当該 Arc カードで `STRATA_VERIFY_EAGER` を試したが採用しなかったと記録しています。また `docs/A770_SPEED_SPEC.md:716-732` は、同資料の current build で `STRATA_VERIFY_PROFILE=1` と EAGER を使うと `verify: layer 0 rang but its payload never arrived whole` で失敗し、EAGER の要求は 3/3 回失敗したと記録しています。同資料はこれを診断用 eager 経路の問題とし、通常の graph mode 推論には影響しないとの見解を記しています。これは資料に記録された特定 build の試行結果であり、この調査で実行・再測定した結果ではありません。

## 根拠

- EAGER 判定と eager stage stamp: `sycl/src/core/verify.cpp:826-833`。
- graph/segment capture の抑止と通常 window の直接実行: `sycl/src/core/verify.cpp:1687-1742,1996-2008,2041-2045,2152-2155`。
- プロファイル用ホスト時計の収集と表示: `sycl/src/core/verify.cpp:1954-1959,2403-2406`。
- バッチ window が別 graph 経路を使う箇所: `sycl/src/core/verify.cpp:3098-3114`。
- SYCL のビルド条件: `CMakeLists.txt:12-21`, `sycl/CMakeLists.txt:1-21`。
- 資料中の試行記録: `docs/INTEL.md:830-833`, `docs/A770_SPEED_SPEC.md:716-732`。
