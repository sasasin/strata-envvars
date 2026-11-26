# `DF2B_SECS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`DF2B_SECS` は、Strata の Metal 用独立ベンチマーク `engine/metal/tests/df2_bench.cpp` の `soak` モードで、stand-in graph を連続実行する時間（秒）を決める。通常の Strata エンジンやモデル推論の設定ではなく、このベンチマークの `main` 内でのみ参照される。`DF2B_ONLY` の値が正確に `soak` の場合に限り読み取られる（`engine/metal/tests/df2_bench.cpp:62-79,442-450`）。

## 値と判定

`DF2B_ONLY` が `soak` のとき、環境変数が未設定なら `60.0` 秒、設定済みなら `std::atof` の戻り値を使う。文字列全体の妥当性検査、空文字の特別扱い、範囲制限はない。したがって空文字や数値に変換できない先頭部分は通常 `0.0` となり、`12junk` のように数値として読める接頭部があればその値になる。大文字小文字や前後の空白を独自に検査しない。ループ条件は経過時間が `secs` 未満かどうかだけである（`engine/metal/tests/df2_bench.cpp:442-447`）。

| 条件 | unset | 設定例と結果 | 無効・境界例と結果 |
|---|---|---|---|
| `DF2B_ONLY=soak` | `60.0` 秒 | `2.5` → 約 2.5 秒、`12junk` → `atof` が読む数値接頭部 | 空文字、`junk`、`0`、`0anything`、負値 → ループ条件を満たさず stand-in graph の反復なし。C ライブラリが `nan` と解釈する値も比較が成立せず反復なし。`inf` と解釈する値は終了条件を満たさず実質的に無期限となる |
| `DF2B_ONLY` が `soak` 以外または未設定 | 参照されない | 該当なし | 該当なし |

## 有効になる条件

- Metal ベンチマーク `df2_bench` を実行し、そのプロセスで `DF2B_ONLY` が大文字小文字も含めて正確に `soak` であること。`DF2B_ONLY` 自体も `getenv` で読み取った文字列との完全一致で選択される（`engine/metal/tests/df2_bench.cpp:79,442`）。
- この分岐は `mtl::Context` の初期化、Metal kernel のコンパイル、stand-in 用データと dispatch の準備の後に到達する。準備処理が失敗して先に終了する場合は `DF2B_SECS` の値は使われない（`engine/metal/tests/df2_bench.cpp:62-72,423-425,442`）。
- `DF2B_SECS` はこのベンチマークの soak 分岐以外では参照されない。対象 commit のリポジトリ全体で完全一致検索した読み取り箇所は `engine/metal/tests/df2_bench.cpp:443` のみ。

## 実行時の詳細

`main` 起動後、`DF2B_ONLY` が `soak` と判定された時点で `DF2B_SECS` を一度読み、ローカル変数 `secs` に保持する。その後、経過時間が `secs` 未満の間、GPU 上で stand-in graph を実行する。ここで使うのはコメント上「verify window」の代用として準備されたメモリ帯域負荷用 graph であり、実際のモデル推論や drafter の通常の処理を実行する分岐ではない（`engine/metal/tests/df2_bench.cpp:421-425,442-447`）。

値の読み取り後に環境変数を変更しても、保持済みの `secs` は変わらない。正の有限値では指定時間を超えた最初の graph 実行後にループを抜けるため、厳密な終了時刻を保証する timeout ではない。約 5 秒ごとにその区間の GPU 実行時間中央値を出力し、分岐の最後は終了コード `0` で戻る。ゼロまたは負値ではループを一度も実行せず同じく `0` で戻る（`engine/metal/tests/df2_bench.cpp:442-450`）。

## ログと測定値

soak 分岐に入る前に、秒数は含めず次の設定行を stdout に出す（`engine/metal/tests/df2_bench.cpp:441-443`）。

```text
config: pos %d, mm4 variant %s, head variant %s, host gap %.2f ms, iters %d
```

各約 5 秒の区間で反復があった場合、次の形式の行を stdout に出し、その後バッファを flush する。秒数が 5 秒未満ならこの区間ログは出ない。入力文字列の警告や無効値エラーを出す処理はこの分岐にない（`engine/metal/tests/df2_bench.cpp:446-449`）。

```text
t=%3.0fs  stand-in graph GPU median %.3f ms (n=%zu)
```

この調査ではベンチマークを実行していないため、実測値は記載しない。

## 根拠

- `engine/metal/tests/df2_bench.cpp:62-79` — ベンチマークの起動、`DF2B_ONLY` の読み取りと既定値。
- `engine/metal/tests/df2_bench.cpp:421-425` — stand-in workload の説明と構築。
- `engine/metal/tests/df2_bench.cpp:441-450` — 設定ログ、`DF2B_SECS` の `atof` 変換、反復・5 秒ごとの出力・終了。
