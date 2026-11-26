# `STRATA_IO_PF_BUDGET_FRAC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_IO_PF_SCHED` によるスケジュール読み込みが有効なとき、予測した expert を1 decode window 内で先読みするバイト予算の比率を指定する。実測した I/O worker の読み取り率・worker 数・window 時間から求める予算にこの値と適応係数を掛ける。未設定時は `0.5`。`STRATA_IO_PF_BUDGET_MB` に正の固定値があると、その固定予算が優先され、この比率は計算に使われない。読み取りと計算は `FileExpertSource` にあり、scheduler が候補を予算内に採用する（`engine/include/strata/core/expert_source.hpp:1233-1248`、`engine/src/core/expert_source.cpp:1192-1200,1228-1258`）。

この変数は予測読み込み量の制限に作用する。expert の選択や生成結果を変える分岐はこの変数の参照経路にはなく、変化するのは scheduler が予測読み込みとして採用できる候補数・バイト量である（`engine/src/core/expert_source.cpp:1228-1258`）。

## 値と判定

Linux の `set_io_prefetch(true, ...)` 内で、変数が設定されている場合に `std::atof` で変換し、`std::clamp(..., 0.01, 4.0)` で範囲を制限する。文字列全体の妥当性検査や変換エラーの報告はない。`atof` は数値として読める先頭部分を変換するため、たとえば `2tail` は `2`、`true` や空文字・数値で始まらない文字列は `0` となり、下限の `0.01` に制限される。先頭空白は変換時に許容され、数値の後ろは検査されない。負値と `0` は `0.01`、`0.01` 以下は `0.01`、`4` 以上は `4` になる。大文字小文字の判定は行わない（`engine/src/core/expert_source.cpp:1292-1298`）。

| 条件 | unset | 有効になる値（例） | 無効な文字列・境界例 |
|---|---|---|---|
| Linux で I/O prefetch を開始 | `0.5` | `0.5`、`2tail` → `2`、`0` / 負値 → `0.01` | 空文字、`true`、`abc` → `0.01`。`0.01` 未満は `0.01`、`4` 超は `4` |
| Linux 以外、または I/O prefetch を開始しない経路 | 読み取りなし | 該当なし | 該当なし |

`nan` など非有限値について明示的な拒否・診断はありません。通常の数値入力以外についてはコード上の変換結果だけが使われます（`engine/src/core/expert_source.cpp:1297`）。

## 有効になる条件

- Linux であり、`FileExpertSource::set_io_prefetch(true, ...)` が実行されること。Linux 以外では関数本体がコンパイル時分岐で no-op となり、この名前も読み取らない（`engine/src/core/expert_source.cpp:1261-1266,1310-1312`）。
- I/O prefetch 自体が有効であること。`STRATA_IO_PREFETCH` が明示的に非ゼロなら有効化を要求できる。未設定または空文字なら `linux_io_defaults()` に従い、GGUF をその場で読む場合、または `experts.bin` で page cache の空きが expert 容量の55%以上の場合に既定で有効となる。`STRATA_IO_PREFETCH=0` など非ゼロでない明示値では既定有効化されない（`engine/src/program/generate.cpp:8688-8703`、`engine/include/strata/core/expert_source.hpp:1081-1094`）。
- 予算比率を実際に予測読み込みの採否に使うには、さらに `STRATA_IO_PF_SCHED` が `atoi` で非ゼロになる必要がある。unset・空文字・数値として先頭が `0` の値では scheduler は off であり、この比率は設定されても使われない（`engine/src/core/expert_source.cpp:1292-1298`）。
- `STRATA_IO_PF_BUDGET_MB` が正の固定値へ変換される場合は固定バイト予算を返すため、比率は予算計算に使われない。未設定時の固定予算は `0`（自動計算）である（`engine/src/core/expert_source.cpp:1296-1298,1195-1200`）。
- `FileExpertSource` に mapped file tier の backing file があり、unbuffered/direct 読み込みでなく、ファイル descriptor を開けること。条件を満たさない場合 `set_io_prefetch()` は有効化せず戻る（`engine/src/core/expert_source.cpp:1261-1277`）。
- scheduler の実行候補は router lookahead から渡され、`warm_scored()` の経路で採否判定される。`STRATA_IO_PF_AHEAD=0`、gate が閉じている、直接読み込み経路などでは通常の `warm()` にフォールバックし、scheduler の予算採否を通らない（`engine/src/core/expert_source.cpp:1228-1230,1284,1299-1300`、`engine/src/program/generate.cpp:10302-10333`）。

