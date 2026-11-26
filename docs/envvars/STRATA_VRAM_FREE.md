# `STRATA_VRAM_FREE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Windows の NVIDIA CUDA 実行経路で、Strata が空き VRAM を測る際に NVML のカード全体の値も取得し、CUDA runtime が返す値との小さい方を採用するための opt-in 設定である。`device_free_bytes()` の戻り値が専門家キャッシュの容量計算・割当て前確認や、起動後およびリクエスト時の空き VRAM 判定に使われる。環境変数自体がキャッシュを有効化するわけではなく、たとえば `--expert-cache auto` を指定したときに、そのキャッシュ枠数の見積もりへ反映される。CLI の既定は `--expert-cache 0` である（`engine/src/core/expert_cache.cpp:99-102,153-174`、`engine/src/program/generate.cpp:1416-1419,9077-9085,16080-16090,18528-18534`）。

NVML の値で CUDA の値を増やすことはなく、NVML が値を返さない場合は CUDA runtime の値を維持する。コード上、この設定は生成内容を直接選ぶ条件ではなく、VRAM に基づく容量・余裕の見積もりを変える（`engine/src/core/expert_cache.cpp:158-172`）。

## 値と判定

`std::getenv` で値を取得し、文字列全体を大文字小文字を区別して `"device"` と `std::strcmp` で比較する。数値変換、空白除去、部分一致、真偽値の解釈はしない（`engine/src/core/expert_cache.cpp:153-157`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `_WIN32`、非 HIP / 非 gfx906 / 非 Metal、非 SYCL（NVML 用コードが定義される Windows CUDA 経路） | CUDA runtime の空き値を使う | 完全一致の `device` | 空文字、`1`、`0`、`true`、`DEVICE`、`device `、`xdevice` など |
| 上記以外（Linux、HIP、Metal、SYCL、gfx906 互換ビルドなど） | CUDA/HIP 等の当該実装の値 | 該当なし。この変数を読む NVML 分岐はコンパイルされない | 値はこの機能には作用しない |

設定の有無ではなく値の完全一致で判定する。空文字や未知の文字列は警告なしで無効扱いとなり、値域・境界値はない。NVML 用コードは `_WIN32 && !STRATA_EC_NO_VMM && !SYCL_LANGUAGE_VERSION` のときだけ有効になり、`STRATA_EC_NO_VMM` は HIP、gfx906、Metal で定義される（`engine/src/core/expert_cache.cpp:5-9,26-36,153-157`）。SYCL は別実装の `engine/sycl/src/core/expert_cache.cpp` を使い、そこにこの変数の読み取りはない。

## 有効になる条件

- 上表の Windows CUDA ビルドであること。Linux、AMD HIP、Metal、SYCL ではこの NVML 読み取りは動かない（`engine/src/core/expert_cache.cpp:5-9,26-36`）。
- 値が完全一致で `device` であること。
- `device_free_bytes()` が呼ばれる経路であること。主な呼び出し元には、空き容量を使う drafter の可否判定、専門家キャッシュの自動サイズ決定と割当て前確認、起動後の空き量表示、サーバーのリクエスト開始時の記録がある（`engine/src/program/generate.cpp:8205-8215,9077-9085,9420-9435,9444-9483,16080-16090,18528-18534`、`engine/src/core/expert_cache.cpp:605-638`）。
- キャッシュ枠数は別の CLI 設定にも依存する。`--expert-cache auto` は空き量から枠数を算出し、予約量 `--vram-reserve-mib` などを差し引く。既定の `--expert-cache 0` はキャッシュを要求しない。明示枠数でも、プロファイルや per-layer のサイズ調整、割当て前確認など空き量を参照する経路には影響し得る（`engine/src/program/generate.cpp:1416-1419,3984-3987,9202-9229,9444-9483`）。
- NVML が利用でき、現在の CUDA device と対応する PCI bus ID の照会が成功すること。DLL のロード、必要な関数の解決・初期化、CUDA device 情報取得、NVML の device handle とメモリ情報取得のいずれかが失敗すれば CUDA の値へ戻る（`engine/src/core/expert_cache.cpp:48-79,158-172`）。

