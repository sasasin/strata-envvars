# `STRATA_MMVQ_WAVE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_HIP_GFX906` ビルドで native MMVQ が使う wave64 カーネルと、従来の CUDA 配置を切り替えます。gfx906 用の既定は wave64 配置です。値を文字列 `0` にすると、Q8_1 入力の列ごとに同じカーネルを実行する従来配置へ戻ります。通常の CUDA/HIP ビルドでは切替コード自体がコンパイルされず、この変数は native MMVQ の選択に影響しません。

## 値と判定

gfx906 用カーネル実装は `std::getenv()` の結果を `std::string` にして、文字列全体を `"0"` と比較します。数値変換や先頭文字だけの比較はありません。

| 値 | gfx906 での判定 |
|---|---|
| unset | wave64 配置を使う |
| 空文字 | wave64 配置を使う |
| 厳密に `0` | wave64 を使わず、従来配置へ進む |
| `1`、`00`、`0anything`、その他の文字列 | wave64 配置を使う |

大文字小文字、空白、数値としての妥当性は関係しません。CLI 引数や設定ファイルとの優先順位はありません。

カーネル選択用の `g_wave_off` は翻訳単位のグローバル変数として初期化されるため、初期化後に値を再評価しません。実行中に環境を書き換えても、この値は更新されません。parity test には別途、negative control の判定時に `getenv()` を呼ぶ箇所があります。根拠: `src/kernels/cuda/native_mmvq.cu:1572-1578`、`src/kernels/mmvq_multi_parity.cpp:245`。

## 有効になる条件

- CMake の `STRATA_HIP_GFX906` が有効で、gfx906 向け HIP 互換ビルドであることが必要です。このビルドは CMake で `STRATA_HIP_GFX906=1` を定義します。通常の CUDA/HIP ビルドではソースの `#if defined(STRATA_HIP_GFX906)` が wave64 実装を除外し、切替マクロも空になります（`CMakeLists.txt:64-67,122-137`; `src/kernels/cuda/native_mmvq.cu:1572,1636-1639`）。
- 有効な値判定でも、native MMVQ の各型別関数が `STRATA_WAVE_MMVQ` の切替箇所を通る必要があります。ここにあるのは Q5_0/Q5_K、Q2_0、Q3_K、IQ4_XS、Q4_K、Q6_K と `small_mmvq` 経由の型です（`src/kernels/cuda/native_mmvq.cu:1642-1655,2144-2155,2185-2196,2225-2237,2265-2276,2305-2316,2345-2358`）。
- Q6_K は先に packed MMVQ を試し、登録済み packed weight でその経路が成功すると wave 判定を通らず終了します（`src/kernels/cuda/native_mmvq.cu:2345-2356`）。同じ関数が Q6_K の他の条件で継続した場合は wave 判定に進みます。
- `STRATA_MMVQ_WAVE=0` は gfx906 の parity test が従来配置を実行するためにも設定されています。テストコードでは、wave64 配置だと negative control が検出できるレイアウト差を持たないケースを許容します（`CMakeLists.txt:764-774`; `src/kernels/mmvq_multi_parity.cpp:241-249`）。

## 実行時の詳細

gfx906 ビルドでは、各型別 MMVQ 関数が入力形状・ポインター・stream を検証した後に `STRATA_WAVE_MMVQ` を評価します。`g_wave_off` が false なら、wave64 kernel を列数 1〜8 に対応するテンプレートで起動し、launch check の後に戻るため、通常の CUDA 配置には進みません。true ならマクロ内で処理せず、関数ごとの既存 single/multi-column CUDA 配置へ進みます（`src/kernels/cuda/native_mmvq.cu:1613-1639,1642-1655,2144-2168`）。

wave64 kernel はブロックあたり4つの wavefront で各1行を処理し、lane 間の butterfly reduction で出力します。これは gfx906 ビルドに限られる GPU 実行経路です。環境変数の値による専用ログ、警告、エラーはありません。入力検証や launch 自体が失敗した場合は既存の例外経路が使われます（`src/kernels/cuda/native_mmvq.cu:1564-1568,1572-1637`）。

## 文書との照合

`docs/AMD_HIP.md` は gfx906 の MMVQ を「1 wavefront per row, 64-lane butterfly, no LDS」と記し、`STRATA_MMVQ_WAVE=0` を CUDA 配置へ戻すスイッチとして示しています。同文書はスイッチを置き換え先のレイアウトと bitwise parity test で確認したとしていますが、`STRATA_MMVQ_WAVE` 固有の速度測定値は示していません。性能差はここからは判断できません（`docs/AMD_HIP.md:492-505`）。

## 根拠

- 値の読み取り、gfx906 条件、kernel、切替マクロ: `src/kernels/cuda/native_mmvq.cu:1572-1639`。
- 切替が呼ばれる型別 MMVQ と Q6 packed の先行経路: `src/kernels/cuda/native_mmvq.cu:1642-1655,2144-2155,2185-2196,2225-2237,2265-2276,2305-2316,2345-2358`。
- CMake の gfx906 macro 定義およびテスト値: `CMakeLists.txt:64-67,122-137,764-774`。
- 説明資料: `docs/AMD_HIP.md:492-505`。
- テスト専用の設定有無チェック: `src/kernels/mmvq_multi_parity.cpp:241-249`。この読み取りは parity test の negative control 用で、通常の実行ファイルにおける切替判定とは別です。
