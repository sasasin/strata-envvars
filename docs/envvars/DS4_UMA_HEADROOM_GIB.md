# `DS4_UMA_HEADROOM_GIB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

DeepSeek-V4.1 (`strata-dsv41`) の統合 GPU 向けメモリ見積もりに使う、ホスト RAM の予約量を GiB 単位で指定します。Linux の CUDA 統合 NVIDIA GPU で、`MemAvailable`（および認識できた cgroup v2 制限下の空き）からこの量を引いた値が、CUDA の報告する空き容量より大きい場合に、expert 配置などが使える GPU メモリ量として採用されます。既定値は 6 GiB です。

この環境変数は Strata 同梱の DeepSeek-V4.1 専用実行ファイルの処理です。CMake では `STRATA_BUILD_DSV41` は既定 OFF で、ON の場合に `strata-dsv41` を追加します（`CMakeLists.txt:906-920`）。一般の `strata` 実行経路に同じ読み取りはありません。

## 値と判定

実装は `std::getenv()` の有無で未設定を判定し、設定時は `std::atof()` で数値に変換します。文字列全体の検証や範囲チェックはありません。

| 入力 | `head` の計算 | 結果 |
|---|---|---|
| 未設定 | `6.0` を使い、`uint64_t` に変換して 30 bit 左シフト | 6 GiB |
| 空文字 | `atof("")` の結果 0 を変換 | 0 GiB |
| 数値文字列 | `atof()` の結果を `uint64_t` に変換してから 30 bit 左シフト | 小数部は整数化時に切り捨て。例: `2.9` は 2 GiB |
| 数字の後ろに文字がある文字列 | `atof()` が読める数値接頭部を使う | 例: `8junk` は 8 GiB |
| 数値として変換できない文字列 | `atof()` は 0 を返す | 0 GiB |

先頭空白や符号を含む数値接頭部も `atof()` の変換規則に従います。負値、NaN/無限大、整数化可能範囲を超える値には検査・fallback がありません。浮動小数点から `uint64_t` への変換が表現可能範囲外なら C++ 上の結果は未定義です。また、変換後の値を 30 bit 左シフトするため、大きな値は `uint64_t` の範囲で桁が落ちます。通常の有限・非負の小さな GiB 値を指定する必要があります。

## 有効になる条件

次の条件を満たす場合にだけ headroom が空き容量の見積もりへ反映されます。

- DeepSeek-V4.1 エンジンの `src/dsv41/ds4_model.cu` がビルド・実行されている。
- コンパイル条件が `!_WIN32 && !STRATA_USE_HIP`。Windows と HIP では関数内の環境変数読み取り・計算は行われず、入力された CUDA 空き容量 `fr` をそのまま返します。
- `cudaDeviceGetAttribute(..., cudaDevAttrIntegrated, dev)` が成功し、対象デバイスが統合 GPU と報告される。属性取得失敗時も `fr` を返します（エラーは `cudaGetLastError()` でクリアされます）。独立 GPU なら変数を読みません。
- `ram_avail()` が既知の値を返し、`avail > head` かつ `avail - head > fr` である。条件を満たさない場合は `fr` を維持します。

Linux では `ram_avail()` は `/proc/meminfo` の `MemAvailable` を読み、cgroup v2 の階層で数値の `memory.max` が見つかれば `memory.current` から `memory.stat` の `file` を除いた使用量を使って上限を下げます（`src/dsv41/ds4_model.cu:199-239`）。利用可能量が不明な場合も、headroom を引いた推定値を採用しません。

CLI にこの headroom 値を設定する引数はありません。`--reserve-mib` は得られた空き容量から追加で差し引かれ、`--vram-experts` は残りの expert 用 budget に掛けられます（`src/dsv41/ds4_main.cpp:1320-1321`, `src/dsv41/ds4_model.cu:2271-2275,4603-4617`）。これらは環境変数を上書きするのではなく、後段で別の調整をします。

## 実行時の詳細

`uma_free(dev, fr)` は、統合 GPU かを確認した後に環境変数を読み、`head = (uint64_t)(設定値または 6.0) << 30`、`avail = ram_avail()` を計算します。空き RAM から headroom を引いた値が CUDA の `fr` より大きいときだけ、その値で `fr` を置き換えます。したがってこれは上限の差し替えであり、`fr` と `avail - head` の小さい方を取る処理ではありません。環境変数固有の警告やログ出力はありません。

関数内に `static` cache はなく、呼び出しごとに属性、環境変数、RAM 情報を読み直します。ソース中の呼び出しは、モデルロード時の各 GPU 空き容量初期化、file-backed expert の RAM 先読み量計算、expert 配置時の budget 計算、および vision tower 読み込み後の空き容量再計算です（`src/dsv41/ds4_model.cu:2195-2196,3003-3015,4603-4617,6206-6210`）。設定変更が後続の呼び出しに反映される形ですが、通常のプロセス環境変更手段や呼び出し時期はこの変数固有の実装では規定していません。

初期値 `d.free0` は自動 `file_experts` 判定にも使われ、後続の配置 budget にも使われます。`place_experts()` は各 GPU グループの残予算をもとに各 layer の expert の VRAM 配置数を決めます（`src/dsv41/ds4_model.cu:2255-2275,4585-4650`）。結果として CPU lane に残る expert 数・配置は変わり得ます。起動時の device 概要には VRAM 上の expert 数と通常の空き MiB が表示されますが、この行は `cudaMemGetInfo()` の値を直接表示し、headroom の計算値ではありません（`src/dsv41/ds4_model.cu:5278-5303`）。環境変数に特化した終了・失敗経路はありません。

## 根拠

- 全参照を `rg -n --hidden --glob '!.git/**' 'DS4_UMA_HEADROOM_GIB'` で調べた結果、ソースでの実読み取りは `src/dsv41/ds4_model.cu:255-257` の一箇所です。もう一つのソース参照 `src/dsv41/ds4_model.cu:242-246` は説明コメントで、他の一致は文書のみです。動的な env helper への名前渡しはありません。
- 条件、式、未設定値、fallback: `src/dsv41/ds4_model.cu:242-261`。
- `MemAvailable` と cgroup v2 からの値: `src/dsv41/ds4_model.cu:199-239`。
- 各呼び出しと利用先: `src/dsv41/ds4_model.cu:2195-2196,2255-2275,3003-3023,4585-4650,6206-6214`。
- 引数との関係: `src/dsv41/ds4_main.cpp:1320-1321`; budget 算出 `src/dsv41/ds4_model.cu:2271-2275,4603-4617`。
- 説明資料 `docs/DGX_SPARK_LINUX.md:84-86` は `MemAvailable` から 6 GiB を引く sizing と本変数に言及し、`docs/STRIX_HALO.md:101-103` は `device_free_bytes()` に言及しています。今回確認した対象ソースでは本変数の実装箇所は `src/dsv41/ds4_model.cu` の `uma_free()` です。`include/strata/core/expert_cache.hpp:75-81` の `device_free_bytes()` 説明は別の expert-cache API の説明であり、本変数の読み取り実装ではありません。
