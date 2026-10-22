# `STRATA_IO_PF_BUDGET_MB`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリ・ドライバーの環境変数は対象外。

## 役割

Linux file tier の I/O read-ahead scheduler が、decode window ごとに採用する speculative read-ahead の総バイト上限を固定します。値は MiB 単位で指定し、内部ではバイト数に変換します。scheduler が無効なら、この値を読み込んでも予測 read-ahead の採用制限には使われません。

## 値と判定

実装は `std::getenv()` で設定有無を調べ、設定されていれば `std::atof()` で数値の先頭部分を `double` に変換します。文字列全体の検証はせず、変換結果に `max(0.0, value * 1048576.0)` を適用してから `uint64_t` にします。

| 値 | 内部値と結果 |
|---|---|
| 未設定 | `io_budget_fixed_` は既定値 0 のまま。実測値による自動予算を使う |
| 空文字・数値に変換できない文字列 | `atof()` は 0 になり、固定値 0。自動予算を使う |
| `0`、負数 | 0 に丸められ、自動予算を使う |
| 正数 | MiB 値に 1,048,576 を掛けた値をバイト数に変換し、その値を固定上限として使う。小数部は整数変換時に切り捨てられる |
| 数値の後ろに文字が続く値 | `atof()` が認識する先頭の数値部分を使う（例: `12junk` は 12 として扱われる） |

小数、指数表記、空白などの詳細な数値字句は `atof()` の変換に従います。正数の明示値には追加の上限 clamp がありません。`uint64_t` で表せない大きさの値に対する変換結果は C++ の浮動小数点から整数への変換範囲外となるため、実装上の保証はありません。

## 有効になる条件

- `strata generate` が I/O prefetch を有効にして `FileExpertSource::set_io_prefetch(true, ...)` を呼ぶこと。Linux では `STRATA_IO_PREFETCH` が非空かつ `atoi()` 非0の場合、または file tier の Linux 既定条件で呼び出されます。環境変数が `0` 以外の先頭数値を持つかではなく、`atoi()` の結果が使われます。
- `set_io_prefetch()` の Linux 実装が有効で、source の base mapping と paths が存在し、unbuffered (`direct_`) 読み込みではないこと。これらを満たさない場合は先に戻り、予算値の読込みにも至りません。
- `STRATA_IO_PF_SCHED` の `atoi()` 結果が非0であること。unset、空文字、非数値、`0` は scheduler を無効にし、固定予算は採用判定に使いません。
- read-ahead 予測が行われること。`STRATA_IO_PF_AHEAD=0` や gate 閉鎖時など、予測経路が使われない場合、この上限で採用する予測 job はありません。

この変数自体は scheduler を有効化しません。`STRATA_IO_PF_SCHED` が無効なら `warm_scored()` は通常の `warm()` 経路に fallback します。

## 実行時の詳細

`set_io_prefetch()` は source の I/O prefetch 初期化時に環境変数を一度読みます。プロセス中に環境を書き換えても、格納済みの値は再読込されません。正の固定予算がある場合、各 decode window の予算は常にその値です。未設定または0相当の場合は、worker の読み取り実測帯域と decode window 時間から動的に計算します。両方の実測値が揃うまでは 256 MiB、揃った後は `worker 1本あたりの帯域 × worker 数 × window 時間 × STRATA_IO_PF_BUDGET_FRAC × feedback scale` で求め、最低16 MiBに clamp します。関連変数 `STRATA_IO_PF_BUDGET_FRAC` の既定値は0.5です。

scheduler 有効時、`warm_scored()` は候補の confidence を queue pressure に応じた閾値と比較した後、現在の window で既に採用した byte 数に blob のサイズを加えると予算を超える候補を拒否します。したがってこの設定は I/O bytes の厳密な実読込上限というより、予測 job を先に採用する際の window 単位の上限です。需要 read は別経路で行われます。decode window の境界では worker の読み取り帯域などを使って自動予算用の統計を更新します。

ログでは `STRATA_IO_PF_SCHED=1` の有効時に scheduler と予算機能が案内されます。I/O 統計出力には `budget ... MB/window` が含まれますが、表示値は `io_budget_now()` の戻り値です。Strata の `docs/DETAILS.md` にこの固定予算値の性能測定記載は見つかりませんでした。

## 根拠

- `src/core/expert_source.cpp:1045-1053`: 固定・自動予算の選択、初期値、計算式と自動時の下限。
- `src/core/expert_source.cpp:1081-1111`: scheduler が有効であること、予算取得、候補の予算超過拒否。
- `src/core/expert_source.cpp:1114-1161`: Linux 条件、環境変数の読み取り・変換と初期化タイミング。
- `src/core/expert_source.cpp:1248-1257`: worker の read-ahead 帯域実測。
- `src/core/expert_source.cpp:3276-3291`: decode window の更新箇所。
- `src/program/generate.cpp:5655-5670,5685-5687`: generate 経路の I/O prefetch 起動条件と scheduler ログ。
- `src/program/generate.cpp:15430-15438`: window 予算を含む I/O 統計ログ。
