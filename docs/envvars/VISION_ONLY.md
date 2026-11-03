# `VISION_ONLY`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

`packaging/build_hip_linux.sh` の Linux HIP 向けビルドを vision reader 2つだけに限定します。通常の `strata` 実行時に値を読むコードはなく、Strata の実行時設定ではありません。このスクリプトでは engine と package の工程を省き、CPU reader `strata-vision` と HIP reader `strata-vision-hip` をビルドして終了します。

## 値と判定

スクリプトは `${VISION_ONLY:-}` の空文字判定と非空文字判定を使います。数値や文字列の parse はしません。

| 環境の状態 | 判定と動作 |
|---|---|
| 未設定 | 空として扱う。engine（設定により `strata-dsv41` も）をビルドし、reader 2つと package も通常どおり処理する |
| 空文字 | 未設定と同じ。engine と通常の後段工程を実行する |
| 空でない任意の値 | 有効。例: `1`、`0`、`false`。engine のビルドと stage/package を省略し、reader 2つのビルド後に終了する |

空でない値の内容、大文字小文字、数値としての妥当性、境界値は検査されません。`VISION_ONLY=0` も有効です。CLI 引数や他の環境変数でこの判定を上書きする経路はありません。

## 有効になる条件

この変数が参照されるのは `packaging/build_hip_linux.sh` を実行した場合だけです。同スクリプトは Linux AMD (HIP) 用と説明されています。OS/backend を判定して変数を無効化する分岐はありませんが、実際のビルドには Linux、HIP/ROCm、`VARIANT`、`LLAMA`、`HP` などスクリプトが要求する設定が必要です。

非空時も CPU reader と HIP reader の設定・ビルドは省略されません。`VARIANT` に応じた `ARCHS`、`VISION_HIP_DEFS` などの reader ビルド設定は引き続き使われます。`DSV41` は engine 工程内でのみ参照されるため、`VISION_ONLY` が非空のとき DeepSeek engine もビルドされません。通常の package 手順にある `NO_PACKAGE` は `VISION_ONLY` の判定を置き換えません。

## 実行時の詳細

スクリプトは engine 工程の直前に `${VISION_ONLY:-}` が空かを調べ、空なら CMake で HIP engine を構成・ビルドします。非空ならこの工程全体を飛ばします。いずれの場合も CPU reader と HIP reader を順に構成・ビルドし、実行ファイルの存在を確認します。reader の設定・ビルドや実行ファイル確認に失敗すると `chk` または明示的な失敗分岐が `build.status` に失敗を記録して非ゼロ終了します。したがって `VISION_ONLY` が非空でも reader のビルド失敗は成功扱いになりません。

2つの reader が成功すると、非空時は `build.status` に `VISION-DONE` と時刻を記録して終了コード 0 で終了します。この分岐より後にある stage ディレクトリの作成、bundle 構成、package 作成は実行されません。スクリプトのログ関数 `st` は `build.status` に追記し、通常の CMake 出力は各ログファイルへリダイレクトされます。

値はシェルスクリプト実行中に判定されます。常駐プロセスやリクエスト単位の cache はありません。スクリプトから `strata` 実行ファイルへ `VISION_ONLY` を転送して挙動を変える処理も確認できません。

## 根拠

- 候補名の索引掲載: `docs/envvars/000_envvers.md:2145`。
- 全参照は `packaging/build_hip_linux.sh` 内のコメントと2つの判定だけ。値の非空判定による engine 工程の選択: `packaging/build_hip_linux.sh:60-77`。
- CPU/HIP reader のビルドと成功確認: `packaging/build_hip_linux.sh:78-90`。
- 非空時の `VISION-DONE` 記録と早期終了: `packaging/build_hip_linux.sh:91-92`。後続に stage/package の処理が続く: `packaging/build_hip_linux.sh:92-125`。
- `st` の記録先と失敗時の終了処理: `packaging/build_hip_linux.sh:45-48`。
- スクリプトの HIP Linux 向け用途と環境設定の説明: `packaging/build_hip_linux.sh:1-18`。Linux HIP package の構成説明: `packaging/ENGINE-COMPONENT.md:112-113`。
