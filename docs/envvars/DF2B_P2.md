# `DF2B_P2`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の診断用実行ファイル `dflash2_bench` の `poison2` サブモードで、host/shared USM を GPU kernel から読み書きする試験を選びます。エンジンの生成処理や通常のベンチマーク設定を制御する変数ではありません。`sycl/CMakeLists.txt:437-438` がこの実行ファイルを定義し、`sycl/src/kernels/dflash2_bench.cpp:900-901` が `poison2` 引数を `run_poison2()` に振り分けます。

## 値と判定

共通 helper は環境変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` で `int` に変換します。`DF2B_P2` の既定値は `0` です。

| 値 | `poison2` で実行するアクセス試験 |
|---|---|
| unset、空文字、変換結果 `0` | 以下の5試験すべて |
| `1` | uncached host USM の kernel read |
| `2` | cached host USM の kernel read |
| `3` | uncached host USM の kernel write |
| `4` | cached host USM の kernel write |
| `5` | shared USM の kernel write |
| その他の整数 | 5試験のいずれも選ばれない |

比較は `atoi()` 後の整数値に対して行います。したがって `2tail` や `  +2` のように先頭の整数部分が 2 になる文字列は値 2 として扱われ、数字に変換できない非空文字列は通常 0 となり全試験を選びます。文字列全体の検証や範囲 clamp はありません。`atoi()` で `int` に収まらない値の結果はこのコードでは扱っていません。

## 有効になる条件

- SYCL 側の `dflash2_bench` をビルドし、GPU を選択できる環境で起動する必要があります。実行ファイルは SYCL 用 CMake プロジェクトの target です（`sycl/CMakeLists.txt:1-11,437-438`）。
- コマンドライン引数が `poison2` のときだけ読み取り値が使われます。引数省略時は `bench` となり、他のサブモードも `run_poison2()` を呼びません（`sycl/src/kernels/dflash2_bench.cpp:894-901`）。
- モデルやサーバーモード、CUDA/HIP backend への条件分岐はありません。読み取り箇所は SYCL ベンチマークのこの関数だけです。

## 実行時の詳細

`run_poison2()` に入るたびに `envi("DF2B_P2", 0)` を一度呼び、値をローカル変数 `mode` に保持します。helper は `std::getenv()` を呼びますが static cache はなく、この関数の実行中に環境を変えても保存済みの `mode` は変わりません（`sycl/src/kernels/dflash2_bench.cpp:56,800-809`）。

関数は最初にアクセス前の基準値を `probe("nothing")` として表示し、その後 uncached host USM、cached host USM、shared USM と device buffer を確保・初期化します。選ばれた各試験では 64 要素を読む、または書き、その直後に attention、gate/up、conv_quant の各 kernel の所要時間を測って stdout に表示します。`mode=0` では全試験を順番に実行します（`sycl/src/kernels/dflash2_bench.cpp:803-820`）。

値が 1〜5 以外の場合、アクセス試験はありませんが、基準計測と buffer 確保・初期化までは行われ、通常は `run_poison2()` が 0 を返します。選択外の試験について警告や理由ログは出しません（同 `:809-821`）。device buffer 確保に失敗すると `out of device memory (<bytes> bytes)` を stderr に出して終了コード 2 で終了します。host/shared USM の確保結果にはこの関数内で明示的な null 判定がないため、失敗時の表示や終了経路は Strata のコードからは特定できません（同 `:62,811-815`）。

このコードが測定するのは Strata が発行する kernel アクセス試験とそれに続く時間表示までです。USM の割り当て属性や driver 側の挙動自体は、この変数の Strata 側の効果として説明しません。

## 根拠

- helper の unset / empty 判定と `atoi()` 変換: `sycl/src/kernels/dflash2_bench.cpp:56`
- 読み取り、各 mode の kernel read/write 試験、戻り値: `sycl/src/kernels/dflash2_bench.cpp:800-821`
- GPU queue と CLI サブモードの振り分け: `sycl/src/kernels/dflash2_bench.cpp:894-901`
- SYCL ベンチマーク target: `sycl/CMakeLists.txt:1-11,437-438`
