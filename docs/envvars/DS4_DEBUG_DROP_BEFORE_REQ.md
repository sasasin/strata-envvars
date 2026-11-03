# `DS4_DEBUG_DROP_BEFORE_REQ`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査対象の Strata checkout は `main` で、調査開始時の `git status --short --branch` は `## main...origin/main` だった。

## 役割

`DS4_DEBUG_DROP_BEFORE_REQ` は DS4 の `DISK_SKIP_AUTO` 切り替えを試すための診断用フックです。指定したリクエスト番号の開始前に、プロセスが使うモデルファイルのページをメモリから追い出す処理を呼び出します。この値だけでは作動せず、`STRATA_DS4_DISK_SKIP_W` が正で、かつ `STRATA_DS4_DISK_SKIP_AUTO` が 0 以外である必要があります。通常の expert 読み込みや生成内容を直接選ぶ設定ではありません。

## 値と判定

`Model::Impl` の初期化時に `env_f("DS4_DEBUG_DROP_BEFORE_REQ", 0.0f)` で読み、その `float` を `int` に変換して保持します。helper は変数が未設定なら既定値を返し、設定されていれば `std::atof()` を使います。したがって、文字列全体の厳密な検証はありません。

| 値 | 判定と結果 |
|---|---|
| 未設定 | 既定値 `0`。退避処理は呼ばれない |
| 空文字・数値として読めない文字列 | `atof` が `0` を返し、退避処理は呼ばれない |
| 正の有限数（例: `3`, `3.9`, `3tail`） | `atof` が読む数値部分を `float` にし、`int` への変換で小数部をゼロ方向に切り捨てる。変換後の整数番号で一致判定する |
| 0、負数、または正でも整数化後に 0 となる値 | `debug_drop_before > 0` を満たさず、退避処理は呼ばれない |

数値の後ろにある文字列は検証されず、例えば `3tail` は数値部分の `3` として扱われます。`atof` の結果を `float`、さらに `int` に変換する前に、有限性や `int` の範囲を検査するコードはありません。範囲外値の結果はこの実装から保証できません。

## 有効になる条件

- `STRATA_DS4_DISK_SKIP_W` の変換値が `0` より大きい。
- `STRATA_DS4_DISK_SKIP_AUTO` の `atof` 変換値が `0` 以外。
- 上記は DS4 `Model::Impl` の初期化時に評価される。片方でも条件を満たさなければ `begin_request()` は最初に戻り、要求番号を進めず、ページ退避もログ出力もしない。
- この診断値が指定するのは `begin_request()` が数えるリクエスト番号である。自動切り替えが無効な経路や、`begin_request()` を呼ばない入力には適用されない。DS4 の CLI は prompt の feed 前に、DS4 serve は新しい要求の開始時にこの関数を呼び出す。

`STRATA_DS4_DISK_SKIP_W` と `STRATA_DS4_DISK_SKIP_AUTO` はそれぞれ別個に解釈されます。前者は `atof` の値を 0 以上に clamp した値、後者は `atof` の値が 0 以外かどうかで判定されます。この文書の対象変数は、その両方を満たす場合にだけ参照されます。

## 実行時の詳細

`begin_request()` は自動切り替えが有効な場合にリクエスト数を 1 増やします。その番号が `DS4_DEBUG_DROP_BEFORE_REQ` の整数値と一致すると、`os::drop_cached(pk.maps, pk.fds)` を呼び、その直後に stderr へ次の形式で出力します。

```text
ds4: DISK_SKIP auto test: this process's file pages dropped before request <番号>
```

ログは退避 API の戻り値を検査せずに出すため、実際に全ページが退避されたことを保証する成功ログではありません。番号はモデルインスタンス内で数えられ、一致した一度だけ処理されます。値は `Model::Impl` の初期化時に読み込んで保持するため、プロセス実行中に環境を書き換えても反映されません。

退避 helper は Windows では各モデル file mapping に `VirtualUnlock` を呼び、続けて現在のプロセスに `K32EmptyWorkingSet` を呼びます。非 Windows の経路では各 mapping に `madvise(..., MADV_DONTNEED)`、各 file descriptor に `posix_fadvise(..., POSIX_FADV_DONTNEED)` を呼びます。いずれも戻り値を無視しており、失敗時の専用警告・終了・fallback はありません。これらの呼び出し後に生成が続きます。各 API や OS が実際にページをどう処理するかは Strata の制御範囲外です。

## 根拠

- `src/dsv41/ds4_model.cu:1352` — `env_f` は未設定時に既定値を返し、設定時に `std::atof` で変換する。
- `src/dsv41/ds4_model.cu:1397-1400,1441-1445` — `STRATA_DS4_DISK_SKIP_W` の正値と `STRATA_DS4_DISK_SKIP_AUTO` の非ゼロ値が自動切り替えの条件であり、対象値は既定 `0.0f` から `int` に変換される。
- `src/dsv41/ds4_model.cu:1446-1457,1492-1500` — request counter はモデル状態として保持され、自動切り替えが無効なら戻り、一致番号で退避 helper を呼んで stderr に出力する。
- `src/dsv41/ds4_model.cu:14946` — 公開 `Model::begin_request()` は内部実装へ委譲する。
- `src/dsv41/ds4_main.cpp:2690-2695,1375,1843-1847` — CLI prompt と serve の要求開始経路から `begin_request()` を呼ぶ。
- `src/dsv41/ds4_os.hpp:442-456` — Windows と非 Windows の退避 API、および戻り値を検査しない実装。
