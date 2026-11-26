# `STRATA_PLE_AUTO_RAM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata generate` が PLE（n-gram）テーブルを既定の direct 読み込みから、メモリマップして RAM にロックする読み込みへ自動で切り替える residency policy の許可スイッチ。値が有効でも、CLI・OS・モデル・メモリ条件を満たさなければ切り替わらない。読み取りは `engine/src/program/generate.cpp` の PLE テーブル初期化中に行われる（`engine/src/program/generate.cpp:6269-6307`）。

## 値と判定

`std::getenv` の結果を `ple_auto_ram_allowed` に渡し、設定されていれば `std::atoi(value) != 0` を許可とする。文字列全体の数値検査ではない。空文字・数値に変換できない先頭・`0` から始まる値（例 `0anything`）は 0 になり無効、`1`・`-1`・`1anything` は非ゼロとなり有効。`atoi` の通常の先頭空白処理も適用される。大文字小文字による文字列比較はない。`atoi` で表現できない範囲の値は C ライブラリ仕様上の変換結果を保証できない（`engine/include/strata/core/ple_residency.hpp:32-37`）。

| 条件 | 未設定 | 設定時に許可となる値 | 設定時に不許可となる値 |
|---|---|---|---|
| Apple 以外 | `STRATA_DEFAULTS=026` でなければ許可 | `atoi` が非 0（例 `1`, `-1`, `1x`） | `atoi` が 0（例 `0`, 空文字, `false`, `0anything`） |
| Apple | 不許可 | 文字列が厳密に `1` の場合だけ | 上記以外すべて（`01`, `1x`, `-1` も不許可） |

Apple 以外で未設定なら既定では許可されるが、`STRATA_DEFAULTS` が厳密に `026`、`0.2.6`、`v0.2.6` のいずれかなら不許可。明示された `STRATA_PLE_AUTO_RAM` はこの既定を上書きする。`STRATA_DEFAULTS` は helper 内の関数 static に一度保存される（`engine/include/strata/core/defaults_026.hpp:21-29`; `engine/include/strata/core/ple_residency.hpp:34-37`）。

## 有効になる条件

- `--ple-gguf` またはモデルから検出された PLE テーブルが存在し、初期読み込みに成功していること。PLE テーブルがない経路では判定されない（`engine/src/program/generate.cpp:5127-5134, 6269-6290`）。
- `--ple-io` が指定されていないこと。明示指定は環境変数より優先し、`--ple-io ram` / `mmap` はその指定どおり、`--ple-io direct` は direct のままになる。オプションの値は `ram` / `mmap` 以外は初期化時に direct として扱われるが、明示指定フラグにより自動 policy は通らない（`engine/src/program/generate.cpp:818-819, 3901, 6270-6272, 6303-6307`）。
- 許可判定が true であること。Apple では環境変数が厳密に文字列 `1` でなければならない（`engine/src/program/generate.cpp:6303-6315`）。
- PLE テーブルサイズと routed experts の RAM 見積もりがともに既知かつ正で、合計のオーバーフローがなく、利用可能 RAM が「PLE テーブル + expert arena + 8 GiB」以上であること。利用可能量は `available_host_bytes()` の値を使い、メモリ情報不明・テーブルサイズ 0・arena サイズ 0 は不許可となる。`STRATA_MEMORY_LIMIT_MIB`、`--memory-limit-mib` や cgroup 制限を含む利用可能量算定の詳細は `conversation_memory.hpp` にある（`engine/src/program/generate.cpp:6316-6324`; `engine/include/strata/core/ple_residency.hpp:25-29`; `engine/include/strata/core/conversation_memory.hpp:11-35, 126, 143-146`）。
- ビルド上の特別な制限は Apple 判定（`__APPLE__`）以外、当該分岐にはない。CUDA/HIP/SYCL の選択による別の値判定は確認できない（`engine/src/program/generate.cpp:6303-6317`）。

## 実行時の詳細

PLE テーブルをまず現在の `pio` 設定（通常 direct）で開き、その直後に自動 policy を評価する。環境変数はこの初期化時に `getenv` で読み、以後の環境変更を追跡しない。許可・メモリ条件を満たすと、テーブルを閉じて mmap + lock 設定で開き直す。成功時は `--ple-io ram` 相当の PLE 行読み込みになるが、トークン選択や生成設定を変える処理ではない（`engine/src/program/generate.cpp:6269-6276, 6288-6290, 6303-6337`）。

自動 mmap で開き直せなければ `resident PLE table failed (...); keeping direct reads` を stderr に出し、元の direct 設定で再オープンする。再オープンにも失敗すると通常の `strata generate: <error>` を出して終了コード 1 を返す（`engine/src/program/generate.cpp:6338-6346`）。成功した場合は policy による ram 選択を stderr に記録する（次節）。

`--serve` ではサーバーが `dict(os.environ)` を元に子エンジン用環境を作り、設定の `env` が同名キーを上書きして子へ渡す。したがって親プロセス環境の値は継承されるが、serve 設定に `STRATA_PLE_AUTO_RAM` があればその値が優先され、エンジン起動時の判定に使われる（`terminal/serve/server.py:4007-4028, 9391-9394`）。

更新機能の軽量テスト起動では、updater が `TEST_ENV` として値 `0` を設定し、ユーザー設定をマージした後にテスト用設定を上書きする。これは updater のテスト実行用であり、通常のエンジン起動の既定値ではない（`terminal/strata_control/updater.py:1218-1224, 1395`）。

## ログと測定値

自動選択成功時、stderr に次の形式で表示する（数値部分は実行時の見積値）。

```text
strata generate: --ple-io ram chosen by the residency policy (the table is %.1f GiB, the expert arena still to fill %.1f GiB and %.1f GiB of RAM is available; STRATA_PLE_AUTO_RAM=0 keeps the direct reads, --ple-io direct forces them)
```

このログは自動選択が成功した場合に限られ、未設定・無効値やメモリ不足だけを理由とするログはこの分岐にはない。マップ再オープン失敗時の fallback 文言は `engine/src/program/generate.cpp:6330-6346` にある。文書化された資料・コメントには条件付きの過去測定があるが、今回の調査では再測定していない（`engine/src/program/generate.cpp:6292-6302`）。

## 根拠

- 直接読み取りと条件分岐: `engine/src/program/generate.cpp:6269-6307, 6316-6348`
- 値変換と `STRATA_DEFAULTS` 既定値: `engine/include/strata/core/ple_residency.hpp:32-37`; `engine/include/strata/core/defaults_026.hpp:21-29`
- メモリ admission: `engine/include/strata/core/ple_residency.hpp:25-29`; `engine/include/strata/core/conversation_memory.hpp:11-35, 126, 143-146`
- CLI 優先順位: `engine/src/program/generate.cpp:818-819, 3901, 6270-6272`
- serve 子プロセス環境: `terminal/serve/server.py:4007-4028, 9391-9394`
- updater 軽量テストの上書き: `terminal/strata_control/updater.py:1218-1224, 1395`
