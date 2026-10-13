# `STRATA_WDDM_BUDGET`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの内部動作と生成された SYCL 移植コードは対象外。

## 役割

Windows の HIP ビルドで、WDDM がこのプロセスに割り当てたローカル video memory budget を空き VRAM の見積もりに反映する処理を無効化します。既定では処理が有効です。Strata は HIP の `hipMemGetInfo` が返した `free_bytes` から、カード総量と DXGI budget の差を差し引きます。`total_bytes` は変更しません。

この値を参照するのは `STRATA_USE_HIP && _WIN32` の実装です。Windows CUDA、Linux の HIP、その他の build では、この環境変数を読むこの処理は有効になりません。

## 値と判定

コードは値全体を検証せず、C の `std::atoi` で `int` に変換し、変換結果が `0` かどうかだけを見ます。

| 環境変数 | `off` の値 | free VRAM 調整 |
|---|---|---|
| 未設定 | `false` | 有効（既定） |
| 空文字 | `true`（`atoi("") == 0`） | 無効 |
| 数字で始まらない文字列 | `true`（変換結果 0） | 無効 |
| `0`、`00`、`0suffix` | `true` | 無効 |
| `1`、`1suffix`、`-1` | `false`（変換結果が非 0） | 有効 |

先頭の空白と符号は `atoi` の変換規則に従い、数字列の後ろにある文字列は判定されません。したがって、これは「`0` のときだけ無効」ではなく、「`atoi` の結果が 0 なら無効」です。`atoi` の変換範囲外の値について、Strata 側に検証や fallback はありません。

## 有効になる条件

- Windows (`_WIN32`) かつ HIP (`STRATA_USE_HIP`) の build であること。
- `cudaMemGetInfo` に null ではない二つの出力ポインターを渡し、最初の呼び出しで `off` が初期化されること。
- `hipMemGetInfo` が成功し、環境変数で無効化されていないこと。
- 現在の HIP device と DXGI adapter の対応を取得でき、`QueryVideoMemoryInfo` が成功し、DXGI の `local.Budget` が 0 より大きく、HIP の `total_bytes` 未満であること。

条件を満たさない場合は、HIP が返した `free_bytes` をそのまま返します。DXGI DLL、adapter、budget 情報を使えない場合にも、Strata は別の見積もりで置き換えません。

## 実行時の詳細

Windows HIP 用互換ヘッダーは `cudaMemGetInfo` を `strata::hip_compat::mem_get_info` に割り当てます。そのため、エンジン各所の空きメモリー照会はこの関数を通り、値は device のメモリー情報や expert cache、その他の GPU バッファーの空き容量見積もりに使われます。たとえば `device_info()` は返された free/total を `DeviceInfo` に保存し、起動時のメモリー計画表示に使います。キャッシュ自動サイズ決定なども `cudaMemGetInfo` または `device_free_bytes()` を利用します。

環境変数の判定結果は関数内の `static const bool off` に保存され、最初の有効な引数での呼び出し時に一度だけ読み取られます。その後プロセス内で環境を書き換えても反映されません。無効でない場合、毎回現在の HIP free/total を取得し、現在の device の DXGI local budget を問い合わせます。budget が使えるときは `withheld = total_bytes - local.Budget` を計算し、`free_bytes` から差し引きます。差し引く量が free より大きい場合は 0 にします。成功した最初の調整時だけ、次の stderr ログを出します。

```text
strata: Windows budgets N of this card's M MiB for this process; free VRAM is counted within that (STRATA_WDDM_BUDGET=0: off)
```

## 文書との照合

`docs/AMD_HIP.md` は Windows HIP で `hipMemGetInfo` の free 値を Windows の video memory budget に合わせて引き下げることと、`STRATA_WDDM_BUDGET=0` で無効化できることを説明しています。実装上は `atoi(...) == 0` による判定なので、空文字や数字で始まらない文字列も無効化します。資料にある RX 6800 の速度比較は既存の報告値であり、この調査で再測定した値ではありません。

## 根拠

- `include/strata/hip_compat/cuda_runtime.h:84-95` — Windows HIP で `cudaMemGetInfo` を Strata の互換関数へ割り当てる条件。
- `src/core/device.cu:106-127,182-209` — Windows HIP 限定の関数、環境変数判定、DXGI budget 取得、free 値の補正とログ。
- `src/core/device.cu:134-159` — device ordinal から DXGI adapter を取得し、一度試した adapter を保存する処理。
- `src/core/device.cu:247-279` — `device_info()` の free/total 取得。
- `src/core/expert_cache.cpp:28-30,490-491` — `device_free_bytes()` が `cudaMemGetInfo` を呼ぶ経路。
- `src/program/generate.cpp:4801-4828` — expert cache 自動サイズ決定時に使う空き容量と Windows HIP の予約量判定。
- `docs/AMD_HIP.md:92-98` — 仕様説明と報告された RX 6800 の比較。速度値は測定条件付きの文書記載であり、本調査による検証ではない。
