# `NO_PACKAGE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`tools/packaging/build_hip_linux.sh` の HIP Linux エンジン・コンポーネント作成工程で、ステージ用ディレクトリを完成させた後にパッケージ化へ進まず、正常終了するための開発用制御変数です。Strata engine の実行時動作を変更する環境変数ではありません。同スクリプトは `strata` と2つの vision reader、収集済みライブラリ、必要な tuning data などを `$OUT/stage` に準備し、この変数が非空ならそこで止まります（`tools/packaging/build_hip_linux.sh:86-131`）。

## 値と判定

スクリプトは `${NO_PACKAGE:-}` を `-n` で検査します。未設定と空文字はどちらも空に展開されて通常のパッケージ工程へ進みます。それ以外は内容を解釈せず、非空であれば停止します。したがって `1` だけでなく `0`、`false`、空白だけの値も停止条件です。数値変換・大文字小文字の比較・範囲判定はありません（`tools/packaging/build_hip_linux.sh:131`）。

| 条件 | unset | 停止する値 | 停止しない値 |
|---|---|---|---|
| 同スクリプトがステージ完了まで到達 | パッケージ化を続行 | `1`、`0`、`false`、空白など任意の非空文字列 | 空文字 |
| `VISION_ONLY` が非空 | `NO_PACKAGE` の判定箇所に到達せず `VISION-DONE` で終了 | 同左 | 同左 |

## 有効になる条件

- `tools/packaging/build_hip_linux.sh` を実行する経路に限られます。スクリプトは HIP を有効、CUDA を無効にして engine を構成し、Linux AMD 向けの package を組み立てます（`tools/packaging/build_hip_linux.sh:60-65, 79-80, 134-135`）。通常の Strata 実行プロセスがこの変数を読む箇所は確認できません。
- 非空の `VISION_ONLY` がある場合、同スクリプトは CPU/GPU vision reader のビルド後、ステージを作る前に `VISION-DONE` を記録して終了します。そのため `NO_PACKAGE` は評価されません（`tools/packaging/build_hip_linux.sh:71-85`）。
- `NO_PACKAGE` に CLI 引数や別の環境変数による上書き・優先順位はありません。スクリプト内では値の内容でなく設定文字列が空かどうかだけを判定します（`tools/packaging/build_hip_linux.sh:5-17, 131`）。
- ステージ準備より前の build、収集、shape 検査、または tuning table 作成に失敗した場合は、この判定には到達せず、各工程のエラー経路で終了します（`tools/packaging/build_hip_linux.sh:63-84, 127-131`）。

## 実行時の詳細

スクリプトは `$OUT/stage` を作り直し、`BUILD.json` を記録し、依存ライブラリや kernel data、実行ファイル、任意の kpack、tuning table をステージします（`tools/packaging/build_hip_linux.sh:86-130`）。その後 `NO_PACKAGE` を一度評価し、非空なら `$OUT/build.status` に `STAGE-DONE` と時刻を書き、終了コード 0 でその場で終了します。従って `package_engine.py`、`binary_deps.py`、`BUILD-DONE` の記録は実行されません（`tools/packaging/build_hip_linux.sh:44-47, 131-141`）。

読み取りはステージ工程の末尾にある一回の shell 展開で、プロセス開始時の値をキャッシュする処理はありません。スクリプトがコマンドライン引数から値を受け取る経路もありません。非空で終了する分岐は `$OUT/components` の削除・再作成より前にあるため、既存の `$OUT/components` があってもこの分岐では触れられません（`tools/packaging/build_hip_linux.sh:131-135`）。

## ログと測定値

非空の場合に観測できる明示的な記録は `$OUT/build.status` の `STAGE-DONE <時刻>` で、プロセスは成功終了します。専用の警告・エラー出力はありません。空または未設定の場合は package 作成へ進み、成功すれば最後に同ファイルへ `BUILD-DONE <時刻>` が記録されます（`tools/packaging/build_hip_linux.sh:44-47, 131-141`）。この変数に関する測定値はありません。

## 根拠

- `tools/packaging/build_hip_linux.sh:5-17` — スクリプトの目的と `NO_PACKAGE=1` の説明。
- `tools/packaging/build_hip_linux.sh:60-85` — engine / vision reader の build と `VISION_ONLY` の早期終了。
- `tools/packaging/build_hip_linux.sh:86-130` — stage の準備、検査、tuning table 作成。
- `tools/packaging/build_hip_linux.sh:131-141` — 値の判定、package 処理、最終ステータス。
