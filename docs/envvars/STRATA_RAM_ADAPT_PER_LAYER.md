# `STRATA_RAM_ADAPT_PER_LAYER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の resident RAM expert copy を staged promotion で入れ替えるとき、各 layer で比較する incoming / outgoing 候補数を調整する。未設定時は 2。値を `P` とすると、候補計算は各 layer で incoming を最大 `2P` 件、outgoing を最大 `P` 件に絞る。これは候補数であり、実際に stage される交換数の保証ではない。`STRATA_RAM_ADAPT` の総数上限や候補の gain、queue 状態で実数は減る（`engine/src/program/generate.cpp:12333-12348,22847-22918`; `engine/src/core/expert_source.cpp:5009-5031`）。

この設定は resident RAM copy の内容を選ぶ staged 枝に作用する。GPU tier の選択規則、routing、重みを直接変更しない。従来の同期 RAM 置換枝では参照されない（`engine/src/program/generate.cpp:22847-22849,22919-22926`）。

## 値と判定

serve 初期化時に `std::getenv` で設定有無を確認し、設定されていれば `std::atoi` の結果を `std::max(1, ...)` に渡す。設定値は最低 1 に clamp される。未設定だけが既定値 2 のままで、空文字も含む設定済みの値は変換後に最低 1 になる（`engine/src/program/generate.cpp:12334-12348`）。

| 条件 | unset | 変換後の実効値（入力例） | `atoi` が 0 を返す入力例（実効値） |
|---|---:|---|---|
| `--serve` の初期化 | 2 | `1`, `2`, `4`, `+3`, ` 3tail` はそれぞれ `1`, `2`, `4`, `3`, `3` として扱う | 空文字、`0`, `0anything`, `-2`, `true`, `n/a` は変換結果 0 が 1 に clamp される |

`atoi` は数値文字列全体の検証をしないため、先頭の空白・符号の後の十進数の先頭部分を読み、後続の非数値部分を無視する。数値部分がなければ 0 となる。設定値は拒否されず、`int` の範囲内なら設定済み入力はすべて実効値 1 以上になる（上限 clamp はない）。`int` の範囲を超える入力についてコードに検証処理はなく、値を規定できない（同 `generate.cpp:12347`）。

## 有効になる条件

値の読み取り自体は `o.serve` の初期化ブロック内で行われるが、値が候補計算に使われるには次の条件がすべて必要（`engine/src/program/generate.cpp:12302-12307,22843-22849`）。

- `STRATA_RAM_ADAPT2` が設定され、`atoi` の結果が非 0 であること。
- `STRATA_RAM_ADAPT` が設定され、decode loop 内で一度評価される `atoi` の結果が正であること。これは staged promotion の window あたりの総数上限にもなる。
- 初回 window ではなく、adaptive usage があり、pending swap がなく、adaptive round が idle であること。
- `src.complement_ready()` が真で resident RAM complement が利用可能であること。コード上この枝は複数 GPU、peer-device、remote optimization、`--batch` 実行を除外する。
- layer に VRAM 外の resident outgoing expert と、VRAM 外かつ RAM 非 resident で候補スコアが 2 以上の incoming expert があること。`STRATA_RAM_ADAPT_SKIP_TOP` は incoming 候補から decode usage 上位を除外する。

`STRATA_RAM_ADAPT_PROMPT_W`（既定 0.25）が正なら prompt routing seed が incoming score に加算され、window ごとに seed は 0.95 倍される。`STRATA_RAM_ADAPT_CACHED_W`（既定 0.15）は page-cache tier の incoming score に掛かる。これらは候補順位に関わるが、本変数の候補数上限とは別の値である（`engine/src/program/generate.cpp:12345-12348,16056-16067,22856-22900`）。

## 実行時の詳細

`STRATA_RAM_ADAPT_PER_LAYER` は `--serve` 初期化時に一度読み、`RamAdapt2::per_layer` に保持する。リクエストごとや window ごとに環境から再読込する処理はなく、実行中の環境変更は反映されない。専用 CLI 引数による上書きもない（`engine/src/program/generate.cpp:12332-12349`）。

staged 枝が有効な window 境界で、各 layer の候補から incoming を最大 `2P`、resident outgoing を最大 `P` に絞る。その後、既に queue にある候補を除外・減点し、差分 gain が 1 未満なら採用せず、全 layer の候補を gain 順に並べて `STRATA_RAM_ADAPT` 件まで `ram_stage` に渡す。従って `P` を増やしても交換が必ず増えるわけではない。queue が `STRATA_RAM_ADAPT_QUEUE` の上限（未設定時 64）に達した場合や同じ layer の競合 job がある場合、`ram_stage` は false を返して stage しない。成功した読み込みは source の I/O thread で行われ、後の window 境界で install 対象になる（`engine/src/program/generate.cpp:22850-22918`; `engine/src/core/expert_source.cpp:5007-5031`）。

この初期化と利用箇所に OS / backend 固有の分岐は見当たらない。実際の適用は上記 serve・resident RAM・単一 GPU 等の実行条件に従う（同 `generate.cpp:12332-12349,22847-22849`）。

## ログと測定値

この変数の値、parse 結果、候補数を直接表示するログや、無効文字列に対する警告・エラーはない。`STRATA_RAM_ADAPT2` が有効なら request 終了時に次の累積カウンター行を stderr に出す。実際の promotion が 0 件でも、`ram_adapt2.on` が真なら表示条件を満たす（`engine/src/program/generate.cpp:23801-23805`）。

```text
strata serve: resident RAM (STRATA_RAM_ADAPT2): <n> promotions read on the I/O thread, <n> installed, <n> skipped at the install (<n> of them: the GPU tier took one of the pair)
```

`docs/DETAILS.md:277-282` は `STRATA_RAM_ADAPT` の従来の同期置換動作を説明しているが、`STRATA_RAM_ADAPT2` の staged 枝や本変数の候補数制御は説明していない。同資料に本変数の測定値はないため、性能値は記載しない。

## 根拠

- `engine/src/program/generate.cpp:12302-12307,12332-12349` — serve 初期化、既定値と環境値の読み取り。
- `engine/src/program/generate.cpp:22843-22918` — 適用条件、候補数への反映、stage 上限。
- `engine/src/core/expert_source.cpp:5007-5031` — RAM stage queue と I/O thread の起動。
- `engine/src/program/generate.cpp:23801-23805` — staged promotion の累積ログ。
- `docs/DETAILS.md:274-282` — resident RAM の既存説明との照合。
