# `STRATA_FETCH_PVM`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。ソースツリーには未追跡の benchmark 結果ディレクトリがあったが、以下は HEAD の Strata 所有ソースと資料に基づく。

## 役割

Windows の SYCL 実装で、GGUF 内の expert をメモリマップ経由で staging buffer にまとめて読み込む前に、読み込み対象ページを `PrefetchVirtualMemory` で先行要求するかを切り替える変数です。これは実験用の A/B スイッチです。通常は API を使い、`STRATA_FETCH_PVM=0` で呼び出しを無効にします。

対象コードは `sycl/src/core/expert_source.cpp` の `FileExpertSource::fill_many()` です。CUDA/HIP 実装や Linux の同名制御は見つかりませんでした。

## 値と判定

環境変数全体の文字列比較ではなく、`std::atoi()` の結果が 0 かどうかで判定します。

| 値 | 挙動 |
|---|---|
| 未設定 | `PrefetchVirtualMemory` を動的に検索し、見つかれば使用する（既定） |
| `0`、空文字、数値に変換できない文字列 | `atoi` が 0 を返すため API を無効にする |
| 0 以外に変換される値 | API を検索して使用する。例: `1`, `-1`, `2`, `1abc` |
| `0abc` | 先頭の数値部分が 0 なので無効 |

`atoi` のため、先頭の空白や符号を含む数値接頭部が変換され、後続文字列は無視されます。数値全体の妥当性検査や範囲制限はありません。

## 有効になる条件

- Windows ビルドであること（環境変数の処理自体が `_WIN32` の条件コンパイル内）。
- `FileExpertSource::fill_many()` に未処理の fill が渡ること。
- unbuffered/direct 読み込みではないこと。`direct_` が空なら PVM 分岐へ進み、空でなければ direct 読み込み後に関数から戻るため、この変数は参照されません。
- GGUF をその場でマップする経路であること。通常の `experts.bin` は `role_ptr_` を設定せず、この staging/prefetch 経路を使いません。GGUF 経路は、native layout で pack に `experts.bin` がなく、対応する GGUF 情報がある場合に `open_gguf()` でファイルをマップし、3 種類の role 範囲を `role_ptr_` に設定します。
- `kernel32.dll` に `PrefetchVirtualMemory` が存在すること。見つからない場合は API 呼び出しをせず、通常の fill 処理を続けます。

## 実行時の詳細

`FileExpertSource::prefetch()` は staging 対象の expert を収集し、`fill_many()` に渡します。CPU 側で処理する expert の欠落分を layer 単位で集める呼び出し元もあります。`fill_many()` は Windows で、各 expert の gate/up/down に対応する3範囲を `WIN32_MEMORY_RANGE_ENTRY` 配列に追加し、`GetCurrentProcess()` と共に PVM 関数へ一括で渡します。その直後に複数スレッドで各 fill を処理します。PVM の戻り値は破棄されるため、失敗時の専用エラーや警告はありません。

API 関数ポインターは `fill_many()` 内の関数ローカル `static` として初回に一度だけ解決されます。そのため最初の対象 fill で環境変数を評価し、その後にプロセス環境を変更しても再評価しません。明示的なログ出力もありません。

関連資料 `docs/DETAILS.md` は、GGUF 直読みでは expert を複数スレッドで取得し、Windows では `PrefetchVirtualMemory` による一括ページ要求を行うと説明しています。`experts.bin` のある pack にはこの GGUF 直読み経路を適用しないという記述も実装と一致します。同資料には `STRATA_FETCH_PVM` の値判定や性能測定は記載されていません。資料の説明を超える速度向上は確認していません。

## 根拠

- `sycl/src/core/expert_source.cpp:491-501`: native layout で `experts.bin` がなく GGUF 情報がある場合に `open_gguf()` へ進む。
- `sycl/src/core/expert_source.cpp:713-788`: GGUF shard をマップし、expert の3 role範囲を `role_ptr_` / `role_bytes_` に保持する。
- `sycl/src/core/expert_source.cpp:909-949`: staging 対象を集めて `fill_many()` に渡す経路。`prefetch_pairs()` は direct/unbuffered 向けである。
- `sycl/src/core/expert_source.cpp:968-1030`: direct 経路の早期 return、環境変数の `atoi` 判定、関数ポインターの動的解決、範囲の一括要求、および後続の複数スレッド処理。
- `sycl/src/core/expert_source.cpp:2362-2385`: resident copy にない blob が staging またはマップ済みファイルから返される。
- `sycl/src/core/expert_source.cpp:2728-2736`: SYCL 実行中に CPU 処理対象 expert をまとめて `prefetch()` する呼び出し。
- `docs/DETAILS.md:215-224`: GGUF 直読みの条件、複数スレッド取得、および Windows の一括ページ要求。
