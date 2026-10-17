# `MOE_PROBE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の grouped routed-expert カーネルを CPU 参照実装と照合し、性能を測る `metal/tests/expert_parity.cpp` のための probe です。`moe_gu` カーネルの function constant 22 に整数値を渡し、値が `1` の場合に量子化用テーブルの threadgroup への読み込みを省略します。カーネル内コメントは、この設定では i-quant の値が誤ると明記しています。

これはテスト／ベンチ用コードの設定であり、通常の Metal 推論経路で使う環境変数ではありません。推論側は function constant 22 を設定せず、カーネル側の既定値 `0` で動作します。

## 値と判定

`expert_parity.cpp` は `getenv("MOE_PROBE")` が null かを調べ、設定されていれば `std::atoi` の結果を function constant 22 に渡します。未設定時は `0` です。空文字や数値として解釈できない文字列は `atoi` により `0` になります。数値の先頭部分だけが変換されるため、たとえば `1junk` や ` 1` は `1`、`2` は `2`、`-1` は `-1` になります。カーネルが probe として扱うのは変換後の値がちょうど `1` の場合だけです。

| `MOE_PROBE` | function constant 22 | `moe_gu` の処理 |
|---|---:|---|
| 未設定 | 0 | `load_tab` を実行する |
| `1`、`1junk`、` 1` など `atoi` が 1 を返す値 | 1 | `load_tab` を省略する |
| 空文字、数値で始まらない文字列、その他の整数 | 0 または変換値 | 変換後が 1 でなければ `load_tab` を実行する |

文字列全体の検証、範囲制限、警告やエラー処理はありません。

## 有効になる条件

`metal/tests/expert_parity.cpp` が構築する `moe_gu` パイプラインに限って参照されます。同ファイルの説明では、この実行ファイルは synthetic 入力の parity 確認と速度測定を行うツールです。リポジトリ内の通常の Metal 推論エンジン `metal/src/engine/window.cpp` は同じカーネルを使いますが、function constant 22 は渡していません。したがってこの変数を設定しても、そこで構築される推論用パイプラインには反映されません。

カーネルの `load_tab<F>` は量子化形式ごとに実装が異なり、i-quant 形式では参照テーブルを埋めます。probe 値 `1` はそのロードを飛ばすため、i-quant の parity 結果は正しい値を示しません。他形式でテーブルロードが不要なものもあります。down-projection の `moe_down` パイプラインにはこの probe を適用しません。

## 実行時の詳細

環境変数は `expert_parity.cpp` の `make()` が `moe_gu` パイプラインを構築するたびに読み取られます。プロセス内の static cache はありません。`make()` は通常の実行に加え、ベンチマークの構成 sweep でも呼ばれるため、読み取り位置はプロセス起動時に一度だけとは限りません。環境変数を子プロセスへ転送・上書きする処理はこの参照箇所にはありません。

変数を読み取るときの専用ログ、警告、エラーはありません。テスト／ベンチ実行の parity 値や速度表示には probe の値を別途表示するコードは確認できません。probe `1` による不正な i-quant 値は、結果の不一致として現れ得ます。

## 根拠

- `metal/tests/expert_parity.cpp:1-9` — 実行ファイルの parity／speed 用途と入力・出力の概要。
- `metal/tests/expert_parity.cpp:221-230` — パイプライン構築時の環境変数読み取り、`atoi`、function constant 22 への設定。
- `metal/tests/expert_parity.cpp:280,426-441` — `make()` が通常実行と構成 sweep から呼ばれる箇所。
- `metal/kernels/moe.metal:202-218` — function constant 22 の既定値と、値が `1` の場合に `load_tab` を省略する分岐および i-quant 値に関するコメント。
- `metal/kernels/quant.metal:95-126` — i-quant 形式で `load_tab` が参照テーブルを用意する実装。
- `metal/src/engine/window.cpp:864-875,1833-1839` — 通常推論経路では function constant 22 を指定せず、constant 23 などを設定して `moe_gu` を構築する箇所。
