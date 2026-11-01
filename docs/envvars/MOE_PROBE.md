# `MOE_PROBE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`MOE_PROBE` は macOS/Metal の開発・計測用実行ファイル `expert_parity` から、`moe_gu` kernel の function constant 22 に値を渡す probe です。値が 1 の場合は gate/up kernel の lookup table 読み込みを省略します。製品の Strata Metal engine が読む環境変数ではありません。`metal/CMakeLists.txt` は `metal/tests/*.cpp` を個別の実行ファイルとして登録し、`expert_parity.cpp` もその対象に含めます（`metal/CMakeLists.txt:41-48`）。

## 値と判定

| 環境の状態 | pipeline に渡す値 | kernel 側の動作 |
|---|---:|---|
| 未設定 | `0` | lookup table をロードする |
| 空文字 | `0`（`atoi("")`） | lookup table をロードする |
| `atoi` の結果が `1` | `1` | lookup table のロードと barrier を省く |
| その他の parse 結果 | その整数値 | `1` でないため lookup table をロードする |

ホスト側は `getenv("MOE_PROBE")` が null なら 0、設定されていれば `std::atoi` の結果を渡します。数値文字列全体の検証や範囲チェックはありません。`atoi` が読む 10 進整数の先頭部分が 1 なら、たとえば `1x` も 1 として扱われます。数値として読めない文字列は 0 になります。表現可能な `int` の範囲を超える入力について、呼び出し側に明示的なエラー処理はありません（`metal/tests/expert_parity.cpp:417`）。

## 有効になる条件

- macOS の Metal 用 CMake プロジェクトでビルドした `expert_parity` を実行し、その `make()` が `moe_gu` pipeline を作る経路に入る必要があります。Metal CMake プロジェクト自体は `if(NOT APPLE)` で macOS 以外を拒否します（`metal/CMakeLists.txt:13-18,41-48`）。
- `MOE_PROBE` は gate/up pipeline にだけ渡されます。down kernel 用 pipeline の生成には渡されません（`metal/tests/expert_parity.cpp:412-418`）。
- kernel では function constant 22 が未指定なら 0 とし、`moe_probe == 1` の場合だけ `load_tab` と threadgroup barrier を実行しません（`metal/kernels/moe.metal:202-218`）。コメントはこの設定を「no table load」とし、i-quant では誤った値になると明記しています。したがって正しさを保つ通常設定ではなく、テスト/ベンチで table load の影響を見る probe です。
- 読み取り箇所はテストソースのみです。Metal engine の環境読み取り箇所や CLI 引数・別の環境変数との優先順位は確認できません。`--bench` 等の実行モードは `expert_parity` 自身の CLI ですが、環境変数による上書き・優先順位を追加するコードはありません（`metal/tests/expert_parity.cpp:219-249,412-418`）。

## 実行時の詳細

`expert_parity` は `make()` 内で `moe_gu` pipeline を構築するたびに環境値を評価し、function constant 22 に設定します。プロセス起動時に一度だけ保存する static cache はありません。GPU kernel は定数値を `moe_probe` として参照し、値が 1 以外なら table をロードして barrier を行います（`metal/tests/expert_parity.cpp:412-418`; `metal/kernels/moe.metal:202-218`）。

`MOE_PROBE` 自体について専用のログ、警告、終了コード分岐はありません。`expert_parity` の通常出力・終了結果は parity/bench の処理から生じますが、probe の値を表示したり、不正な文字列をエラーにしたりする処理はこの参照箇所にはありません。

## 根拠

- 環境値の読み取りと function constant 22 への転送: `metal/tests/expert_parity.cpp:412-418`
- probe の定義、未指定時 0、table load の条件、用途コメント: `metal/kernels/moe.metal:202-218`
- `expert_parity` を含む `metal/tests/*.cpp` の個別実行ファイル化、および macOS 条件: `metal/CMakeLists.txt:13-18,41-48`
