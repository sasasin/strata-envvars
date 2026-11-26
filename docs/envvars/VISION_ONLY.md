# `VISION_ONLY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`tools/packaging/build_hip_linux.sh` をビジョン読取ツールだけのビルドに切り替える、Linux AMD HIP パッケージ作成スクリプト向けの環境変数である。非空にすると `strata` エンジンの configure/build を省き、CPU 用 `strata-vision` と HIP 用 `strata-vision-hip` をビルドした後、エンジン component の stage・package 処理へ進まず終了する。アプリケーションや `strata` 実行時の設定ではない（`tools/packaging/build_hip_linux.sh:2-5, 60-85`）。

## 値と判定

スクリプトは `set -u` の下で `${VISION_ONLY:-}` をシェル展開し、空文字列との比較および `-n` 判定を行う。文字列の値は parse しない。未設定と明示的な空文字は同じ扱いで、エンジン工程を実行し、読者のビルド後も通常の packaging 工程へ続く。空でない任意の値が有効であり、`1`、`true`、`0`、`false`、`0anything` もすべて reader-only 経路を選ぶ。大文字小文字、空白、数値としての妥当性は検査しない（`tools/packaging/build_hip_linux.sh:21, 60, 85`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| このスクリプトの実行 | エンジンも構築し、その後 reader と package を処理 | 空文字以外すべて（例: `1`, `true`, `0`, `false`, `0anything`, ` `） | なし。空文字 `VISION_ONLY=` は未設定と同じ |

## 有効になる条件

- `tools/packaging/build_hip_linux.sh` を実行する場合に限り評価される。スクリプトは Linux AMD HIP エンジンパッケージ用と記載されている（`tools/packaging/build_hip_linux.sh:1-5`）。
- `VISION_ONLY` が非空でも、スクリプト前半で必須としている `VARIANT` と `HP` などの設定、ROCm 開発環境、および reader の configure/build が必要である。変数はこれらを代替しない（`tools/packaging/build_hip_linux.sh:22-32, 52-59, 71-84`）。
- ビルド対象は CPU reader `strata-vision` と HIP reader `strata-vision-hip`。このモードでは `strata` エンジン本体を作らないため、その後の engine component/package は作られない（`tools/packaging/build_hip_linux.sh:60-85`）。

## 実行時の詳細

スクリプト実行時、エンジンの CMake configure/build の直前に値を検査する。非空ならそのブロックを丸ごと飛ばし、続く CPU reader と HIP reader の configure/build と実行ファイル確認を行う。reader の確認後、同じ変数を再評価し、非空なら `build.status` に `VISION-DONE` と時刻を追記して `exit 0` する。したがって stage directory 作成、ライブラリ収集、`BUILD.json` 作成、package 処理には到達しない（`tools/packaging/build_hip_linux.sh:44-47, 60-85, 86-140`）。

読み取りはこのスクリプトの実行中に行われ、プロセス内で値を保存する cache はない。CLI 引数や設定ファイルによる上書きはなく、同じシェル環境変数を二度判定する。実行中に環境を書き換える処理はスクリプト内にない。reader のビルド工程が失敗すれば `chk` の検査により `ABORT ... failed` を `build.status` に記録して終了する（`tools/packaging/build_hip_linux.sh:45-47, 75-85`）。

## ログと測定値

reader の確認後に成功経路を通ると、`$OUT/build.status` に `VISION-DONE <時刻>` が記録され、スクリプトは終了コード `0` で終了する。これはスクリプト自身が出力ファイルに記録するステータスである。失敗時は `chk` が `ABORT <工程> failed (rc=<終了コード>)` を同ファイルへ追記し、終了コード `1` で終了する（`tools/packaging/build_hip_linux.sh:44-47, 75-85`）。対象変数について Strata 資料に記載された測定値はない。

## 根拠

- `tools/packaging/build_hip_linux.sh:1-17` — 対象スクリプトと変数の説明。
- `tools/packaging/build_hip_linux.sh:21-32` — シェル設定およびスクリプト実行に必要な設定。
- `tools/packaging/build_hip_linux.sh:44-47` — status 記録と工程失敗時の終了処理。
- `tools/packaging/build_hip_linux.sh:60-85` — 変数の両判定、エンジン工程の省略、reader ビルド、reader-only 終了。
- `tools/packaging/build_hip_linux.sh:86-140` — reader-only 終了後に続く通常の stage/package 工程。
