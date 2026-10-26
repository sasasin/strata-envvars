# `DS4_MX_TIER`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek 4.1 engine の CPU lane が処理する MXFP4 expert row dot product の SIMD tier を手動指定します。指定できるのは、その実行 CPU で利用可能な実装だけです。有効な指定がなければ、利用可能な vector tier を小さな warm job で測って選びます。tier は演算結果を変えず、処理速度の選択に使われます。

## 値と判定

環境変数の文字列全体を、tier 名と大文字小文字を区別して比較します。数値変換や前後空白の除去はありません。

| 値 | 動作 |
|---|---|
| `scalar` | scalar tier を選択 |
| `avx2` | CPU が AVX2 をサポートする場合に選択 |
| `avxvnni` | ビルドに AVX-VNNI 実装があり、CPU が AVX-VNNI をサポートする場合に選択 |
| `avx512` | CPU が必要な AVX-512F/BW と OS の ZMM 状態保存をサポートする場合に選択 |
| `avx512vnni` | CPU が AVX-512 VNNI と上記 AVX-512 条件をサポートする場合に選択 |
| 未設定、空文字、上記以外、または非対応tier名 | 自動選択へ進む |

自動選択では、対応する vector tier がなければ `scalar`、候補が1つならそのtier、複数なら測定値が最良のtierを選びます。自動測定は scalar tier を候補に含めません。CPU が tier を実行できるかは CPUID と OS が有効にしたレジスタ状態から判定され、AVX-VNNI は該当コードがビルドされている場合だけ候補になります。

## 有効になる条件

この変数を読むのは `src/dsv41/ds4_gguf_cpu.cpp` の MXFP4 CPU row-kernel 選択です。DS4 engine で CPU lane を作成してこのコードを通る場合に評価されます。変数は Strata の一般的な GGUF/他 engine の CPU SIMD tier を指定するものではありません。CPU lane の案内は `docs/DEEPSEEK41.md` にあり、同資料は低bit CPU lane のビルド要件として `STRATA_NATIVE_EXPERTS=ON` を記載しています。

有効なtierを指定していても、`mx_rows_tier()` に渡された行幅 `k` が256の倍数でなければ実際の行演算は scalar に切り替わります。同関数は呼び出し時にも CPU tier 対応を確認し、非対応なら scalar に戻します。

## 実行時の詳細

`mx_tier()` の関数内 static 値として最初の選択結果を保存します。通常のDS4モデル構築では `make_pools()` が CPU lane の pool を作った後、最初の生成tokenより前に `mx_tier()` を呼んで評価を済ませます。その後プロセス内で環境変数を書き換えても選択は変わりません。

自動選択の測定は、5120要素幅・64行の合成行列と1/2/4 activationを使い、各候補につき6 roundを実行します。最初のroundを除き、候補ごとの最短所要時間を比較します。CPU lane の起動ログは verbose 時に stderr へ出力され、tier名と測定情報が含まれます。手動指定時の測定情報は `DS4_MX_TIER=<name>` です。自動候補が1つだけ、またはvector候補がない場合は測定せず、その情報欄は空になります。

## 根拠

- `src/dsv41/ds4_gguf_cpu.cpp:262-280`: `getenv`、文字列完全一致、対応可否判定、自動選択。
- `src/dsv41/ds4_gguf_cpu.cpp:217-259,350-379`: CPU機能検出、tier対応判定、static cache。
- `src/dsv41/ds4_gguf_cpu.cpp:282-321`: warm job、round、候補比較。
- `src/dsv41/ds4_gguf_cpu.cpp:393-415`: 行幅・CPU対応の再確認、選択tierでの処理。
- `src/dsv41/ds4_model.cu:4832-4870`: CPU pool 作成後の事前評価と verbose 時の stderr ログ。
- `docs/DEEPSEEK41.md:129-147`: DS4 の CPU lane、対応するexpert形式、ビルド要件。
