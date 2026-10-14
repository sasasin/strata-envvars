# `STRATA_ADAPT_ASYNC_BATCH`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve --adapt-async 1` の適応層が、RAM 上の expert arena から GPU expert cache へ expert を入れ替えるとき、1 tick に投入する H2D コピー数の上限を指定します。対象は arena を使う経路だけです。上限は round 全体の swap 数ではなく、同じ round 内で分割して順次投入する各 batch の件数です。

## 値と判定

`generate.cpp` 内の整数用 `a_env` helper が `getenv()` の値を `atoi()` で変換します。値が未設定または空文字なら既定値を使い、それ以外は `atoi()` の結果を使います。`STRATA_ADAPT_ASYNC_BATCH` の既定値は `0` です。

| 環境変数の状態・値 | `a_batch` | 動作 |
|---|---:|---|
| 未設定、空文字 | 0 | round の全コピーを1 batch として投入 |
| `0`、数値として変換できない文字列 | 0 | round の全コピーを1 batch として投入 |
| 正の整数 N | N | 1 tick に最大 N コピーを投入し、完了後に次の batch を投入 |
| 負の整数 | 0 | `max(0, atoi(...))` により0として扱い、round の全コピーを1 batch として投入 |

`atoi()` は文字列全体の厳密な検証をしません。先頭の空白や符号を受け付け、数値の後ろに文字があっても数値部分を変換します（例: `"  +16tail"` は16、`"tail16"` は0）。明示的な空文字だけは `atoi()` に渡さず既定値になります。この変数では既定値も0なので、未設定・空文字・無効な数値文字列はいずれも全コピー投入になります。コードに変換値の上限検査はありません。

## 有効になる条件

- 適応層が有効で、`--adapt-every` と `--adapt-swaps` が正であること。
- `--serve` と `--adapt-async 1` を使い、expert arena (`srcp == &arena_src`) の経路であること。実装上、arena 以外では `a_batch` を0に固定します。
- この arena の非 pipelined 経路であること。arena と `--pipeline-windows 2` の組み合わせでは非同期適応層自体が blocking tier に切り替わります。また、ドキュメント上の arena 経路は単一 GPU・layer split なしです。

環境変数に正数を設定しても、これらの条件が揃わなければ batch 上限は適用されません。arena 以外の resident RAM 経路では、同じ非同期適応層でも round の全 swap を1 batch で投入します。

## 実行時の詳細

値は `generate.cpp` の非同期適応層の状態を初期化するときに一度読み取られ、`a_batch` に保持されます。tick ごとや request ごとの再読込はありません。起動後に環境値を変えても、既に初期化された状態には反映されません。

arena 経路では適応対象を選び、GPU cache 上で退避する expert を non-resident にした後、`a_post_batch()` が次の範囲を job thread に渡します。`a_batch > 0` の場合、範囲の終端は `min(aswaps.size(), a_bi + a_batch)` です。0 の場合は残りの全 swap を範囲に含めます。コピー完了後、実装はその batch に含まれた expert の residency table を更新し、残りがあれば次の batch を投入します。したがって N を小さくすると1 tick あたりの投入数を抑える一方、1 round のコピーが複数 batch に分かれて進むことがあります。

batch 内のコピー元は arena の blob で、各コピーは expert の GPU slot へ `cudaMemcpyAsync(..., cudaMemcpyHostToDevice, ...)` で投入されます。`STRATA_ADAPT_ASYNC_WAIT`（既定1）はコピー完了を待ってから batch の residency を確定するか、未完了なら後続 tick へ進むかに関係します。batch 数を指定するこの変数自体は wait/poll 方針を変更しません。失敗時には適応処理が失敗し、呼び出し元で `ERR an adaptive refill failed` などのエラーになります。

## 根拠

- `src/program/generate.cpp:9062-9070`: `a_env` の unset/空文字処理、`atoi()`、arena 条件、および既定値0。
- `src/program/generate.cpp:6983-6993`: `--adapt-async` の適用条件。arena と `--pipeline-windows 2` の併用は非同期 tier を無効化する。
- `src/program/generate.cpp:9188-9204`: batch ごとのコピー投入範囲と、0なら残りすべてを含める処理。
- `src/program/generate.cpp:9253-9287, 9295-9349`: tick 進行、退避処理、各 batch の完了後に residency を更新して次 batch を投入する処理。
- `src/program/generate.cpp:9172-9181`: arena から GPU slot への非同期 H2D コピー。
- `docs/DETAILS.md:180-187`: arena の `--adapt-async` 経路と、この変数がコピー数を制限すること、既定0（全投入）の説明。測定については RTX 3090 + Ryzen 5 5600X の cold prompt 条件で x1.07–1.11 と記載されているが、これはこの変数単独の効果を測った値ではない。
