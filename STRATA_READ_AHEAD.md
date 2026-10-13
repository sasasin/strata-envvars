# `STRATA_READ_AHEAD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Linux で Strata がファイルの読み込み前に OS へ先読みを依頼する処理を止めるスイッチです。エンジンでは `madvise(..., MADV_WILLNEED)` と `posix_fadvise(..., POSIX_FADV_WILLNEED)` の呼び出しを抑止します。Windows のエンジン実装はこの先読み API を何もしないため、この変数は影響しません。

対象は同期読み込みそのものではなく、OS への先読みヒントです。ヒントの失敗は戻り値を無視するため、環境変数を有効にしても OS が読み込みを完了する保証はありません。

## 値と判定

| 経路 | unset | 設定時の判定 |
|---|---|---|
| Linux エンジン（CUDA/SYCL 共通の platform helper） | 有効 | `std::atoi(value) != 0` なら有効、`== 0` なら無効 |
| Windows エンジン | 常に無効 | `read_ahead_enabled()` が常に `false`。値を読まない |
| `strata-vision`（非 Windows の同梱ツール） | 有効 | `std::atoi(value) != 0` なら有効、`== 0` なら無効 |
| `strata-vision`（Windows） | この処理を実行しない | 先読み箇所全体が `!_WIN32` で除外される |

`atoi` を使うため、文字列全体の厳密な数値検証はありません。空文字や数値に変換できない文字列は 0 と判定され無効です。先頭の空白や符号の後から数字列を読み、数字列より後ろの文字は判定に使われません（例: `2junk` は有効、`0junk` は無効、`01` は有効）。負の非ゼロ整数も有効です。整数範囲を超える値について、ソースは検証や fallback を設けていません。

根拠: `src/platform/memory.cpp:150-155`, `src/platform/memory.cpp:117-119`, `tools/vision/strata_vision.cpp:102-113`。

## 有効になる条件

- エンジンの先読みは非 Windows ビルドでのみ実装されています。Windows は `read_ahead_enabled()` が常に false を返し、両方の `advise_willneed` overload も空実装です。
- Linux エンジンの値は `read_ahead_enabled()` の関数内 static 変数に保存されます。したがって最初の呼び出し時に一度読み、プロセス内で後から環境を書き換えても判定は変わりません。
- `strata-vision` の projector 先読みは `llama_backend_init()` の後、モデル読み込み前に環境を直接読みます。エンジン helper の static cache とは別判定です。
- CUDA/SYCL や機能経路が先読み API を呼ばない場合、この変数による追加の処理はありません。ファイル tier が unbuffered の場合は、expert source が mapped-read の `advise_pairs` を拒否します。

## 実行時の詳細

Linux の helper は環境変数が unset なら先読みを有効にし、設定されていれば `atoi` の結果が非ゼロかを初回に判定します。有効時、メモリマップ範囲には 128 KiB ごとの `madvise(..., MADV_WILLNEED)`、開いたファイルの範囲には 128 KiB ごとの `posix_fadvise(..., POSIX_FADV_WILLNEED)` を依頼します。範囲が null/0 byte、または fd が負なら何もしません。各 OS 呼び出しの戻り値は無視されます（`src/platform/memory.cpp:146-169`）。

エンジンでは、プロファイルから GPU expert cache を埋める際に mapped expert の先読みを行います。CUDA 経路では `STRATA_FILL_AHEAD` が別途先読みする expert 数を決め、既定 256 です。`STRATA_READ_AHEAD=0` はその数を変えず、OS への先読み依頼を無効にします（`src/program/generate.cpp:5152-5173`）。SYCL にも同様の profile fill 経路があります（`sycl/src/program/generate.cpp:4714-4733`）。また SYCL の file expert source は mapped complement を構築する際、layer 内の対象 expert を `advise_pairs` で先読みします（`sycl/src/core/expert_source.cpp:2048-2054`）。peer expert cache の mapped fill も先読み helper を使います（`src/core/peer_experts.cpp:160-168`）。

ほかに、非 Windows の native dense/native head/native embedding 読み込み（`src/core/native_dense.cpp:264-267`, `src/core/native_head.cpp:47-55`, `src/core/native_head.cpp:131-140`）、native weights pack のファイル読み込み（`src/core/weights.cpp:277-289`）、MTP draft ファイル読み込み（`src/core/mtp.cpp:117-124,301-315`）が同じ helper を使います。同梱 `strata-vision` は非 Windows で projector ファイル全体を 128 KiB 単位に先読みしてからモデルをロードします（`tools/vision/strata_vision.cpp:101-113`）。

## 文書との照合

`docs/DETAILS.md:282-286` は Linux で weights、native dense matrices、GPU cache fill、resident RAM copy、MTP draft files を 128 KiB 単位で先読みし、`STRATA_READ_AHEAD=0` で止めると説明しています。呼び出しコードと整合します。同節の性能値（Gen3 NVMe / RTX 5090 / 32 GB / Q2_0 resident at 262K で ready 70 秒対約 920 秒、fill 39 MB/s 対 3.2 GB/s）は資料に記載された測定としての引用であり、この調査で再測定した値ではありません。`docs/TROUBLESHOOTING.md:64-67` も Linux の先読みと無効化を説明しています。

## 根拠

- 判定と OS ごとの差: `src/platform/memory.cpp:117-119,146-169`; API 宣言と説明: `include/strata/platform/memory.hpp:56-62`。
- profile fill と別変数 `STRATA_FILL_AHEAD`: `src/program/generate.cpp:5152-5173`, `sycl/src/program/generate.cpp:4714-4733`。
- mapped expert source / peer fill: `sycl/src/core/expert_source.cpp:951-966,2048-2054`, `src/core/peer_experts.cpp:160-168`。
- その他のエンジン読み込み経路: `src/core/native_dense.cpp:264-267`, `src/core/native_head.cpp:47-55,131-140`, `src/core/weights.cpp:277-289`, `src/core/mtp.cpp:117-124,301-315`。
- 同梱ツール: `tools/vision/strata_vision.cpp:101-113`。
- 説明と測定条件: `docs/DETAILS.md:282-286`, `docs/TROUBLESHOOTING.md:64-67`。
