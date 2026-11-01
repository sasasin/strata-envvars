# `STRATA_ISA_FLOOR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

これはエンジンの実行時環境変数ではなく、ソース版セットアップが古い x86 CPU 向けエンジンを選んでビルドするときに読む環境変数です。`setup.py` の `cpu_floor()` が値を読み、選択した floor を `-DSTRATA_ISA_FLOOR=avx` または `-DSTRATA_ISA_FLOOR=none` として CMake に渡します。通常のエンジン実行ファイルにこの環境変数を設定しても、Strata の実行時動作は変わりません。

`avx` は AVX（AVX2/FMA/F16C なし）、`none` は SSE4.2 + POPCNT の CPU を対象にする実験的なビルドです。空値はセットアップによる CPU 判定を使います。CMake の説明では通常ビルドの floor は AVX2 です（`setup.py:1465-1485,5842-5847`; `CMakeLists.txt:35-45`）。

## 値と判定

`os.environ.get("STRATA_ISA_FLOOR", "").strip().lower()` で値を取得・正規化し、正規化後が `avx` または `none` のときだけその値を返します。文字列全体を比較します。

| 環境値 | `cpu_floor()` の扱い |
|---|---|
| 未設定、空文字、空白だけ | CPU を自動判定 |
| `avx`（大文字小文字や前後空白は無視） | `avx` を強制 |
| `none`（大文字小文字や前後空白は無視） | `none` を強制 |
| その他（例: `0`, `true`, `bogus`） | エラーにはせず CPU を自動判定 |

強制値の確認は CPU 自動判定より先です。そのため `avx` / `none` は AVX2 搭載 CPU でも返されます。無効値に対する専用の警告や終了経路はありません。自動判定では ARM64 は空値、AVX2 CPU も空値です。AVX2 未満では Windows は CPUID/XGETBV、Windows 以外は `/proc/cpuinfo` を使い、AVX があれば `avx`、SSE4.2 と POPCNT があれば `none`、どちらもなければ `unsupported` を返します（`setup.py:1433-1451,1454-1456,1465-1485`）。

## 有効になる条件

- 値を読むのはソース版 `setup.py` の `cpu_floor()` が呼ばれたときです。主な呼び出しは setup の CPU 判定（`setup.py:9520`）と、ローカル CUDA/HIP エンジンの既存 build 照合・ビルド（`setup.py:4796,5927`）です。macOS の通常 setup は先に Mac 専用処理へ戻り、SYCL は専用 setup へ分岐するため、それらの経路ではこの通常の CPU 判定位置を通りません（`setup.py:9068-9069,9220-9225`）。
- `cpu_floor()` の返値がコンパイル設定になるのはローカルエンジンをビルドする経路です。CUDA は `--build` などでビルドが選ばれた場合に `isa_floor_defs()` が CMake 引数を作り、HIP の Linux ビルドも同じ helper を使います（`setup.py:7772-7799,4821-4827,5842-5847,5944-5950`）。通常の ready-made engine を使う経路ではこの値をエンジンへ渡しません。したがって、AVX2 CPU で `STRATA_ISA_FLOOR=avx` を指定しただけでは、通常は ready-made engine が選ばれ、古い CPU 向け build には切り替わりません。ローカル build を行う必要があります。
- CMake は値を空、`avx`、`none` に限定し、他の CMake 値なら configure を `FATAL_ERROR` で止めます。環境変数に未知の値を設定しても `setup.py` が空値または自動判定値に変換するため、この CMake エラーには直結しません（`CMakeLists.txt:39-45`）。
- 非 x86 で CMake に非空の floor が渡された場合、CMake は警告して floor を空に戻します。`STRATA_PORTABLE` が有効な build と非空 floor は排他的です（`CMakeLists.txt:44-45,62-71`）。
- CMake の非空 floor 経路では ggml CPU backend を build host の ISA ではなく指定 floor に設定し、`avx` と `none` に応じた compile definition を付けます。Strata 独自の高 ISA カーネルは CPU capability check の後段で使われる設計で、floor は主に ggml CPU 側と古い CPU 用カーネルの構成に適用されます（`CMakeLists.txt:1936-1951,1991-2023`; `src/kernels/cpu/expert_layout.cpp:224-226`）。

## 実行時の詳細

値は `cpu_floor()` を呼ぶたびに `os.environ.get()` で読み直され、関数内・モジュール内の cache には保存されません。setup プロセスの起動時点で親プロセスから引き継いだ環境値が使われます。setup 実行中に環境値を書き換える Strata の処理は見つかりません。CMake 引数を生成する時点では floor の文字列を明示的に `-DSTRATA_ISA_FLOOR=...` に変換します（`setup.py:1465-1485,5842-5847`）。

自動判定結果が `unsupported` の場合、setup は `this CPU has neither AVX2 nor SSE4.2; Strata needs at least SSE4.2 (Intel Nehalem, 2008, or newer)` を表示して終了します。AVX2 のない CPU でサポート対象 floor が得られると、setup は実験的で遅い対応である旨と `STRATA_ISA_FLOOR=<floor>`、10–20 分の一度限りのコンパイルを警告し、`a.build = True` にします。AMD GPU と Windows の組合せでは、続けて Linux での build を求める失敗メッセージを出して終了します（`setup.py:9520-9540`; 出力形式 `setup.py:896-909`）。

これらの警告は自動判定で AVX2 未満だった場合のものです。強制値 `avx` / `none` そのものに対応する専用ログはありません。エンジン実行時にこの環境変数を再読込する箇所もありません。

## 根拠

- 環境からの直接読み取りと値判定: `setup.py:1465-1485`。
- 読み取り呼び出し箇所: `setup.py:4796,5927,9520`。
- 値を CMake cache 定義へ変換する箇所: `setup.py:5842-5847`。
- CUDA/HIP build への引き渡し: `setup.py:4821-4827,5944-5950`。
- CMake の値制限、対象 CPU、build 設定: `CMakeLists.txt:35-45,62-71,1936-1951,2008-2023`。
- setup の unsupported 終了、古い CPU の警告と build 選択: `setup.py:9520-9540`。

`STRATA_ISA_FLOOR` の全参照には上記の setup / CMake 実装のほか、説明コメントやテスト参照もあります。環境値を読む本番コードは `setup.py:1469` であり、エンジンの C++/GPU 実行コードに実行時読み取りはありません。テストコードは実装根拠として使用していません。