## 実行時の詳細

通常の `generate` 初期化時に、Linux I/O prefetch を有効にすると `set_io_prefetch(true, ...)` が呼ばれ、そこでこの値を読み込んで `io_budget_frac_` に保持する（`engine/src/program/generate.cpp:8693-8703`、`engine/src/core/expert_source.cpp:1261-1304`）。サーバー実行では GPU cache の全 expert 常駐により既定の I/O prefetch を一時停止し、常駐状態が崩れたとき再度 `set_io_prefetch(true, ...)` を呼ぶ経路があるため、その再有効化時に環境値も読み直される。プロセス内で環境値を変更した場合に既存インスタンスが自動更新される仕組みはない（`engine/src/program/generate.cpp:10275-10285,10341-10369`）。

自動予算は worker の実測読み取り率 `io_bw_`、worker 数、decode window 時間 `io_win_us_`、この比率、フィードバック係数 `io_scale_` の積。両方の実測値が揃うまでは `256 MiB`、計算後の自動予算は最低 `16 MiB`。window ごとの使用実績に応じて `io_scale_` は縮小・回復する。固定 MB 予算が正なら自動計算を使わない（`engine/src/core/expert_source.cpp:1192-1200,1202-1223`）。

予測候補は信頼度と現在の queue 圧力で判定され、候補のバイト数が window 予算を超えると採用されない。採用された job は deadline と信頼度で worker が処理する（`engine/src/core/expert_source.cpp:1228-1258,1355-1389`）。

## ログと測定値

`STRATA_IO_PREFETCH` と `STRATA_IO_PF_SCHED` が実際に有効なとき、起動時に次の scheduler 有効ログが stderr に出る。比率の数値そのものはログに出ない（`engine/src/program/generate.cpp:8719-8721`）。

```text
strata generate: io prefetch scheduling ON (STRATA_IO_PF_SCHED=1): a deadline per read, confidence admission (STRATA_IO_PF_MINCONF), a per-window byte budget (STRATA_IO_PF_BUDGET_MB / _FRAC)
```

リクエスト単位の file-tier I/O 統計が有効な場合は stderr の `strata serve: file tier I/O this request:` 行に `budget ... MB/window` として実際の byte budget が表示される。これは計算後の予算であり、比率の入力値ではない（`engine/src/program/generate.cpp:23835-23873`）。不正値を知らせる個別の警告・エラーは見つからなかった。

## 根拠

- 候補名の全参照: `terminal/data/settings-register.json:17917` は設定レジストリの名前エントリ、`engine/include/strata/core/expert_source.hpp:1238` と `engine/src/core/expert_source.cpp:1193` はコメント、実際に環境から読むのは `engine/src/core/expert_source.cpp:1297` の `set_io_prefetch()` 内 `std::getenv` 1 箇所。
- 値の既定値・変換・範囲制限・固定予算との優先: `engine/include/strata/core/expert_source.hpp:1235-1238`、`engine/src/core/expert_source.cpp:1195-1200,1292-1298`。
- Linux の有効化条件、ログ、server の停止・再開: `engine/src/program/generate.cpp:8688-8724,10275-10285,10341-10369`、`engine/include/strata/core/expert_source.hpp:1081-1094`。
- 予測候補の予算判定・scheduler job: `engine/src/core/expert_source.cpp:1228-1258,1355-1389`。
- 測定予算のログ: `engine/src/program/generate.cpp:23835-23873`。
