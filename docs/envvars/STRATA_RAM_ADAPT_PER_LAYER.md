# `STRATA_RAM_ADAPT_PER_LAYER`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata serve` の resident RAM 適応機能 `STRATA_RAM_ADAPT2` が、各モデル層についてRAM上のexpertを入れ替える候補数を制限します。RAMにある未使用expertを追い出す候補は最大 `N` 個、RAMへ昇格させる候補は最大 `2N` 個まで、その層から選びます。実際の入れ替え数を直接指定する値ではありません。

## 値と判定

| 状態 | 値 |
|---|---|
| 未設定 | 既定値 `2` |
| 設定あり | `std::atoi` で整数変換した結果と `1` の大きい方 |

文字列全体の妥当性は検査しません。`atoi` のため、先頭の空白と符号は整数変換で扱われ、数字列の後ろに文字があっても数字のprefixが変換されます。空文字や数字で始まらない文字列は `0` になり、最終値は `1` です。`0` および負数も `1` に切り上げられます。正の値に上限 clamp はありません。整数型に収まらない値の結果はコードで別途定義されていません。

## 有効になる条件

この値が候補選択に使われるのは、次の条件を満たす `strata serve` のwindow境界処理です。

- `STRATA_RAM_ADAPT` が `atoi` で正数になる。
- `STRATA_RAM_ADAPT2` が設定され、その `atoi` 結果が0以外になる。
- 初回windowではなく、適応usageが空でなく、前回の適応swapが残っていない。
- 非同期適応jobがないか idle で、resident RAM complement が準備済み。
- 単一GPUで、peer device / remote expert optを使わず、`--batch` が0。

したがってこの変数単独では機能を有効化しません。`STRATA_RAM_ADAPT2` が無効なら `per_layer` は読み取られますが候補選択へ到達しません。また、旧来の `STRATA_RAM_ADAPT` 経路（`STRATA_RAM_ADAPT2` 無効時）はこの上限を使わず、層ごと最大1組を選びます。

## 実行時の詳細

値は`serve`のRAM適応設定を初期化するときに一度読み取られます。環境変数を後から変更しても、そのserve実行中の設定値は変わりません。読み取り自体にログ出力はありません。

各適応window境界でRAM適応2が動くと、GPUに常駐していないexpertについてusageとprompt由来seedを合算し、候補を作ります。`STRATA_RAM_ADAPT_SKIP_TOP` が正なら、まずusageが上位の昇格候補を指定数だけ除外します。その後この変数の値を `N` として、昇格候補は最大 `2N`、RAMから追い出す候補は最大 `N` に絞り、usage/推定読み出しコストに基づいて組み合わせます。候補が不適格、既にI/O queueにある、または利益条件を満たさない場合は入れ替えが少なくなるか発生しません。

層ごとに作った入れ替え候補はgain順にまとめられ、全層を通じて最大 `STRATA_RAM_ADAPT` 個までI/O threadへstageされます。従って、この変数は層ごとの候補範囲を広げますが、全体のstage上限を増やしません。`STRATA_RAM_ADAPT_CACHED_W` はpage cache上のexpertの推定miss costに、`STRATA_RAM_ADAPT_PROMPT_W` はprompt routing seedに関係します。処理結果はserve終了時に `resident RAM (STRATA_RAM_ADAPT2)` の累積read/install/skipログへ反映されます。

## 根拠

- `src/program/generate.cpp:8267-8283` — serve用設定、既定値2、`atoi` と下限1の処理。
- `src/program/generate.cpp:10831-10843` — RAM適応2有効時のprompt routing seed。
- `src/program/generate.cpp:14794-14817` — 適応window境界でのRAM適応条件、前windowのinstallとseed更新。
- `src/program/generate.cpp:14820-14875` — 層ごとの候補生成、`2N`/`N`の制限、候補gain条件、全体のstage上限。
- `src/program/generate.cpp:14878-14900` — `STRATA_RAM_ADAPT2` が無効な旧経路ではこの値を使わず層ごと最大1組とする分岐。
- `src/program/generate.cpp:15361-15375` — resident RAM適応処理の累積ログ。

`docs/DETAILS.md` および既存の設計資料には、この環境変数固有の値域や性能測定の記載を確認できませんでした。ここでは測定値や性能効果を主張しません。
