# `STRATA_IO_PF_MINCONF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux の `FileExpertSource` におけるスケジュール済み I/O read-ahead で、ルーター予測の expert を先読みキューへ採用する confidence の基準値を指定する。未設定時は `0.5`。キューの使用量が予算に対して増えると、実際の採用閾値はこの値から `1.0` へ線形に上がる。値は通常の expert 選択やモデル出力を変えるものではなく、予測 expert の先読み採否だけに作用する（`engine/include/strata/core/expert_source.hpp:1233-1244`、`engine/src/core/expert_source.cpp:1225-1258`）。

設定値を読み取る箇所は `FileExpertSource::set_io_prefetch` のみ。`STRATA_IO_PF_SCHED` が有効なら予測ごとの confidence を使い、無効なら `warm_scored` は通常の `warm` にフォールバックする（`engine/src/core/expert_source.cpp:1228-1230, 1261-1304`）。

## 値と判定

`std::getenv` が null でないとき `std::atof` で文字列を数値変換し、`std::clamp(..., 0.0, 1.0)` で範囲に収める。文字列全体の妥当性検証はない。`atof` が数値として読めない先頭なら `0` となり、数値の後ろに文字が続いても数値部分が使われる。未設定だけが既定値 `0.5` を保つ。空文字は設定済みなので `atof("") == 0` 相当となり `0`。負値は `0`、1 より大きい値は `1` に clamp される（`engine/include/strata/core/expert_source.hpp:1236`、`engine/src/core/expert_source.cpp:1292-1298`）。

| 条件 | unset | 有効になる値（例） | 無効・境界の値（例） |
|---|---|---|---|
| Linux で `set_io_prefetch(true, ...)` が初期化を完了 | `0.5` | `0`、`0.25`、`0.5`、`1`。値域は `[0,1]` | 空文字、`abc`、`0anything` は変換値 `0`。`-1` は `0`、`2` は `1` に clamp。`0.5tail` は `0.5` として扱われる |
| 上記以外（非 Linux、prefetch を有効化しない、または初期化が途中で戻る） | 読み取りなし | 該当なし | 該当なし |

「無効・境界」は環境変数自体の拒否を意味しない。`atof` の変換値が採用され、範囲外だけ clamp される。大文字小文字や真偽値の比較はせず、`true` 等は数値として読めないため `0` になる（`engine/src/core/expert_source.cpp:1261-1298`）。

## 有効になる条件

- OS が Linux であること。`set_io_prefetch` の本体は `__linux__` 内にあり、それ以外の OS では引数を使わず何もしない（`engine/src/core/expert_source.cpp:1261-1312`）。
- I/O prefetch が要求され、file tier の `base_` とファイルが存在し、unbuffered 経路でないこと。条件を満たさなければ設定読み取りより前に戻る（`engine/src/core/expert_source.cpp:1261-1277`）。
- 先読みスケジューラーを使うには `STRATA_IO_PF_SCHED` が `atoi` で 0 以外になること。さらに本変数が変える採否は、`io_sched_`、`io_pf_`、`direct_` が空、`io_ahead_`、decode gate がすべて先読み経路を許す場合に限る。それ以外は通常の `warm` にフォールバックする（`engine/src/core/expert_source.cpp:1228-1230, 1292-1295`）。
- 予測 confidence を渡す routing-aware look-ahead が動く必要がある。予測器はルーター重みが BF16 の形式であることなどを検証し、開始できない場合は `routing-aware prefetch off (...)` を出す（`engine/src/program/generate.cpp:10302-10337`）。予測の confidence は、予測対象が次層から遠いほど半減し、token 内の rank が下がるほど小さく計算される（`engine/src/core/expert_source.cpp:3749-3759`）。
- `STRATA_IO_PF_MINCONF` 自体を無視・上書きする CLI 引数は確認できない。`STRATA_IO_PF_SCHED` が無効でも値の読み取りは行われるが、scheduler が採否に使わない。

## 実行時の詳細

`set_io_prefetch(true, ...)` の呼び出しで環境変数を読み、`io_minconf_` に保存する。プロセス起動時に固定で読むのではなく、I/O prefetch の初期化ごとに読む。通常は一度の初期化中に一度読み、実行中に環境を変更しても現在の `io_minconf_` は更新されない。`strata serve` が GPU cache 状態に応じて Linux の既定 prefetch を止め、後で再開する経路では `set_io_prefetch` を再度呼ぶため、その再初期化時には環境値を読み直す（`engine/src/core/expert_source.cpp:1261-1304`、`engine/src/program/generate.cpp:10275-10285, 10343-10368`）。

`warm_scored` は候補ごとに `pressure = min(1, io_q_bytes / max(1, budget))`、`bar = io_minconf + (1 - io_minconf) * pressure` を計算する。confidence が `bar` 未満なら候補を拒否し、そうでなければ当該 decode window の byte budget 超過も確認して採用する。したがって `0` はキューに空きがあると confidence の低い予測も通す一方、キュー圧力が上がるほど閾値は上がる。`1` は常に閾値 1 であり、confidence が 1 未満の予測を通さない。各 window の byte budget は別の予算制御であり、本変数がその上限を変えるわけではない（`engine/src/core/expert_source.cpp:1192-1200, 1228-1258`）。

予算超過で拒否された候補や期限に間に合わなかった job は別カウンターで扱われる。採用・拒否は先読み I/O だけに関係し、需要時の読み込み経路そのものを無効化する設定ではない（`engine/src/core/expert_source.cpp:1243-1258, 1355-1378`）。

## ログと測定値

スケジューラーが有効で prefetch が実際に有効なとき、stderr に次の行が出る。設定した `MINCONF` の数値そのものは表示しない。

```text
strata generate: io prefetch scheduling ON (STRATA_IO_PF_SCHED=1): a deadline per read, confidence admission (STRATA_IO_PF_MINCONF), a per-window byte budget (STRATA_IO_PF_BUDGET_MB / _FRAC)
```

I/O 統計の出力経路では、window 集計として `not admitted (confidence)` の件数を表示する。これは confidence 閾値未満で拒否した候補数であり、実際の閾値値は表示されない（`engine/src/program/generate.cpp:8719-8721, 23864-23872`）。この変数固有の性能測定値は `docs/DETAILS.md` に見当たらず、ここでは測定値を記載しない。

## 根拠

- `engine/include/strata/core/expert_source.hpp:1233-1253` — scheduler 状態、既定 confidence、採否用カウンター。
- `engine/src/core/expert_source.cpp:1225-1258` — confidence 閾値、キュー圧力、候補採用と予算判定。
- `engine/src/core/expert_source.cpp:1261-1312` — Linux 条件、環境変数の読み取り・変換・clamp、scheduler 初期化。
- `engine/src/core/expert_source.cpp:3749-3759, 3789` — 予測 confidence の生成と `warm_scored` 呼び出し。
- `engine/src/program/generate.cpp:10302-10337` — look-ahead の開始条件と起動失敗ログ。
- `engine/src/program/generate.cpp:8719-8721, 23864-23872` — 有効ログと統計の出力。
- `docs/DETAILS.md:302-317` — Linux file tier と io prefetch の関連説明。`STRATA_IO_PF_MINCONF` の個別値規則や測定値は記載されていない。
