# `STRATA_IO_PF_TARGET`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux の `FileExpertSource` が行う scheduled I/O prefetch の適応予算で、読み出し先の page cache から後で実際に使われた read-ahead bytes の比率をどの値以上に保つかを指定します。既定値は `0.5` です。比率が目標を下回ると、次の decode window の予測読み込み予算を縮め、目標以上なら回復させます。この値は予測 read-ahead の予算に作用し、需要読み込みやモデルの routing 値を変更するものではありません。値の読み込みは `FileExpertSource::set_io_prefetch`、フィードバックは `FileExpertSource::io_window_tick` です（`engine/src/core/expert_source.cpp:1202-1222,1261-1267,1292-1304`）。

## 値と判定

環境変数が未設定ならメンバー初期値 `0.5` を使います。設定されていれば `std::atof` で数値変換し、`std::clamp(..., 0.0, 1.0)` を適用します。文字列全体の数値妥当性は検査せず、`atof` が認識する先頭の数値部分が使われます。したがって空文字や数値で始まらない文字列は `0` になり、`0anything` も `0` です。先頭空白は `atof` の変換規則に従います（`engine/include/strata/core/expert_source.hpp:1248`; `engine/src/core/expert_source.cpp:1292-1299`）。

| 条件 | 未設定 | 設定時に有効になる値 | 設定時に無効・境界となる値 |
|---|---|---|---|
| `FileExpertSource::set_io_prefetch(true, ...)` が Linux で実行され、mapped file tier を使用 | `0.5` | 数値として変換された値を `[0,1]` に clamp。例: `0.25`, `1`, `0.7suffix` → `0.25`, `1`, `0.7` | 空文字、`true`、`garbage`、`0anything` → `0`; 負値は `0`、`1` 超は `1` に clamp。`atof` が認識する `nan` は比較で clamp されず、後続の `io_target_ > 0.0` を満たさないためフィードバックを行わない |
| Linux 以外、prefetch を開始しない場合、または mapped file tier でない場合 | 初期値は `0.5` のまま | この呼び出しでは読み取られない | この環境変数による実行時の効果はない |

`0` は feedback を止める指定です。非ゼロ値でも feedback 自体が動くとは限らず、次節の条件が必要です（`engine/src/core/expert_source.cpp:1218-1222,1261-1267,1298-1304`）。

## 有効になる条件

- `FileExpertSource::set_io_prefetch(true, ...)` が実際に Linux で有効化される必要があります。`on` が false、`base_` が null、`paths_` が空、または unbuffered (`direct_` が空でない) なら早期 return します。非 Linux の実装は引数を使わず、環境変数を読みません（`engine/src/core/expert_source.cpp:1261-1267,1310-1312`）。
- 通常の `strata generate` 経路では `STRATA_IO_PREFETCH` が未設定または空で Linux file-tier default が成立するか、設定値の `atoi` が非ゼロであることが prefetch 開始条件です。明示的な `STRATA_IO_PREFETCH=0` は default を上書きして無効にします。default は Linux の GGUF mapped file tier では有効、`experts.bin` では page-cache room ratio が `0.55` 以上の場合に有効です。unbuffered read や利用可能な mapped file tier がない経路では setter が有効化できません（`engine/src/program/generate.cpp:8688-8704`; `engine/include/strata/core/expert_source.hpp:1081-1094`; `engine/src/core/expert_source.cpp:1264-1277`）。
- 適応処理には `STRATA_IO_PF_SCHED` の `atoi` 結果が非ゼロであることが必要です。未設定・空文字・数値で始まらない値・`0` は scheduler を無効にし、`STRATA_IO_PF_TARGET` が読み込まれていても使用しません（`engine/src/core/expert_source.cpp:1292-1298,3818`; `engine/include/strata/core/expert_source.hpp:998-999`）。
- scheduler が有効でも、`io_window_tick` は新しい decode window の開始時（layer が前回より小さくなった時）に呼ばれ、その window で予測 read-ahead bytes `dpf` が増えていなければ比率を計算しません（`engine/src/core/expert_source.cpp:1202-1222,3804-3819`）。
- `STRATA_IO_PF_BUDGET_MB` が正の値に変換されて固定予算が設定されると、その固定予算が優先され、feedback の `io_scale_` は `io_budget_now()` の予算計算に使われません。自動予算では、計測済み read rate と window 時間、`STRATA_IO_PF_BUDGET_FRAC`、`io_scale_` を使います（`engine/src/core/expert_source.cpp:1192-1200,1295-1298`）。
- scheduler の候補投入にはさらに read-ahead が有効 (`STRATA_IO_PF_AHEAD` が未設定または `atoi` 非ゼロ)、decode gate が開いていることなどが必要です。これらを満たさない `warm_scored` 呼び出しは通常の `warm` に fallback します（`engine/src/core/expert_source.cpp:1228-1230,1284,1299-1303`）。

