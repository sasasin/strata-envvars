# `STRATA_ISA_FLOOR`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

`setup.py` で、AVX2 を持たない古い CPU 向けの実験的なエンジンをどの命令セットの下限でビルドするか指定します。`avx` は AVX（Sandy/Ivy Bridge 世代）、`none` は SSE4.2 + POPCNT（Nehalem/Westmere 世代）を選びます。これは Strata エンジンの実行時設定ではありません。`setup.py` が値を読み、対応する `-DSTRATA_ISA_FLOOR=...` を CMake に渡し、CMake がビルド内容を決めます。手動で CMake を使う場合は CMake cache 変数 `-DSTRATA_ISA_FLOOR=avx` / `none` を指定する必要があり、シェル環境変数だけでは CMake はこの値を取り込みません。

## 値と判定

`setup.py:cpu_floor()` は `os.environ.get("STRATA_ISA_FLOOR", "").strip().lower()` で読みます。よって unset と空文字は同じ自動選択扱いです。前後の空白は除かれ、大文字小文字は区別しません。

| 正規化後の値 | `setup.py` の扱い |
|---|---|
| `avx` | CPU 自動判定を無視し、AVX floor を指定 |
| `none` | CPU 自動判定を無視し、SSE4.2 floor を指定 |
| 空、その他（例: `true`, `1`, `bogus`） | エラーにはせず、CPU 機能から自動選択 |

自動選択では、AVX2 があれば通常ビルド（floor なし）です。AVX2 がなければ Windows は CPUID と OS の YMM 保存状態から AVX を判定し、それがなければ SSE4.2 + POPCNT を判定します。Linux など Windows 以外では `/proc/cpuinfo` の flags を調べ、`avx` があれば `avx`、なければ `sse4_2` と `popcnt` の両方があれば `none`、どちらもなければ `unsupported` とします。`unsupported` は setup の起動フローで「少なくとも SSE4.2 が必要」として停止します。

根拠: `setup.py:730-769,5128-5142`。

## 有効になる条件

環境変数が参照されるのは `setup.py` のエンジン選択・ビルド経路です。既製エンジンをそのまま使う場合、環境変数だけでそのバイナリの ISA floor は変わりません。`--build` などでソースからビルドする場合、または AVX2 のない CPU 用に setup がビルドする場合に選択値が CMake へ渡ります。CUDA と Linux HIP のビルド経路はいずれも `cpu_floor()` の結果を `isa_floor_defs()` で CMake に渡します。Windows の HIP は古い CPU 用エンジンを setup でビルドできず、setup が案内付きで停止します。

有効な `avx` / `none` が指定されていれば、AVX2 搭載 CPU でも古い floor を強制できます。無効値は無視して自動判定へ戻るため、設定値の typo に対する明示エラーはありません。既存の setup 管理ビルドは、保存済み `BUILD.json` の `isa_floor` と今回の選択が異なる場合に一致扱いされず再ビルドされます。手動ビルドでは CMake cache に同じ名前の変数があり、空 / `avx` / `none` 以外は configure error、`STRATA_PORTABLE` と同時指定も configure error です。

根拠: `setup.py:2643-2676,3330-3335,3400-3441,5433-5456`; `CMakeLists.txt:35-45`。

## 実行時の詳細

`avx` ビルドでは CMake が ggml-cpu の CPU variants と native CPU 設定を無効にし、SSE4.2 と AVX を有効、AVX2 / FMA / F16C などを無効にして、ビルド機ではなく対象 floor 向けにします。`none` では AVX も無効にします。Strata 自身の AVX2 / AVX-512 kernel はバイナリに残りますが、CPU 機能チェックを通る場合に限って使われます。エンジン起動時にコンパイル済み floor を `isa_floor_build()` で取得し、対象 CPU が AVX または SSE4.2 + POPCNT を持たない場合は診断を stderr に出して終了コード 2 で戻ります。古い CPU で動かす場合は ggml-cpu の kernel が CPU 側 expert を処理し、AVX floor では一部の Strata AVX1 kernel も機能チェックと型条件を満たす場合に使われます。

setup は値を `cpu_floor()` の呼び出し時に読みます。エンジン実行ファイルはビルド時に選んだ floor を compile definition に持つため、起動後に環境変数を変更しても実行中エンジンの floor は切り替わりません。

根拠: `CMakeLists.txt:1227-1250,1295-1304`; `src/kernels/cpu/expert_layout.cpp:139-187`; `src/program/generate.cpp:2657-2683`; `src/kernels/cpu/native_expert.cpp:149-193,217-230`。

## 資料との照合

`docs/INSTALL.md` は古い CPU build を experimental とし、AVX または SSE4.2 用のビルドで CPU 側 expert が ggml-cpu を使うこと、GPU 側は変わらず CPU 側は遅くなること、実機の古い CPU では未検証であることを説明しています。同資料の性能値は Ryzen 5 7600 + RTX 5070 上で古い経路を強制した場合の測定であり、古い実 CPU の速度保証ではありません。手動 CMake では `-DSTRATA_ISA_FLOOR=...`、setup では `STRATA_ISA_FLOOR=...` を使うという区別も資料と実装で一致します。

根拠: `docs/INSTALL.md:139-166`。
