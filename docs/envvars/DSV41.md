# `DSV41`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`DSV41` は Linux AMD (HIP) の配布ビルドスクリプト `packaging/build_hip_linux.sh` 専用の環境変数です。DeepSeek-V4.1 用の `strata-dsv41` エンジンを追加でビルドし、stage と engine package に含めるかを切り替えます。通常の `strata` 実行時設定ではありません。

## 値と判定

スクリプトは `${DSV41:-}` が空かどうかを見て既定値を設定し、以降は `DSV41` が文字列 `1` と完全一致する場合だけ有効と判定します（`packaging/build_hip_linux.sh:23-42,68`）。

| 呼び出し側の値 | `VARIANT=rx9070` | その他の `VARIANT` |
|---|---:|---:|
| 未設定または空文字 | 有効（既定値 `1`） | 無効（既定値 `0`） |
| `1` | 有効 | 有効 |
| `0`、`true`、`01`、その他の非空文字列 | 無効 | 無効 |

数値変換や trim、大文字小文字変換はありません。値が非空なら variant 既定値を適用せず、文字列 `1` 以外は無効です。スクリプトの `VARIANT` 自体は必須で、`DSV41` より前に検証されます（同 `:23,33-42`）。このスクリプトに `DSV41` を指定する CLI 引数や別設定ファイルはありません。

## 有効になる条件

- `DSV41=1` と判定され、かつ `VISION_ONLY` が未設定または空であること。`VISION_ONLY` に非空値があると engine ビルド全体がスキップされるため、`DSV41` が有効でも `strata-dsv41` は作られません（`packaging/build_hip_linux.sh:60-77,91`）。
- `DSV41=1` のとき、スクリプトは別の CMake build directory `OUT/bd` を再構成し、`-DSTRATA_BUILD_DSV41=ON` と `-DSTRATA_NATIVE_EXPERTS=ON` を渡して `strata-dsv41` をビルドします。`STRATA_BUILD_DSV41` はここで設定される CMake option であり、`DSV41` とは別の環境変数ではありません（同 `:68-73`; `CMakeLists.txt:934-935`）。
- `DSV41` が無効なら、この追加 build は行われません。通常の `strata` と vision reader の build/package 経路は引き続き進みます（`packaging/build_hip_linux.sh:60-68,78-90`）。

## 実行時の詳細

環境値はスクリプト開始時の shell expansion で一度参照され、その後は同じスクリプト内の shell 変数として使われます。プロセス実行中に環境を書き換えて再評価する箇所はありません（`packaging/build_hip_linux.sh:42`）。

有効時は CMake configure と `strata-dsv41` build のログをそれぞれ `OUT/cfg-dsv41.log`、`OUT/build-dsv41.log` にリダイレクトします。失敗時、`chk` が `OUT/build.status` に処理名と終了コード、`ABORT ... failed` を記録して終了コード 1 でスクリプトを終了します。build 成功後も、指定された `COMMIT` の build id がバイナリに含まれない場合、または実行可能ファイルがない場合は `ABORT` を記録して終了します。欠落時は `build-dsv41.log` の末尾 20 行も status file に追記されます（同 `:45-48,70-75`）。

有効時の `BUILD.json` には `"dsv41": true` を記録し、stage にバイナリをコピーし、ライブラリ収集対象に加え、package 作成時に `--require-dsv41` を渡します。無効時は `"dsv41": false` となり、これらの追加処理を行いません（同 `:94-108,121-124`）。ここで確認した範囲では、スクリプトの status file と各 build/package ログが主な観測先です。`DSV41` 自体を表示する専用の利用者向け警告や実行時ログはありません。

## 根拠

- 候補一覧での掲載: `docs/envvars/000_envvers.md:466`。
- 値の既定と判定、variant 条件: `packaging/build_hip_linux.sh:23-42`。
- `VISION_ONLY` と DeepSeek build 条件、CMake option の引き渡し: `packaging/build_hip_linux.sh:60-77`; option の定義は `CMakeLists.txt:934-935`。
- build 失敗・成果物確認: `packaging/build_hip_linux.sh:45-48,70-75`。
- manifest、stage、package への反映: `packaging/build_hip_linux.sh:94-108,121-124`。
- リポジトリ全体の完全一致検索では、このスクリプト以外に `DSV41` を環境から読む実装は見つかりませんでした。`CMakeLists.txt:2930-2935` の `DSV41` はコメント内の名前であり、環境値の読み取りではありません。
