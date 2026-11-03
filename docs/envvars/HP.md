# `HP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`HP` は Linux AMD/HIP 向けのビルド・パッケージ作成スクリプトが使う、ROCm devel SDK のルートパスです。通常の Strata 実行ファイルが読む実行時設定ではありません。`packaging/build_hip_linux.sh`、`packaging/build_dsv41_hip_linux.sh`、`packaging/build_split_hip.sh` が値を必須入力として受け取り、HIP コンパイラや ROCm の検索先を組み立てます（各スクリプトの変数入力と利用: `packaging/build_hip_linux.sh:11,26-28,53-57`、`packaging/build_dsv41_hip_linux.sh:8,18-20,39-42`、`packaging/build_split_hip.sh:10,20-28,32-34`）。

## 値と判定

| スクリプト | 未設定 | 空文字 | 設定値 |
|---|---|---|---|
| Linux HIP エンジン／reader パッケージ | `${HP:?HP=<ROCm devel root>}` でエラー終了 | 同じくエラー終了 | 値をパスのルートとして使用 |
| DeepSeek-V4.1 HIP パッケージ | 同上 | 同上 | 同上 |
| split HIP エンジンのビルド | 同上 | 同上 | 同上 |

これらのスクリプトは `set -u`（split は `set -eu`）で動き、`${HP:?…}` は未設定または null（空文字）のとき展開エラーにします。非空値について形式・存在・ディレクトリ妥当性の事前検証や変換、数値境界判定はありません。値を `$HP/…` のパスに連結し、CMake の HIP コンパイラ・ROCm root・prefix/flags に渡します（`packaging/build_hip_linux.sh:22,26,53-57`、`packaging/build_dsv41_hip_linux.sh:14,18,39-42,46-48`、`packaging/build_split_hip.sh:17,20,26-34`）。

`CORE` と `LIBW` はそれぞれ別に設定されていなければ `HP` が既定値です。明示された `CORE` / `LIBW` はそれらの検索先・データ配置に使われますが、`HP` は引き続きコンパイラ、ROCm root、HIP flags、devel ライブラリ検索などに使われます（`packaging/build_hip_linux.sh:26-28,56-57,98-103`、`packaging/build_dsv41_hip_linux.sh:18-20,41-42,66-68`、`packaging/build_split_hip.sh:20-21,26-34`）。

## 有効になる条件

この変数を読むのは上記の Linux HIP packaging/build スクリプトを実行した場合です。ビルド済みの Strata CLI、Python サーバー、通常のモデル実行に対する条件や効果はありません。`build_hip_linux.sh` はエンジンと HIP image reader を作り、設定によって DSV41 も作成します。別の `build_dsv41_hip_linux.sh` は DSV41 パッケージを作り、`build_split_hip.sh` は split HIP バイナリをビルドします（`packaging/build_hip_linux.sh:2-3,60-90`、`packaging/build_dsv41_hip_linux.sh:2-4,43-52`、`packaging/build_split_hip.sh:2-8,29-38`）。

各スクリプトは `HP` から `ROCM_PATH` と `HIP_PATH` を export し、split ビルドではさらに `$HP/bin` を `PATH` の先頭に加えます。CMake にも HIP compiler/root と ROCm flags を明示して渡します（`packaging/build_hip_linux.sh:53-57`、`packaging/build_dsv41_hip_linux.sh:39-42`、`packaging/build_split_hip.sh:26-34`）。これはビルド工程へのパス設定です。これらのスクリプトから、同名 `HP` を生成後の Strata プロセスに対する実行時設定として渡す処理は確認できません。

## 実行時の詳細

`HP` は各シェルスクリプトの初期化時に一度変数へ代入されます。要求値がなければ、後続処理に入る前の必須展開でスクリプトが終了します。パス自体が間違っている場合の独自診断はなく、CMake や後続の収集・stage 処理の成否に現れます。エンジンと DSV41 のスクリプトは CMake configure/build の出力を `$OUT` 配下のログへリダイレクトし、`chk` が失敗コードを `build.status` に記録して `ABORT … failed (rc=…)` を追記して終了します（`packaging/build_hip_linux.sh:45-48,61-66`、`packaging/build_dsv41_hip_linux.sh:33-35,46-51`）。`build_split_hip.sh` は configure/build の出力をリダイレクトせず、失敗時に終了します（`packaging/build_split_hip.sh:29-38`）。

値の再読み込み、static cache、リクエスト単位の評価はありません。ビルド時に環境から得た値を CMake 引数や `stage_tuning.py --rocm` に使います。エンジンパッケージのスクリプトはライブラリを `$HP/lib` 等から検索し、チューニング表の stage にも `HP` を渡します（`packaging/build_hip_linux.sh:98-103,116-117`、`packaging/build_dsv41_hip_linux.sh:66-75`）。

## 根拠

- `packaging/build_hip_linux.sh:11,22-28,53-57,98-117`: Linux HIP エンジンパッケージの入力、既定、HIP 設定、ライブラリ収集、チューニング表処理。
- `packaging/build_dsv41_hip_linux.sh:8,14-20,39-48,66-75`: DSV41 パッケージでの同じ入力と利用。
- `packaging/build_split_hip.sh:10,17-34`: split HIP ビルドの入力、必須判定、HIP 環境と CMake 設定。
- 候補索引 `docs/envvars/000_envvers.md:671` に `HP` は載っています。候補名の完全一致参照を調べたところ、環境入力として使う Strata 所有コードはこの 3 つの packaging スクリプトでした。C++/Python の Strata 実行時 `getenv` / `os.environ` による読み取りは見つかりませんでした。
- ほかに `tests/dsv41/build_dq_test.sh:47-64` にシェル変数 `HP` がありますが、これは `HIP_ROOT` から作るテスト用のローカル変数で、環境変数 `HP` の読み取りではありません。ベンチマーク結果内にも同名のローカル配列名がありますが、環境変数としての参照ではありません。
- `packaging/README.md:32` は Linux HIP engine package のビルド入口として `packaging/build_hip_linux.sh` を示しています。測定値はこの変数の役割を説明する根拠にしていません。
