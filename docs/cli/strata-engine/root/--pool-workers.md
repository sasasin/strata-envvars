# `strata`（推論エンジン）`--pool-workers`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。調査時の Strata checkout は `main` が `origin/main` と一致し、`git status --short --branch` に未コミット変更はなかった。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンのトップレベル。`root/` scope） |
| オプション | `--pool-workers` |
| 別名 | なし |
| 値 | `N`。整数として `std::atoi` で読み取る。負数は拒否され、`0` は自動選択。正数に CLI 側の上限はない |

## 役割

CPU expert pool の worker 数を指定する。指定した正数は CPU の自動推奨値より大きくてもそのまま使われるため、CPU expert の処理に参加する thread 数を明示的に調整できる。worker は論理プロセッサへの pinning 対象となり、結果の計算方法や出力形式を切り替えるオプションではない（`engine/src/program/generate.cpp:856,9002-9004`、`engine/src/kernels/cpu/pool.cpp:991-1002`）。

## 使い方

```sh
# worker 数を 8 に指定して serve モードを起動する例
./engine/strata --serve --pack ./model.pack --pool-workers 8

# 0 を指定し、自動選択を明示する例
./engine/strata --serve --pack ./model.pack --pool-workers 0
```

## 値と既定値

- 省略時の内部値は `0`。明示的な `0` も同じ自動選択経路に入る（`engine/src/program/generate.cpp:856,3936`）。
- `N` は `std::atoi` で変換される。厳密な整数形式チェックはなく、数字に変換できない値は `0` になり自動選択として扱われる。指定値がない場合は stderr に `--pool-workers needs a value` を出して終了コード `2` で終了する（`engine/src/program/generate.cpp:3844-3846,3936`）。
- 負数は後段の共通 resource parameter validation で拒否され、stderr に `strata generate: invalid sampling or resource parameter` を出して終了コード `2` となる（`engine/src/program/generate.cpp:5267-5274`）。
- 同じオプションを複数回指定すると parser の反復処理で値が上書きされ、最後の値が残る（`engine/src/program/generate.cpp:3842-3847,3936`）。
- 正数には parser・validation 上の上限がない。CPU の推奨値を超えた場合にも自動で縮小せず、指定数で pool worker を作る（`engine/src/kernels/cpu/pool.cpp:865-871,980-987,991-1003`）。

## 実行時の動作

parser は値を `Options::pool_workers` に格納し、推論開始時に `ExpertPool` へ渡す。`N > 0` なら worker 数を `N` とし、`N == 0` なら検出した CPU topology と実行条件から選ぶ（`engine/src/program/generate.cpp:3936,9001-9004`、`engine/src/kernels/cpu/pool.cpp:865-880`）。

自動選択は通常、host thread が使う core を除いた物理 core 数を基準にする。CPU が 16 core 以上なら追加で 1 core を空け、hybrid CPU、container CPU quota、複数 socket、NUMA split の条件で計算が変わり、上限は 32 worker。OS が core 配置を返さない場合は論理 processor 数から推定する（`engine/include/strata/kernels/cpu/pool_plan.hpp:76-122`）。`--pool-affinity auto` または `p-cores` の hybrid CPU では、0 の自動選択に P-core 数から host 用の 1 を引いた数を使う。正数を指定した場合は affinity による worker 数の選択より優先される（`engine/src/kernels/cpu/pool.cpp:865-878`）。

`--pool-cores` と併用した場合、正の `--pool-workers N` は指定数を維持し、worker はリストの先頭から順に割り当てられる。リストの有効 CPU 数より worker 数が多い分は pinning されず OS に任される。`--pool-workers 0` なら有効な `--pool-cores` リストの長さが worker 数になる（`engine/src/kernels/cpu/pool.cpp:823-839,865-871,1006-1013`）。

`--pool-measure` が有効な場合は、測定用 pool にもこの worker 数を渡して affinity を選ぶ（`engine/src/program/generate.cpp:9001-9004`）。ネイティブ expert arena の起動時には、正数指定を最大 6 thread までの arena thread 数にも反映する（`engine/src/program/generate.cpp:8870-8872`）。

## 適用条件と副作用

- エンジン起動時に CPU pool worker thread を指定数だけ生成し、通常は各 worker を検出済みの論理 processor に pin する。指定数が配置先候補より多い場合は余剰 worker が pin されない（`engine/src/kernels/cpu/pool.cpp:991-1003,1006-1013`）。
- 指定数が CPU topology・実行可能 thread 数・container quota などから算出した推奨値より大きい場合、Strata は指定を維持したまま `strata cpu pool: warning: ... Recommended: --pool-workers ...` を stderr に出す。警告は推奨値を超えた条件に応じた説明を含み、同じプロセス内では一度だけ出る（`engine/src/kernels/cpu/pool.cpp:980-987`、警告条件と文面は `engine/include/strata/kernels/cpu/pool_plan.hpp:125-145`）。
- `--no-pool` を併用しても `ExpertPool` 自体は生成され、起動時に worker 数が表示される。ただし expert-pool callback を無効にし、表示には `(UNUSED: --no-pool)` が付く。したがってこの組み合わせでは worker thread を生成しても通常の expert pool 処理には使わない（`engine/src/program/generate.cpp:9003-9004,10479-10487`）。
- worker 数の値は実行中に再設定する経路を確認できず、起動時の pool 構築で反映される。ここで確認したソース範囲では、ファイル出力やネットワーク動作への直接の副作用は見つからなかった。

## 出力とエラー

起動時に stderr へ pool の task 数・参加 thread 数を出す。自動選択時は worker 数、検出した物理 core 数と論理 processor 数、および選択を制限した条件も出力する。worker の配置情報も別の起動ログに出る（`engine/src/program/generate.cpp:9005-9011,9022-9026`）。正数が推奨数を超える場合の警告は上記のとおりで、指定値は変えずに続行する。

## 根拠

- `engine/src/program/generate.cpp:856` — 既定値 `0` と正数指定の意図。
- `engine/src/program/generate.cpp:1443-1446` — 同一 revision の usage 表示（補助資料）。
- `engine/src/program/generate.cpp:3842-3847,3936` — parser の値取得、欠落時の終了、および `atoi` 変換。
- `engine/src/program/generate.cpp:5267-5274` — 負数を含む共通 validation と終了コード `2`。
- `engine/src/program/generate.cpp:8870-8872,9001-9004` — arena thread 数への反映と `ExpertPool` への引き渡し。
- `engine/src/kernels/cpu/pool.cpp:865-880,980-1003` — 明示数・自動数の選択、過大指定の警告、worker thread 生成。
- `engine/include/strata/kernels/cpu/pool_plan.hpp:76-122,125-145` — 自動 worker 数計画と警告条件。
- `engine/src/kernels/cpu/pool.cpp:823-839,1006-1013` — `--pool-cores` 相当の配置候補と、候補を超える worker の pinning。
- `engine/src/program/generate.cpp:10479-10487` — `--no-pool` 時に pool を unused とする経路。

この文書は `strata-engine/root/` scope の parser を対象とする。`qwen36/` scope の別 parser にある同名オプションは、この調査には含めていない。
