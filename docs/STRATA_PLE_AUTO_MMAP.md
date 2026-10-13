# `STRATA_PLE_AUTO_MMAP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

PLE（per-layer token embedding）GGUF を既定の direct I/O で開いているとき、起動時の読み取り probe が遅いと判定した場合に、読み取り方式を `mmap` に切り替えるかを制御します。対象は `strata generate` の CUDA 実装と SYCL 実装です。値が有効でも、遅い probe が成立した場合に限って切り替えます。

## 値と判定

実装は `std::getenv()` で値を取得し、`std::atoi()` の結果を 0 と比較します。文字列全体の妥当性検査はありません。

| 環境変数 | 判定 |
|---|---|
| 未設定 | 自動切り替えを無効にする |
| 空文字 | `atoi("") == 0` のため無効 |
| 設定値の `atoi()` 結果が 0 | 無効。例: `0`, `0abc`, `abc` |
| 設定値の `atoi()` 結果が非 0 | 自動切り替えを許可。例: `1`, `2`, `-1`, `1abc`, ` 1` |

`atoi()` は先頭の空白と符号を受け付け、数字列の後ろにある文字列を検査しません。数値として読める先頭部分がない場合は 0 になります。環境変数は direct probe が遅い場合にその場で読み取られます。static cache はなく、この切り替え判定は PLE 初期化中に一度だけ行われます。

## 有効になる条件

自動切り替えには、次の条件がすべて必要です。

- PLE テーブルがあり、初期 I/O モードが `direct` である。`--ple-io mmap` と `--ple-io ram` は probe の対象外です。
- `STRATA_PLE_PROBE` が未設定である。設定値の内容は見ず、設定されていれば probe 自体を行いません。
- `ple_direct_rows_per_s()` が正の値を返し、その値が 15,000 rows/s 未満である。テーブルの行数が 4,096 未満、読み取り失敗などで計測値が 0 以下なら自動切り替えも遅さの警告も出ません。
- `--ple-io` を明示していない。`--ple-io direct` を指定すると、環境変数が非ゼロでも自動切り替えを行わず、遅い場合は警告だけを出します。
- `STRATA_PLE_AUTO_MMAP` の `atoi()` 結果が非 0 である。

このため、既定の `direct` で使う場合に、この環境変数を非ゼロにすると、遅い probe のとき `mmap` への切り替えが許可されます。値が未設定または 0 の場合は、遅い probe のときも `direct` のまま警告します。CLI で `mmap` / `ram` を選んだ場合はこの変数による追加動作はありません。

## 実行時の詳細

エンジンは PLE テーブルを `direct` で一度開いた後、最大約 0.6 秒の probe を実行します。probe は最大 64 バッチ、1 バッチ 64 行を読み、行数が 4,096 未満なら実行せず `-1` を返します。計測値が 15,000 rows/s 以上なら stderr に `strata generate: PLE direct read probe: ... (fine)` を出します。

遅いと判定され、自動切り替えが許可された場合は stderr に `using --ple-io mmap instead` を含む案内を出してテーブルを閉じ、`mmap` モードで開き直します。開き直しに失敗すると `strata generate: <error>` を出し、終了コード 1 で戻ります。切り替えが許可されない場合は `WARNING: --ple-io direct measures slow here` を出して direct を維持します。警告には prompt の読み取りが遅くなり stall watchdog に達する可能性と、`mmap` または `ram` を選ぶ案内が含まれます。

## 根拠

- `src/program/generate.cpp:1747-1765`、`sycl/src/program/generate.cpp:1635-1653`: direct 読み取り probe。行数下限、バッチ、時間上限、失敗時の戻り値。
- `src/program/generate.cpp:1886-1888`、`sycl/src/program/generate.cpp:1740-1742`: `--ple-io` の指定を `ple_io_explicit` に記録。
- `src/program/generate.cpp:3187-3190,3206-3208,3210-3243`、`sycl/src/program/generate.cpp:3004-3006,3023-3061`: PLE があるときの初期モード、probe 条件、閾値、自動切り替えと警告。CUDA と SYCL の該当ロジックは同じ。
- `docs/DETAILS.md:1868-1870`: direct が既定であること、遅い probe は通常は警告のみで、`STRATA_PLE_AUTO_MMAP=1` が旧来の `mmap` 切り替えを有効にするという資料上の説明。ソースでは `atoi()` が 0 以外の値を許容し、明示的な `--ple-io direct` では環境変数による切り替えを抑止します。
