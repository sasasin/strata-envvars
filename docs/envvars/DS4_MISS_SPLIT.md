# `DS4_MISS_SPLIT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1 の CPU lane が処理する expert のうち、ファイルから読み込み中の expert と、すでに読み込み可能な expert の計算順を切り替えます。既定では読み込み済み分を先に計算し、その後は読み込みが完了した expert から計算します。`DS4_MISS_SPLIT=0` は全件の読み込みを待ってから従来の順序で計算します。これは CUDA/HIP の一般設定ではなく、`src/dsv41/ds4_model.cu` の CPU lane にある engine 内の設定です。

## 値と判定

値は `std::atoi` で変換され、結果が 0 かどうかで判定されます。

| 環境変数の状態 | `split` |
|---|---|
| 未設定 | 有効（既定） |
| 設定値を `atoi` した結果が 0 | 無効 |
| 設定値を `atoi` した結果が 0 以外 | 有効 |

したがって空文字、数値で始まらない文字列、`0`、`0tail` は無効です。`1`、`-1`、`2tail` は有効です。空白と符号は `atoi` の変換規則に従い、文字列全体の妥当性検査はありません。判定値は関数内の `static const bool` に保持され、最初に該当経路を通った時点で一度だけ読み取られます。その後の同一プロセス内の環境変更は反映されません。

## 有効になる条件

`cpu_experts()` の対象 layer が `gg::kFmtMXFP4` 形式のときに判定されます。この形式には MXFP4 expert のほか、役割ごとの低 bit expert type を含む構成もあります。`cpu_experts_mx()` は実際に全役割が MXFP4 かを確認し、そうでなければ IQ CPU lane へ送ります。

値が有効でも、処理は従来順序に戻る条件があります。

- `ord` に呼び出し元指定の順序がある。
- store がなく `StoreHold` が読み込みを管理していない。
- expert が 2 件未満。
- この呼び出し時点ですでに全 expert が読み込み済み。

これらの場合は `wait_all()` の後、全件を一度に `cpu_experts_mx()` へ渡します。`DS4_MISS_SPLIT=0` の場合も同じ経路です。`gg::kFmtMXFP4` 以外の形式ではこの変数を参照する分岐に入りません。

## 実行時の詳細

split 経路では、`StoreHold` が対象 layer の未 RAM resident expert の store 読み込みを開始します。読み込み済みの expert を `hot`、未完了のものを `cold` に分け、`hot` を先に計算します。その後 `cold` の中から読み込み済みになったものを順に選び、まだ一件も完了していなければ先頭の未処理 expert の読み込みを待ってから一件ずつ計算します。全 expert の処理後、`StoreHold` の破棄時に store slot を解放します。

この分岐は、CPU lane の expert を計算しながら、他の expert のファイル読み込みを進めるための順序変更です。実装コメントでは expert ごとの行計算が独立で、出力 bit は同じとしています。環境変数専用のログ出力はありません。別の `--pcie-frac` 等の GPU 実行条件が CPU lane を使う状況に影響し得ますが、この変数自身は CLI 引数や設定ファイルとの優先順位を持ちません。

## 文書との照合

`docs/DETAILS.md` の CPU lane と DeepSeek V4.1 の説明には、この変数固有の既定値や効果の説明は見つかりませんでした。性能値はこの commit の文書に条件付きで示されていないため記載していません。

## 根拠

- `src/dsv41/ds4_model.cu:5821-5857` — store 読み込みの開始、ready 判定、個別/全件 wait、slot 解放。
- `src/dsv41/ds4_model.cu:5859-5900` — 既定値、`atoi` 判定、fallback 条件、hot/cold の分割と計算順。
- `src/dsv41/ds4_model.cu:5639-5641` — MXFP4 CPU 処理から IQ CPU lane への dispatch。
- `src/dsv41/ds4_gguf.cuh:39-45` — expert layer format と各 role の型、全 role が MXFP4 かの判定。
- `src/dsv41/ds4_model.cu:6588-6590, 9245-9248` — CPU lane から `cpu_experts()` を呼ぶ経路。
