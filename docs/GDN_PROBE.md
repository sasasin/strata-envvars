# `GDN_PROBE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`GDN_PROBE` は通常の Strata 実行設定ではなく、Metal の `gdn_prompt_parity` ベンチマーク用フックです。値 `1` と `2` は GDN prompt scan カーネルの一部処理を意図的に省き、ベンチマーク結果の正しさを壊す診断用の比較を行います。環境変数を読むコードは `metal/tests/gdn_prompt_parity.cpp` にだけあり、通常の Metal engine の呼び出しは関数定数 6 に `0` を渡します。

## 値と判定

ベンチマークが `GDN_PROBE` を読む箇所では、未設定なら `0`、設定されていれば `std::atoi()` の結果を使います。`atoi` は先頭の空白と符号の後の10進数字列を読み、数字列の後ろは無視します。空文字や数字で始まらない文字列は `0` になります。したがって `1`, `1tail`, `  +1x` は `1` として扱われ、`2` は `2`、`3` や `true` は `0` と同じ扱いです。整数範囲を超える文字列の結果はこのコードでは保証できません。

| 変換結果 | カーネルで変わる処理 |
|---|---|
| `1` | scan の simdgroup 部分和を threadgroup memory に書いて同期・合算する処理を省略します。ソースコメントは結果が誤ると明記しています。 |
| `2` | scan 後の状態更新ループを省略します。 |
| その他（通常の既定値 `0` を含む） | これらの処理を省略しません。 |

## 有効になる条件

- `metal/tests/gdn_prompt_parity.cpp` をベンチマークモード `--bench` で実行していること。通常の parity 検査モードは `--bench` でない場合に早期 return するため、この環境変数を読む行に到達しません。
- ベンチマークの scan 構成ループ内で、負の scan-block 値かつ `nm[9] != 'v'` の条件を満たす場合にだけ関数定数 6 に値が渡されます。`gdn_scan_v` は除外する意図の条件です。
- `GDN_PROBE` を環境から読む処理は Metal テスト用ソースに限定されます。製品側の `metal/src/engine/window.cpp` と `metal/src/engine/prompt_chain.inc` は通常の `gdn_scanr_4` に関数定数 6 の値 `0` を明示的に渡します。

ベンチマーク配列には `chunked` という短い名前も含まれますが、同じ条件式が `nm[9]` を参照します。この文字列の有効範囲外を読むため C++ 上の動作は未定義です。そのため、その反復で環境変数が適用されるかは断定できません。

## 実行時の詳細

テストプログラムは `--bench` のとき、scan カーネルを組み立てる各該当反復で `std::getenv("GDN_PROBE")` を呼び、設定値を `std::atoi()` で整数化して関数定数 index 6 に設定します。結果は `gdn_prompt.metal` の `gdn_probe` に届き、値 `1` は部分和の共有・同期・合算を飛ばし、値 `2` は scan state の更新を飛ばします。値は一度だけ static cache されるものではありません。

`gdn_prompt_parity` はベンチマーク時間を stdout に表示します。環境変数自体について専用のログや警告はありません。値 `1` は誤った結果を意図するため、その測定を通常の正確性・性能として解釈できません。

## 根拠

- `metal/tests/gdn_prompt_parity.cpp:1-5,23-26,138-174` — テストベンチマーク、`--bench` 判定、環境変数読み取りと関数定数への設定。
- `metal/kernels/gdn_prompt.metal:154-156,209-225` — 関数定数 index 6 の宣言と値 `1` / `2` による処理省略。
- `metal/src/engine/window.cpp:2253-2255` — 製品側の prompt GDN scan は定数 `0` を指定。
- `metal/src/engine/prompt_chain.inc:208-211` — 製品側の別 prompt chain 経路も定数 `0` を指定。
