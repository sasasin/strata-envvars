# `BUILD_JOBS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Windows 向けの 2 つの packaging バッチが、CMake のビルド並列数として `BUILD_JOBS` を `cmake --build -j` に渡します。対象は `strata-vision` のビルドと `strata-dsv41` のビルドです。Strata エンジンの実行時設定ではありません。

## 値と判定

どちらのバッチも、値を整数などへ変換せず、文字列としてコマンド行に展開します。

| 状態 | `packaging/build_vision_windows.bat` | `packaging/build_dsv41_windows.bat` |
|---|---|---|
| 未設定 | `BUILD_JOBS=4` を設定 | `BUILD_JOBS=4` を設定 |
| 空文字 | `if not defined` により既定値 `4` を設定 | `if "%BUILD_JOBS%"==""` により既定値 `4` を設定 |
| 非空の値 | 値をそのまま `-j` の後ろへ展開 | 値をそのまま `-j` の後ろへ展開 |

したがって既定値は両スクリプトで `4` です。非空値の数値妥当性、正負、上限・下限を Strata のバッチは検査・補正しません。値が不正な場合の具体的な解釈は、このバッチから起動される CMake 側に委ねられます。

## 有効になる条件

Windows で該当するバッチを実行し、スクリプトが `cmake --build` の行まで進んだ場合に使われます。Vision バッチは CUDA 12 / CUDA 13 の variant を受け、`strata-vision` をビルドします。DSV41 バッチは `strata-dsv41` をビルドします。値を読む Strata の C++ 実行ファイルや通常の推論経路は確認できません。

## 実行時の詳細

両バッチは `setlocal` を使い、未設定または空の変数に限ってローカルに既定値 `4` を設定します。非空の値はそのまま `-j` の引数に展開されます。別の Strata CLI 引数による優先順位や、実行中の再読み取り・キャッシュはありません。値が適用されるのは各バッチのビルドコマンドだけです。

Vision バッチは `cmake --build ... -j %BUILD_JOBS%` が失敗すると `|| exit /b 1` で終了します。DSV41 バッチは `start /wait` で同じく `-j %BUILD_JOBS%` を実行し、その後 `errorlevel 1` なら終了コード 1 で終了します。いずれもビルドコマンドの出力を独自に抑止・変換する指定はありません。

## 根拠

- `packaging/build_vision_windows.bat:20,26-36,57-64` — バッチのローカル環境、CUDA variant ごとの処理、未設定値への既定値設定、`strata-vision` のビルドと失敗時終了。
- `packaging/build_dsv41_windows.bat:8-16,19-27` — ローカル環境、空値への既定値設定、`strata-dsv41` のビルドと `errorlevel` による失敗終了。
- 候補一覧には `000_envvers.md:55` に記載があります。Strata リポジトリ内の完全一致参照は上記 2 バッチに限られ、C++ / Python の実行時読み取りは確認できませんでした。
