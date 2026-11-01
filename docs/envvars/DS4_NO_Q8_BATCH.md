# `DS4_NO_Q8_BATCH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Strata の DeepSeek-V4.1（DS4）Metal 経路で、複数の Q8 activation quantization job を一つの Metal dispatch にまとめる経路を止めます。変数が設定されていると、job ごとに `q8_quant` を呼ぶ経路になります。単独の Q8 量子化や `mv` のバッチ外の呼び出しは、この変数を判定する `quant_flush` を通らないため対象外です。

## 値と判定

| 状況 | `quant_flush` の処理 |
|---|---|
| `DS4_NO_Q8_BATCH` が未設定 | `DS4_QUANT_SINGLE` が未設定なら複数 job の Metal dispatch を試す |
| 空文字を含め、何らかの値が設定されている | 複数 job の dispatch を試さず、job ごとに `q8_quant` を呼ぶ |
| `DS4_QUANT_SINGLE` が設定済み | `DS4_NO_Q8_BATCH` の値にかかわらず、job ごとに `q8_quant` を呼ぶ（短絡評価のため対象変数は読まれない） |

対象変数は文字列の内容を変換・比較せず、`std::getenv(...) == nullptr` かどうかだけで判定します。したがって `0` や `false` も「設定済み」として batch dispatch を無効にします。数値の境界や不正値 fallback はありません。CLI 引数・設定ファイルからこの値を設定する処理や、他の値との優先順位は見つかりませんでした。`DS4_QUANT_SINGLE` は別の環境変数で、同じく設定有無を判定します。

## 有効になる条件

- `DS4_NO_Q8_BATCH` の分岐は `src/dsv41/ds4_gguf.cu` の `#if defined(STRATA_METAL)` 内にあります。よって CUDA/HIP ビルドではこの変数は参照されず、効果もありません。
- Metal の DS4 executable は `metal/CMakeLists.txt` が `ds4_gguf.cu` をソースに含め、`STRATA_METAL=1` を定義して作ります（同ファイル 132-146, 165-171 行）。
- 実際に分岐へ到達するのは、`mv()` が Q8_0 (`f == 2`) の job を `QuantItems` に追加し、`quant_flush()` に到達した場合です。`mv()` は `n <= 0` または最大 job 数超過なら先に `false` を返します。
- `quant_flush()` は item 数が 0 以下なら環境変数を評価せず終了します。
- batch dispatch を試したものの `metal_host::q8_quant_multi()` が `false` を返した場合も、各 job の `q8_quant()` に fallback します。従って未設定は batch 成功を保証しません。

## 実行時の詳細

`mv()` は GG 型の重みの job と Q8_0 型の重みの job について、入力 activation を `quant_add()` で `QuantItems` に集めます。`quant_flush()` は item があるとき、まず `DS4_QUANT_SINGLE` の設定有無を関数内 static 値として初回評価します。この値はプロセス中 cache されます。一方 `DS4_NO_Q8_BATCH` は static ではなく、`quant_flush()` の呼び出しごとに（ただし `single` が false の場合に限り）環境を読みます。

Metal で両方の条件（`DS4_QUANT_SINGLE` 未設定かつ `DS4_NO_Q8_BATCH` 未設定）を満たすと、job 情報を `Spec` 配列に詰めて `metal_host::q8_quant_multi()` を呼びます。同関数が成功を返せばそこで処理を終えます。失敗を返す場合や対象変数が設定済みの場合は、`QuantItems` の各 item に対して `q8_quant()` を順に呼びます。`q8_quant()` は Metal host の行量子化を試し、成功しなければ通常の kernel launch 経路へ進みます。

この変数の判定自体はログを出さず、失敗終了にもつながりません。batch 試行時、Metal の `ds4_quant.metal` コンパイルに失敗すると `dsv41 metal: compiling ds4_quant.metal failed` が stderr に出て `q8_quant_multi()` が false を返すため、呼び出し元は個別量子化へ fallback します。pipeline の取得に失敗した場合も false を返して同じ fallback になります（`metal/src/engine/ds4_host.cpp:31-43`, `metal/src/engine/ds4_finish.cpp:612-638`）。対象変数によって実行時間や性能がどう変わるかは、このコード調査では測定していません。

## 根拠

- 候補名の参照と値判定、Metal compile guard、batch と個別処理の分岐: `src/dsv41/ds4_gguf.cu:254-277`。
- Q8 quantization の単一 job 経路と Metal host 経路への fallback: `src/dsv41/ds4_gguf.cu:206-212`。
- `mv()` が job を作り `quant_flush()` を呼ぶ箇所、および Q8_0 job の追加: `src/dsv41/ds4_gguf.cu:1173-1198,1230-1269`。
- Metal DS4 executable がこのソースを含み `STRATA_METAL` を定義する箇所: `metal/CMakeLists.txt:132-146,165-171`。
- multi dispatch の false 条件と成功時の dispatch: `metal/src/engine/ds4_finish.cpp:612-638`。compile failure の stderr: `metal/src/engine/ds4_host.cpp:31-43`。
