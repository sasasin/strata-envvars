# `DS4_TEST_IDLE_MS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 engine の独立実行ファイル `strata-dsv41` が、モデルのロードと説明表示を終えた後、serve または通常処理へ進む前に指定ミリ秒だけ待機します。コードコメントは用途を「人が入力するテスト」としています。サーバーではリクエストごとの待機ではなく、`serve()` を呼ぶ前の一度だけです。

この engine は `STRATA_BUILD_DSV41` が有効なときに作られる別 executable で、CMake 上の既定値は OFF です。従って通常の `strata` 実行ファイルの設定ではありません。

## 値と判定

| 環境変数の状態 | 待機 |
|---|---|
| 未設定 | なし |
| 設定あり | `std::atoi` が変換した整数値をミリ秒として `sleep_for` に渡す |

文字列全体の厳密な数値検証や範囲チェックはありません。`atoi` の規則により、先頭の空白と符号は許容され、数字列の後ろに文字があれば数字の部分が使われます。空文字や先頭から数値に変換できない文字列は `0` となり、待機時間は実質ゼロです。負数も clamp されず負の duration として渡されます。正の値はそのミリ秒数が待機時間になります。

## 有効になる条件

- 実行ファイルが `strata-dsv41` であること。CMake option `STRATA_BUILD_DSV41` の既定は OFF です。
- `--pack-info` のようにモデル load より前に終了する経路では、この変数の読み取り箇所に到達しません。
- `m.load()` が失敗した場合も待機前にエラー終了します。
- モデル load 後、`--serve` かどうか、および serve / score / profile / 推論などの後続処理を分岐する前に評価されます。

## 実行時の詳細

環境変数は `main` のモデル load 成功後に一度読み取られます。値を `std::atoi` で整数化し、`std::chrono::milliseconds` を作って `std::this_thread::sleep_for` に渡します。プロセス起動後の環境変更を再確認するループや子プロセスへの転送は、この箇所にはありません。専用のログ出力や警告もありません。

`docs/DETAILS.md` および `docs/` 内にこの変数の説明は見つかりませんでした。挙動の根拠は以下の実装です。

## 根拠

- `src/dsv41/ds4_main.cpp:1293-1301` — モデル load 成功後、説明表示をしてから一度待機し、その後 `serve()` または通常処理へ進みます。
- `src/dsv41/ds4_main.cpp:1279-1285` — `--pack-info` は model load を行うより前に return します。
- `CMakeLists.txt:797-800,809` — `strata-dsv41` は独立 executable で、`STRATA_BUILD_DSV41` option の既定が OFF であることを示します。
