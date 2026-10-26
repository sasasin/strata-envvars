# `DS4_AHEAD_ORDER`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 用 DSV41 エンジンの非 VRAM expert を CPU lane で計算するとき、router lookahead で先読み要求された expert を先に計算するかを切り替えます。先読み順を有効にすると、先に要求された expert の計算中に、まだ要求されていない expert のファイル読み込みが進む時間を作ります。重み、expert の選択、出力の集約方法はこの変数では変えず、CPU lane が `cpu_experts()` に渡す処理順を変えます（`src/dsv41/ds4_model.cu:6572-6590`）。

## 値と判定

値は `std::atoi()` で整数に変換し、結果が 0 以外なら有効です。文字列全体の検証はありません。

| 環境変数値 | `ahead_order` | 判定 |
|---|---:|---|
| 未設定 | true | 既定で有効 |
| `0`、空文字、数字で始まらない文字列 | false | 無効（`atoi()` の結果が 0） |
| `1`、`-1`、`2` など、整数として 0 以外になる値 | true | 有効 |
| `1x`、` 1` など、`atoi()` が先頭部分から 0 以外を変換できる文字列 | true | 有効。末尾は検査しない |

読み取りは `Model::Impl` の `ahead_order` メンバー初期化時に行われます。モデル生成後に環境変数を変更しても、そのモデルの値は更新されません。ソース内に `DS4_AHEAD_ORDER` の他の読み取り箇所はありません（`src/dsv41/ds4_model.cu:997`）。

## 有効になる条件

値が有効でも、実際に順序が変わるのは decode の CPU lane が処理中の layer について、先読み情報が現在の request sequence と一致し、CPU 側 expert entry が複数あり、entry 数が `kWin * kPicks` 以下の場合だけです。先読み情報がない場合や CPU 側 entry が 0 または 1 個の場合、この分岐は並べ替えをしません（`src/dsv41/ds4_model.cu:6473-6475,6576-6587`）。

先読み情報は DSV41 の lookahead が要求を発行した場合に限られます。lookahead の段数は `DS4_AHEAD` に依存し、対象 layer は同じ device / MTP 区分で MXFP4、router gate があり、expert 数が 1024 以下などの条件を満たす必要があります。ファイルから読む expert がない layer も対象になりません（`src/dsv41/ds4_model.cu:6398-6409,6411-6447,9051-9069`）。`DS4_AHEAD` が無効なら先読み要求が作られず、`DS4_AHEAD_ORDER` を有効にしても順序変更は発生しません。SSD store 初期化時は `DS4_AHEAD` が未設定だと `ahead_mode` を 0 にします（`src/dsv41/ds4_model.cu:4716-4718`）。

## 実行時の詳細

先読み要求がある layer では、実装は CPU 側 expert entry を2群に分けます。既に RAM tier にあるか、先読みで prefetch 要求済みの expert（`!file_read(...) || ahead_fl[e] & 8`）を先に並べ、残りを後に並べます。その index 配列を `cpu_experts()` に渡します。entry の出力スロットは並べ替えとは別に保持され、後続の和はスロット順に行われます（`src/dsv41/ds4_model.cu:6572-6602`）。

この分岐自身はログを出しません。コードコメントは、先読み済み expert を先に計算している間に SSD からの読み込み時間を与える意図と、スロットおよび和が変わらないことを説明しています（`src/dsv41/ds4_model.cu:6572-6574`）。`docs/DETAILS.md` にはこの変数に関する個別の説明や測定値は見当たらず、性能向上はここでは断定しません。

## 根拠

- `src/dsv41/ds4_model.cu:996-1001` — `DS4_AHEAD_ORDER` の変換、既定値、lookahead 状態のメンバー。
- `src/dsv41/ds4_model.cu:6394-6447` — file-backed expert の判定、先読み対象条件、prefetch 要求と状態フラグ。
- `src/dsv41/ds4_model.cu:4716-4718,2785-2794` — SSD store 経路での `DS4_AHEAD` 既定無効化と prefetch thread の開始条件。
- `src/dsv41/ds4_model.cu:6473-6475,6555-6556,6572-6602` — request に対応する先読み順の選択、並べ替え、expert 計算と結果集約。
- `src/dsv41/ds4_model.cu:9051-9069` — decode の非同期経路で次 layer の router lookahead を発行する条件。
