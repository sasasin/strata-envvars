# `STRATA_VRAM_FREE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリ・driver 自身の環境変数動作は対象外。

## 役割

Windows CUDA の expert cache の空き VRAM 見積もりに、NVML から取得したカード全体の空き容量を使う opt-in 設定です。NVML の値が CUDA の当該プロセス向け空き容量より小さい場合にだけ、見積もりをその値まで下げます。expert cache の自動サイズ決定、割り当て前の容量検査、serve 起動後の空き容量警告など、`device_free_bytes()` を使う経路に影響します。

## 値と判定

| 状態 | 判定・動作 |
|---|---|
| 未設定 | 無効。CUDA の `cudaMemGetInfo()` の空き容量を使う |
| 空文字 | 無効。空文字列は `"device"` と一致しない |
| `device` | 有効。NVML が取得できれば CUDA の値との小さい方を返す |
| その他（`Device`、`1`、`true`、`device ` など） | 無効。警告やエラーにはせず、CUDA の値を使う |

値は `std::strcmp(v, "device") == 0` で文字列全体を大文字小文字を区別して比較します。数値変換、前後空白の除去、部分一致はありません。判定結果は `device_free_bytes()` 内の `static const bool` に初回呼び出し時に保存され、同じプロセスで環境変数を後から変更しても再評価されません。根拠: `src/core/expert_cache.cpp:139-143`。

## 有効になる条件

この環境変数を読むコードと NVML 取得処理は、`_WIN32 && !STRATA_EC_NO_VMM && !SYCL_LANGUAGE_VERSION` のときだけコンパイルされます。`STRATA_EC_NO_VMM` は HIP、HIP gfx906 compatibility、Metal で定義されるため、対象は Windows の非 HIP・非 Metal・非 SYCL CUDA 経路です。ほかの OS/backend ではこの変数を読みません。ビルド条件の根拠: `src/core/expert_cache.cpp:4-8,25-35,139`。

設定が有効でも、NVML の DLL・必要な関数・初期化・CUDA デバイス情報・PCI bus ID によるデバイス照合・メモリ情報取得のいずれかが失敗すると、NVML 値は使われず CUDA の値が維持されます。NVML が成功しても値を増やすことはなく、`std::min(free_b, nvml_b)` によって小さい場合だけ空き容量を減らします。根拠: `src/core/expert_cache.cpp:47-78,144-158`。

## 実行時の詳細

NVML は `nvml.dll` を `LOAD_LIBRARY_SEARCH_SYSTEM32` 指定でロードし、関数ポインターを関数内 static の `Lib` に保持します。デバイスごとの取得では現在の CUDA device の PCI 情報を使います。Strata は NVML が返した free bytes を CUDA の `free_b` と比較し、その小さい値を `device_free_bytes()` の戻り値にします。DLL のロードと API 呼び出しは Strata が行う処理として記述しており、NVML/driver 内部の挙動はここでは説明しません。根拠: `src/core/expert_cache.cpp:47-78,98-100,144-160`。

主な利用箇所は、`--expert-cache auto` の空き容量ベースのスロット計算（`src/program/generate.cpp:6870-6876,6952-6973`）、layer split・per-layer/profile sizing 等の計算（同 `:6699-6701,7046-7057,7068-7074,7093-7104`）、`ExpertCache::open()` の割り当て前検査（`src/core/expert_cache.cpp:560-594`）、cache 配置後の自動 cache 縮小判断（`src/program/generate.cpp:7230-7246`）、serve 起動時の空き容量表示と警告（同 `:12166-12194`）です。自動サイズでは `--vram-reserve-mib`、prompt buffer・draft head・pipeline window などに確保する量を差し引いて slot 数を決めます。`--expert-cache N` の明示指定はその slot 要求を行い、`--expert-cache auto` はこの空き容量見積もりから slot 数を決めます（`src/program/generate.cpp:6929-6954`）。明示指定でも `ExpertCache::open()` の事前容量検査は行われ、足りなければ `ExpertCache: ... Lower --expert-cache.` を返して起動側がエラーを出します（`src/core/expert_cache.cpp:581-593`; `src/program/generate.cpp:7200-7228`）。

NVML を有効にして初めて取得結果が得られたか、取得できなかったかを示すメッセージは、プロセス内で一度だけ stderr に出ます。成功時は `strata generate: STRATA_VRAM_FREE=device: free VRAM is read for the whole card (NVML: ... MiB now; CUDA's figure for this process alone: ... MiB)`、失敗時は `strata generate: STRATA_VRAM_FREE=device: NVML did not answer (nvml.dll); free VRAM stays CUDA's figure for this process` です（`src/core/expert_cache.cpp:144-158`）。不正値や未設定に対する専用ログはありません。serve 起動後は計算した空き容量が 256 MiB 以上なら通常ログ、未満なら LOW または reserve-adjusted warning が stderr に出ます（`src/program/generate.cpp:12175-12194`）。この変数自体が終了を起こす分岐はありませんが、容量見積もりが expert cache のサイズや割り当て失敗につながる場合があります。

## 根拠

- 唯一の環境変数読み取りと値判定、NVML 結果の適用: `src/core/expert_cache.cpp:139-160`。
- Windows CUDA 等の compile guard、および NVML の取得失敗条件: `src/core/expert_cache.cpp:4-8,25-35,47-78`。
- 割り当て前の VRAM 検査・不足時のエラー: `src/core/expert_cache.cpp:560-594`。
- 自動 cache のサイズ計算と reserve の適用: `src/program/generate.cpp:6870-6876,6929-6973`。
- serve 起動後の計測ログ・警告: `src/program/generate.cpp:12166-12194`。
- 既存資料も `STRATA_VRAM_FREE=device` を Windows/NVIDIA の opt-in とし、Linux・AMD では未測定（コード上もこの取得機能はビルドされない）と記しています。測定値は資料記載の環境に限るもので、本調査で再測定していません: `docs/DETAILS.md:1449`; `docs/release-notes-0.2.7.md:53`。
