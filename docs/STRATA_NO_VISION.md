# `STRATA_NO_VISION`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Windows 向け HIP エンジンのビルドスクリプト `tools/hip/build_windows.bat` で、画像入力用の補助プログラム2本をビルドし、配布 zip に含めるかどうかを切り替えます。Strata エンジンの実行時挙動を切り替える環境変数ではありません。

## 値と判定

スクリプトは `if not "%STRATA_NO_VISION%"=="1"` で文字列を比較します。値を数値や真偽値として parse せず、空白除去や部分一致もしません。

| 環境変数の値 | 処理 |
|---|---|
| 未設定または空文字 | `"1"` と一致しないため、画像リーダーをビルドして zip に渡す |
| `1` | 画像リーダー2本のビルドをスキップし、zip に渡さない |
| その他（例: `0`, `true`, `01`, `1 `） | `"1"` と一致しないため、ビルドして zip に渡す |

判定はスクリプトの vision 段階に到達したときに行われます。値を保存するキャッシュや、別の設定値との優先順位はありません。

## 有効になる条件

- `tools/hip/build_windows.bat` を実行した場合だけ参照されます。HIP backend の Windows ビルド経路に限られ、他 OS のビルドや実行中の `strata.exe` では読み取られません。
- `tests` 引数の有無にかかわらず、同じ vision 条件分岐を通ります。`tests` は先行するエンジンのビルド対象を変えますが、この変数の判定を変えません。
- この変数を `1` にしても、先行する ROCm セットアップや `strata.exe` / `strata-device.exe` のビルドはスキップされず、最後の `package_windows.py` 呼び出しも行われます。

## 実行時の詳細

変数が `1` 以外なら、バッチは `tools/vision` の CMake 構成を使って CPU 版 `strata-vision.exe` と HIP GPU 版 `strata-vision-hip.exe` をビルドし、`package_windows.py` に `--vision-cpu` と `--vision-hip` を渡します。`STRATA_GGML_DIR` が設定されていればその llama.cpp checkout を使い、未設定ならエンジンのビルドディレクトリ内の取得済みソースを使います。vision 用の `tools/mtmd` が見つからない場合はエラーで終了します。

値が `1` なら上記の vision 構成・ビルド・引数設定ブロック全体を通らず、vision 引数なしで zip 作成に進みます。パッケージャーは指定された vision 実行ファイルだけを stage にコピーし、`BUILD.json` の `vision` を既定の `none` のままにします。したがって、この条件では zip に画像リーダーは含まれません。

## 根拠

- `tools/hip/build_windows.bat:13-23` — 変数の説明と任意設定としての記載。
- `tools/hip/build_windows.bat:32-34,69-85` — `tests` 判定、エンジン本体の構成・ビルド。
- `tools/hip/build_windows.bat:87-115` — vision ビルド条件、必要な llama.cpp の確認、パッケージャーへの引数。
- `tools/hip/package_windows.py:89-103,175-181` — vision 引数がない場合はリーダーをコピーせず、manifest の vision が `none` となる処理。
- `packaging/ENGINE-COMPONENT.md:101` — unset の場合に2本の reader をビルドするというパッケージ経路の補足。