## 実行時の詳細

値は `set_io_prefetch` の有効化時に `getenv` で読み、`FileExpertSource` の `io_target_` メンバーに保存します。`io_window_tick` は、read-ahead 総 bytes と後で使われた bytes の前回値との差から `u = min(1, du/dpf)` を計算し、window 間の EWMA（初回は `u`、以降は `0.8 * 前回 + 0.2 * u`）を更新します。EWMA が target 未満なら `io_scale_` を `0.7` 倍（下限 `0.05`）、target 以上なら `1.1` 倍（上限 `1.0`）にします。`target=0` ではこの更新条件を満たさず、初期 scale `1.0` のままです（`engine/src/core/expert_source.cpp:1202-1222`; `engine/include/strata/core/expert_source.hpp:1245-1249`）。

自動予算の場合、scale は計測された worker read rate × worker 数 × window 時間 × `STRATA_IO_PF_BUDGET_FRAC` に乗じられ、予算は最低 16 MiB です。rate または window 時間が未計測なら暫定 256 MiB です。read-ahead の予測は layer/expert ごとの confidence と残り予算で admission されます。worker は decode が到達した deadline の job を破棄するため、target は読み込みの完了を保証しません（`engine/src/core/expert_source.cpp:1192-1200,1228-1258,1355-1389`）。

値はリクエストごとではなく prefetch の有効化時に読みます。server 内で GPU cache の全 expert residency により Linux default prefetch を一時停止し、その後再開する経路では `set_io_prefetch` が再び呼ばれます（`engine/src/program/generate.cpp:10275-10285,10341-10369`）。各呼び出し時点の環境値が設定されていれば読み直します。未設定ならメンバーを初期化値に戻す代入はありません。通常のプロセス環境を実行中に変更する仕組みや、値を子プロセスへ転送する処理はこの読み取り経路にはありません。

## ログと測定値

対象値を表示する専用ログ、警告、無効値エラーはありません。prefetch が有効で scheduler も有効な場合、`strata generate: io prefetch scheduling ON (STRATA_IO_PF_SCHED=1): a deadline per read, confidence admission (STRATA_IO_PF_MINCONF), a per-window byte budget (STRATA_IO_PF_BUDGET_MB / _FRAC)` が stderr に出ます。このログは target の実値や feedback の結果を出しません（`engine/src/program/generate.cpp:8715-8724`）。

対象変数固有の性能測定値は確認できません。`docs/DETAILS.md` の Linux file-tier 節は prefetch、gate と関連値を記載していますが、この target の値や効果測定は記載していません（`docs/DETAILS.md:302-318`）。

## 根拠

- `engine/include/strata/core/expert_source.hpp:1245-1249` — feedback 状態と target の初期値。
- `engine/src/core/expert_source.cpp:1192-1222` — 自動予算、window feedback と scale 更新。
- `engine/src/core/expert_source.cpp:1261-1312` — Linux file-tier の有効条件、全 env 値の読み込みと非 Linux 分岐。
- `engine/src/core/expert_source.cpp:1228-1258,1355-1389` — confidence/予算による候補 admission と worker deadline。
- `engine/src/core/expert_source.cpp:3804-3819` — decode window 境界での feedback 呼び出し。
- `engine/src/program/generate.cpp:8688-8724,10275-10285,10341-10376` — prefetch の起動条件、観測ログ、server 内の停止・再開。
- `docs/DETAILS.md:302-318` — 関連する Linux file-tier の説明との照合。
