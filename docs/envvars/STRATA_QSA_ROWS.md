# `STRATA_QSA_ROWS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA の block score 計算で、最大4 query の呼び出しに query ごとの multi kernel ではなく `block_scores_rows_kernel<NQ>` を使う opt-in です。query の indexer key scores を計算するカーネルを切り替えます。top-k や attention のカーネルはこの変数では切り替えません。

## 値と判定

変数の文字列全体が ASCII の `1` 1文字と一致する場合だけ有効です。`getenv()` の結果を `v[0] == '1' && v[1] == '\0'` で判定し、数値 parse はしません。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| `1` | 有効 |
| 空文字、`0`、`10`、`true`、前後に空白のある値など | 無効 |

判定結果は `qsa_block_scores()` 内の `static const bool` に保存されます。したがって、最初にこの分岐へ到達した時点の値がプロセス内で使われ、その後の環境変更は再評価されません。環境変数を設定していても、分岐が使われなければ判定自体は遅延します。

## 有効になる条件

値が `1` でも、次の条件をすべて満たす呼び出しでだけ行スコア用カーネルを起動します。

- `qsa_block_scores()` が `nq > 0` で呼ばれ、indexer geometry が実装の固定 geometry（`idx_dim=128`, `idx_n_head=4`, `idx_block=4`）と一致している。
- `STRATA_SCORES_MULTI` が有効である。これは別変数で、未設定なら有効、設定時は `atoi(value) != 0` で判定されます。無効なら `STRATA_QSA_ROWS` の分岐に入らず、通常の単一 query 用経路へ進みます。
- `nq <= MQ` で、`active_blocks <= 0`。この分岐では decode の呼び出しと prefill の pooled16 呼び出しが対象になり得ます。
- 行カーネルの上限である `nq <= 4` を満たす。5〜8 query では helper が `false` を返し、後続の通常経路が選ばれます。

prefill の通常の score 呼び出しは正の `active_blocks` を渡すため、この切替を通りません。HIP の実装にもこの変数の読み取り箇所はなく、設計資料も HIP は対象外としています。

## 実行時の詳細

有効条件を満たすと、`qsa_block_scores()` は `qsa_block_scores_rows()` を呼びます。helper は query 数に応じて `block_scores_rows_kernel<1..4>` を launch し、起動エラーがあれば `qsa_block_scores rows: %s` を stderr に出して終了します。helper が `true` を返すと通常の multi kernel / Turing 向け halve kernel の分岐には進みません。rows kernel に入らない呼び出しでは、この環境変数による変更はありません。

rows kernel は各 query の query-vector slice を register に置いて block score を計算します。実装と `docs/QSAROWS.md` は、通常の multi kernel と同じ score bits を出す設計・検証として説明しています。これはスコア計算の選択であり、選択後の top-k は既存の `qsa_block_topk()` が行います。

`docs/QSAROWS.md` の合成 micro-bench（RTX 2080 Ti / RTX 3060、context 131k）では、multi kernel に対する score kernel の1 call当たり時間がそれぞれ T=1..4 で 47.2/56.9/78.2/101.2 µs 対 36.2/38.0/49.2/54.6 µs、および 73.4/109.4/151.9/193.5 µs 対 63.3/75.5/98.0/130.2 µs と記載されています。設計資料にある実エンジン測定は、Windows 上の RTX 3060 + RTX 2080 Ti の layer split、`--pipeline-windows 2`、131k context で、B-A-B の deterministic bench における decode tokens/s が +3.2% と +0.1% です。これらは資料に記載された条件下の値です。

## 根拠

- 値の完全一致判定、適用ゲート、呼び出しの優先順: `src/kernels/cuda/qsa_select.cu:1709-1744`。
- helper の query 数・geometry 判定、kernel 起動、起動エラー: `src/kernels/cuda/qsa_select.cu:1795-1807`。
- rows kernel の計算と `NQ=1..4` の実装: `src/kernels/cuda/qsa_select.cu:1064-1120`。
- `STRATA_SCORES_MULTI` の既定と parse: `src/kernels/cuda/qsa_select.cu:1547-1549`。
- verify window の呼び出し: `src/core/verify.cpp:1544-1548`。
- prefill が正の `active_blocks` を渡す呼び出し: `src/prefill/prefill.cpp:3148-3161`。
- 既存設計資料と測定条件: `docs/QSAROWS.md:1-5,31-63`、一覧表の要約: `docs/DETAILS.md:2220-2230`。
