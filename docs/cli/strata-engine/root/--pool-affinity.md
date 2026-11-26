# `strata`（エンジン引数）`--pool-affinity`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。索引上の root scope） |
| オプション | `--pool-affinity` |
| 別名 | なし。値 `pcores` は `p-cores` と同じ設定として受理される |
| 値 | `all`、`auto`、`p-cores`、`pcores`、`measure` のいずれか |

## 役割

CPU expert pool の worker をどの CPU コア群に割り当てるかを指定する。`all` は従来の全コア配置、`auto` はハイブリッド CPU で P-core とその SMT sibling を優先して E-core を追加候補にし、`p-cores` は P-core とその SMT sibling に限定する。`measure` は起動時にモデルの native experts を使って `all` と `p-cores` を測り、選んだ配置で pool を作る。ここで変わるのは worker thread の配置であり、計算結果ではない（`engine/include/strata/kernels/cpu/pool.hpp:72-78`、`engine/src/program/generate.cpp:2995-3009`）。

## 使い方

```sh
# 従来の全コア配置
strata --pack ./model.gguf --pool-affinity all

# ハイブリッド CPU で P-core を優先し、必要なら E-core も候補にする
strata --pack ./model.gguf --pool-affinity auto

# P-core とその SMT sibling に worker を限定する
strata --pack ./model.gguf --pool-affinity p-cores

# 対応条件を満たす場合に起動時測定で配置を選ぶ
strata --pack ./model.gguf --pool-affinity measure
```

## 値と既定値

- 値を省略できない。未指定時は `all`（`PoolAffinity::All`）。
- 大文字小文字を区別し、受理値は `auto`、`p-cores`、`pcores`、`all`、`measure`。`pcores` は parser 上の互換表記。
- 引数がない場合は `--pool-affinity needs a value` を stderr に出して終了コード 2。未知の値では `strata generate: unknown --pool-affinity value '…' (expected auto, p-cores, all or measure)` を stderr に出して終了コード 2（`engine/src/program/generate.cpp:3842-3847,3965-3974`）。
- 複数回指定したとき、通常値は後の値が `pool_affinity` を上書きする。ただし `measure` は独立した `pool_measure` フラグを立てるだけで解除されない。そのため、同じ実行引数内に `measure` が一度でもあれば、後続に `all` 等を指定していても起動時測定が行われ、測定結果が最終配置になる（同: `3965-3974,9001-9004`）。

## 実行時の動作

parser は `auto`、`p-cores` / `pcores`、`all` をそれぞれ pool の affinity enum に設定し、`measure` は測定フラグを設定する（`engine/src/program/generate.cpp:3965-3974`）。未指定時の enum 初期値は `All`（同: `858-862`）。通常起動ではこの値を CPU topology 検出と `ExpertPool` に渡す（同: `9001-9004`）。

`auto` と `p-cores` はハイブリッド CPU の topology に応じて worker CPU のリストを変える。`auto` は P-core の primary logical processor、P-core の SMT sibling、E-core の順に並べ、`p-cores` は E-core を候補に加えない。`all` または非ハイブリッド CPU では通常の全コア経路を使う（`engine/src/kernels/cpu/pool.cpp:391-442`）。ハイブリッド CPU で `auto` / `p-cores` を指定し worker 数を別途指定しない場合、pool は P-core 数から host 用の 1 を引いた数を worker 数にする（同: `865-881`）。明示 worker 数や CPU の利用制限なども実際の pool 計画に関わる。

`measure` はモデルの読み込み・expert source の準備後、通常の pool を作る直前に実行される。helper はハイブリッド CPU であること、native pack であること、および各 layer の expert blob が source から取得できることを確認し、2 experts × 4 tokens / layer の native expert 処理を `all` と `p-cores` で交互に3ブロック測定する。各ブロックの中央値を比較し、`p-cores` が `all` より10%を超えて遅くなければ `p-cores`、それ以外は `all` を採用する（`engine/src/program/generate.cpp:3010-3035,3047-3089`）。その後、選択結果で通常の pool を生成する（同: `9001-9004`）。測定中に専用 pool と scratch data を作り、開始時に追加の CPU 処理を行う。測定結果は起動ごとに読み直され、実行中に再測定されない。

## 適用条件と副作用

- `auto` / `p-cores` のハイブリッド判定と CPU 配置は、OS から取得できる CPU topology に基づく。ソースには Windows と Linux の topology 検出経路があるが、CPU や OS が topology をどう報告するかによる差をこの調査だけでは一律に確定できない（`engine/src/kernels/cpu/pool.cpp:312-442`）。
- `measure` がハイブリッド CPU 以外で指定された場合、stderr に「this CPU is not a hybrid one; the layout stays all」と出して `all` を返す。native pack でない、expert source がない、または expert blob を取得できない場合も stderr に条件を示し、`all` に戻す（`engine/src/program/generate.cpp:3014-3035`）。これらは拒否ではなく fallback。
- 測定時は CPU expert pool を起動し、通常の pool 作成時も worker thread を pin する。OS の affinity 設定に失敗した worker は stderr に警告し、以前の affinity を保持する（`engine/src/program/generate.cpp:3048-3075,9001-9004`、`engine/src/kernels/cpu/pool.cpp:624-634`）。
- `--pool-workers` などの worker 数指定は測定用 pool と最終 pool の両方に渡される。実際の配置は明示的な worker CPU 指定や process の CPU 制限など、他の配置条件にも影響される（`engine/src/program/generate.cpp:3010-3011,9001-9004`、`engine/src/kernels/cpu/pool.cpp:823-881`）。
- `--no-pool` を併用しても、この地点では pool を作り、その後 expert-pool callback を無効にする。したがって `measure` の追加測定と pool 初期化は行われる一方、推論処理では pool が unused になる（`engine/src/program/generate.cpp:9001-9008,10479-10487`）。

## 出力とエラー

- 通常の hybrid CPU で `auto` / `p-cores` が `all` 以外の配置になった場合、選択 affinity と worker 数を stderr に表示する（`engine/src/program/generate.cpp:9016-9021`）。pool の CPU 配置も起動時に stderr へ表示される（同: `9022-9036`）。
- `measure` が有効で測定可能な場合、測定値・worker 数・選択した配置を stderr に表示する（同: `3086-3089`）。条件を満たさない場合は上記 fallback のメッセージを出す。
- 未指定値・不正値は parser で終了コード 2。CPU pinning の失敗は警告経路であり、pool.cpp の該当箇所では失敗時に以前の配置を維持する（`engine/src/program/generate.cpp:3844-3846,3971-3974`、`engine/src/kernels/cpu/pool.cpp:624-634`）。

## 根拠

- `engine/src/program/generate.cpp:858-862` — affinity の既定値と `measure` 状態。
- `engine/src/program/generate.cpp:3965-3974` — parser の受理値、互換表記、不正値エラー。
- `engine/src/program/generate.cpp:2995-3009,3010-3089` — 測定条件、測定方法、判定、stderr 出力。
- `engine/src/program/generate.cpp:9001-9008,9016-9036,10479-10487` — 測定後の pool 生成、配置表示、`--no-pool` との関係。
- `engine/include/strata/kernels/cpu/pool.hpp:72-78` — affinity enum の意味。
- `engine/src/kernels/cpu/pool.cpp:312-442,624-634,803-881` — topology に応じた worker 配置、pin 失敗時の扱い、worker 数決定。

制約: Linux / Windows 以外の topology 検出挙動、個別機種の P/E-core 判定精度、測定の所要時間や推論性能への効果はこのソース調査では確定していない。ここでは性能改善を保証しない。
