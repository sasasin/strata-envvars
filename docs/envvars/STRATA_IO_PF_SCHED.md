# `STRATA_IO_PF_SCHED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux の file tier I/O prefetch で、router lookahead が予測した専門家の先読みをスケジュールする。ON の場合、予測の確信度による採否、decode layer までの期限、decode window あたりの推測読み込み byte 予算を使う。OFF の場合は従来の先読み queue に入れる。需要が発生した専門家の読み込みや router の選択自体を変える設定ではない。読み取りと scheduler は `FileExpertSource` にある（`engine/src/core/expert_source.cpp:1228-1258,1261-1304`）。

## 値と判定

`set_io_prefetch()` が Linux で有効化されたとき `std::getenv()` で読み、値全体ではなく `std::atoi(v) != 0` で判定する。未設定、空文字、数字で始まらない文字列、`0` や `0anything` は OFF。`1`、`-1`、`+1`、`1anything`、先頭空白の後に非ゼロ数字がある値は ON。`true` / `false` はどちらも OFF。先頭の符号と数字列の後ろは `atoi` の規則に従い、文字列の大文字小文字は判定に関係しない。明示的な範囲検査や clamp はない（`engine/src/core/expert_source.cpp:1292-1295`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux の buffered file tier で I/O prefetch が開始された場合 | OFF | `atoi` が 0 以外を返す値（例: `1`, `-1`, `1x`） | `atoi` が 0 を返す値（例: 空文字, `0`, `0x`, `true`） |
| 非 Linux、prefetch 無効、または buffered file tier でない場合 | scheduler の値を読まない／実行しない | なし | なし |

`atoi` の結果が `int` で表せない入力の結果は C/C++ の変換仕様上保証できないため、利用可能な値域として扱わない。

## 有効になる条件

- `STRATA_IO_PREFETCH` が明示的に非空かつ `atoi` が非ゼロであるか、Linux file tier の既定条件で prefetch が選ばれる必要がある。`STRATA_IO_PF_SCHED` 自体は I/O prefetch を開始しない（`engine/src/program/generate.cpp:8693-8704`）。
- `FileExpertSource::set_io_prefetch(true, ...)` が Linux で呼ばれ、file mapping の base と paths があり、`direct_` が空である必要がある。非 Linux ではこの関数の Linux 部分がコンパイルされず、unbuffered reader でも初期化を早期終了する（`engine/src/core/expert_source.cpp:1261-1267,1310-1312`）。
- 予測候補は `RouterLookahead` が動作して `warm_scored()` に届く必要がある。生成経路では `STRATA_LOOKAHEAD=0` が lookahead を止め、router weights が BF16 でない場合も開始しない（`engine/src/program/generate.cpp:10302-10320,10334-10338`）。
- `STRATA_IO_PF_AHEAD=0`、または decode gate が閉じている間は `warm_scored()` が通常の `warm()` に委譲し、deadline / confidence / scheduler budget による job 登録はしない。`STRATA_IO_PF_GATE=0` は gate を常時 open にする（`engine/src/core/expert_source.cpp:1228-1229,1284,1299-1300,3487-3495`）。
- `STRATA_IO_PF_MINCONF` は空 queue 時の基準確信度（既定 `0.5`、読み取り値を `[0,1]` に clamp）、`STRATA_IO_PF_BUDGET_MB` は固定予算（既定 `0` で自動）、`STRATA_IO_PF_BUDGET_FRAC` は自動予算の係数（既定 `0.5`、`[0.01,4]` に clamp）、`STRATA_IO_PF_TARGET` は使われた先読み byte の目標割合（既定 `0.5`、`[0,1]` に clamp。`0` は feedback 無効）を変える（`engine/src/core/expert_source.cpp:1295-1298,1192-1200,1211-1222`）。
- Linux 既定で有効になった prefetch は、全専門家が GPU cache に保持されると file tier idle policy によって止まることがある。明示的な `STRATA_IO_PREFETCH=1` はその停止対象ではない。cache の状態が変わって既定 prefetch を再開すると `set_io_prefetch()` が再度呼ばれる（`engine/src/program/generate.cpp:10251-10285,10341-10368`）。

## 実行時の詳細

値は `set_io_prefetch(true, ...)` ごとにメンバー `io_sched_` に読み込まれ、起動時だけの `static` cache ではない。設定を process 実行中に変えても有効中のメンバー値は自動更新されず、再度 prefetch を有効化する経路が通ればその時点の値を読み直す（`engine/src/core/expert_source.cpp:1261-1267,1292-1295`; 再有効化呼び出しは `engine/src/program/generate.cpp:10364-10367`）。

有効時、lookahead は GPU にない予測専門家について rank と先の layer 数から confidence を作り、各候補を `warm_scored()` に渡す（`engine/src/core/expert_source.cpp:3700-3705,3749-3759,3789`）。scheduler は queue 圧力に応じて必要 confidence を上げ、窓予算を超える候補を拒否し、通過した job に layer deadline を持たせる。worker は demand queue を先に処理し、decode が到達済みの job を遅延として捨てた後、最も早い deadline、同じ期限なら confidence の高い順に処理する（`engine/src/core/expert_source.cpp:1225-1258,1355-1389`）。予算は固定 byte 数があればそれを使い、そうでなければ worker の読み込み速度・window 時間・係数に基づきます。初期値は測定値が揃うまで 256 MiB、自動予算には 16 MiB の下限があります（`engine/src/core/expert_source.cpp:1192-1200`）。window ごとに先読みの利用率を EWMA で追い、target 未満なら予算係数を縮小し、以上なら回復します（`engine/src/core/expert_source.cpp:1202-1222`）。

`docs/DETAILS.md` の「Linux file tier」は I/O prefetch と decode gate の基本条件・関連設定を記載していますが、`STRATA_IO_PF_SCHED` 自体の記述はありません。上記 scheduler の効果と値判定は現行ソースの記述に基づきます（`docs/DETAILS.md:302-317`）。

## ログと測定値

prefetch が有効で scheduler が ON のとき、生成経路は stderr に次を出します（`engine/src/program/generate.cpp:8715-8721`）。scheduler OFF 時にはこの scheduler ON 行は出ません。

```text
strata generate: io prefetch scheduling ON (STRATA_IO_PF_SCHED=1): a deadline per read, confidence admission (STRATA_IO_PF_MINCONF), a per-window byte budget (STRATA_IO_PF_BUDGET_MB / _FRAC)
```

request ごとの file-tier I/O 診断が有効な場合、stderr の行に `read ahead ... MB, ... MB of it used; ... late, ... not admitted (confidence), ... (budget ... MB/window)` が含まれます。診断対象は scheduler の late / confidence rejection / budget rejection と予算で、prefetch が動作し `proc_io_sample()` が有効な場合に出力されます（`engine/src/program/generate.cpp:23837-23873`）。この環境変数についての独立した性能測定値は `docs/DETAILS.md` にありません。

## 根拠

- 値の取得と関連設定: `engine/src/core/expert_source.cpp:1261-1304`
- 候補の confidence / deadline 付与と scheduler の採否: `engine/src/core/expert_source.cpp:1225-1258,1355-1389,3700-3790`
- 有効化、既定条件、lookahead 条件、GPU cache idle policy: `engine/src/program/generate.cpp:8693-8724,10251-10338,10341-10377`
- 診断出力: `engine/src/program/generate.cpp:8715-8721,23837-23873`
- 関連設計説明: `docs/DETAILS.md:302-317`