## 実行時の詳細

`device_free_bytes()` はまず `cudaMemGetInfo` から空き量を得る。NVML 対応ビルドでは、関数内の `static const bool device_wide` 初期化時に環境変数を一度だけ読み、プロセス中はその判定を使い続ける。したがって初回 `device_free_bytes()` 呼び出し後に環境を変更しても反映されない。一方、設定が有効な場合の NVML メモリ値の問い合わせ自体は `device_free_bytes()` の呼び出しごとに行われる（`engine/src/core/expert_cache.cpp:99-102,153-160`）。

最初の有効な NVML 問い合わせ時に `nvml.dll` をシステムディレクトリ限定でロードし、必要な関数を解決・初期化する。この `Lib` は static で、一度の初期化失敗後に再試行するコードはない。成功時は対象 GPU の NVML 空き量と CUDA runtime の空き量の最小値を返し、失敗時は CUDA runtime の値をそのまま返す（`engine/src/core/expert_cache.cpp:48-79,158-172`）。

自動キャッシュでは、この空き量を予約分・後続の割当て見込みと比較して枠数へ換算し、プロファイルがあればその長さも上限になる。キャッシュ割当て前の確認が不足を検出するとエラー理由を返し、起動後の自動キャッシュでは書込み後の再計測に基づく縮小も行う（`engine/src/program/generate.cpp:9202-9229,9444-9497,9640-9710`、`engine/src/core/expert_cache.cpp:619-638`）。サーバー経路では全ロード後の空き量を記録・表示し、各リクエスト開始時にも空き量を記録する（`engine/src/program/generate.cpp:16080-16092,18528-18550`）。

## ログと測定値

有効値の場合、初回の有効問い合わせで成功時に次の stderr 行を一度出す。MiB の数値はその問い合わせ時の NVML 値と CUDA 値である。

```text
strata generate: STRATA_VRAM_FREE=device: free VRAM is read for the whole card (NVML: %lld MiB now; CUDA's figure for this process alone: %lld MiB)
```

NVML が答えない場合は次を一度出し、空き量には CUDA の値を使う。

```text
strata generate: STRATA_VRAM_FREE=device: NVML did not answer (nvml.dll); free VRAM stays CUDA's figure for this process
```

変数が未設定・空文字・無効値の場合、または NVML 用分岐がないビルドでは、この設定固有の行は出ない（`engine/src/core/expert_cache.cpp:153-172`）。キャッシュ枠数が不足して割当て前検査に失敗した場合は `ExpertCache: ... only ... of VRAM is free ... Lower --expert-cache.` を含むエラーが生成側へ返される（`engine/src/core/expert_cache.cpp:625-638`）。

`docs/DETAILS.md:1728` は Windows NVIDIA の RTX 5090（WDDM）、128K context、画像 encoder 読込み、`--expert-cache auto` などの条件で、NVML と CUDA の観測値および起動後の空き量を記録している。これは資料に記載された測定であり、本調査で再測定した値ではない。同資料は AMD と Linux では未測定とし、コードの Windows CUDA 限定とも整合する。一方、`docs/SETTINGS.md:354` の一覧は適用先を「NVIDIA and AMD」としており、現行ソースのコンパイル条件より広い。

## 根拠

- `engine/src/core/expert_cache.cpp:5-9,26-36,43-79,99-175` — ビルド条件、NVML 読取り、値の完全一致、最小値採用、fallback とログ。
- `engine/src/program/generate.cpp:1416-1419,3984-3987,9077-9085,9202-9229,9444-9497,9640-9710` — CLI 既定・auto 判定、空き量を使うキャッシュ計算と割当て後の縮小。
- `engine/src/program/generate.cpp:16080-16092,18528-18550` — 起動後とリクエスト時の VRAM 記録・観測。
- `engine/sycl/src/core/expert_cache.cpp:145-168` — SYCL 側の別 `device_free_bytes()` 実装。この範囲に `STRATA_VRAM_FREE` の読み取りはない。
- `docs/DETAILS.md:1728`、`docs/SETTINGS.md:354` — 測定資料と設定一覧の適用先をソースと照合。
