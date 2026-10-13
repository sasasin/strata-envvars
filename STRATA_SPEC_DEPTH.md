# `STRATA_SPEC_DEPTH`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

MTP（multi-token prediction）draft の深さごとに、検証された draft 数と受理された数をリクエストごとに stderr へ出す診断用スイッチです。draft の生成、検証、受理条件を変えません。

実装は `src/program/generate.cpp` のリクエスト処理にあります。集計配列はリクエストごとに初期化され、decode window ごとに更新されます。環境変数はリクエスト末尾の出力判定で読み取られます。

## 値と判定

値の parse はせず、`std::getenv("STRATA_SPEC_DEPTH") != nullptr` だけで判定します。

| 状態 | 動作 |
|---|---|
| 未設定 | 深さ別集計行を出さない |
| 任意の値 | 集計行を出す。`1` 以外や空文字も有効 |

この判定箇所に static cache はありません。各リクエストの末尾で環境の設定有無を確認します。通常のプロセス環境はリクエスト間で一定ですが、実行中に環境を書き換えた場合は、その後の判定に反映されます。

## 有効になる条件

この診断値が有効でも、数える対象は MTP の draft です。draft がない場合や、集計対象の window がない場合は、カウンターがゼロのまま、またはすべてゼロの行になります。

各 window では、suffix draft (`from_sfx`) ではなく、最初の decode window でもない場合に限り、MTP の深さ別カウンターを更新します。従って prompt 処理、suffix draft 専用の window、および最初の decode window は集計対象外です。カウンター更新自体は環境変数の有無にかかわらず行われます。

## 実行時の詳細

各リクエストで `dp_tested[8]` と `dp_ok[8]` をゼロ初期化します。window の照合で `a` 個の draft が受理された後、MTP の有効な深さ `d` について、`d <= a` かつ `d < 8` の範囲を数えます。深さ `d` は `d <= a` なら検証対象として `dp_tested[d]` に加算し、`d < a` なら受理として `dp_ok[d]` にも加算します。このため、最初に不一致となった深さも tested に含まれます。

リクエスト末尾で変数が設定されていれば、次の形式の行を stderr に出します。

```text
strata serve: spec depth: accepted/tested <d0> <d1> <d2> <d3> <d4>
```

実際には各深さの `accepted/tested` の数値が5組並びます。配列は8段まで保持しますが、出力は深さ0〜4のみです。環境変数はこのログの有無だけに使われ、集計処理を有効・無効にしたり MTP の結果を変えたりしません。

## 根拠

- `src/program/generate.cpp:11268-11273` — 各リクエスト内の depth counters 初期化。
- `src/program/generate.cpp:12068-12074` — window 内の一致数 `a` を求め、MTP の深さ別 tested / accepted を更新する条件。
- `src/program/generate.cpp:12513-12523` — リクエスト末尾の環境変数有無判定と stderr 出力。
- `docs/DETAILS.md:1260` — `STRATA_SPEC_DEPTH=1` が各リクエストの draft 深さ別 acceptance を出力するとの説明。資料の `=1` は例であり、実装上は設定値を parse せず、設定されていることだけを確認する。
