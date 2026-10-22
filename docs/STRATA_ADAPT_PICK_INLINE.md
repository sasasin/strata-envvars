# `STRATA_ADAPT_PICK_INLINE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

arena を使う非同期 adaptive tier で、swap 候補の選択処理（`a_pick`）を window 間の tick を処理するスレッド上で行うか、job thread に渡すかを選びます。既定は tick 側での選択です。選択対象や候補の評価式を変える設定ではなく、選択処理を実行するスレッドを切り替えます。

この設定は `src/program/generate.cpp` の実行コードで参照されます。コメントやテストだけの名前ではありません。

## 値と判定

環境変数名を受け取るローカル helper `a_env` が、値が未設定または空文字なら既定値を返し、それ以外は `std::atoi` の結果を返します。`STRATA_ADAPT_PICK_INLINE` の既定値は `1` で、その結果が `0` 以外なら inline 選択、`0` なら job thread での選択になります。

| 環境変数の値 | `a_env` の結果 | 選択処理 |
|---|---:|---|
| 未設定 | 1 | tick 側（inline） |
| 空文字 | 1 | tick 側（inline） |
| `1`、`2`、`-1` | それぞれの整数 | 0 以外なら tick 側（inline） |
| `0`、`0anything` | 0 | job thread |
| `true`、`anything` | 0 | job thread |

`atoi` は文字列全体の厳密な数値検証ではありません。先頭の空白と符号の後にある数字列を変換し、数字列の後ろは判定しません。したがって、たとえば ` 1tail` は `1`、`1tail` も `1` として扱われます。数値として読み取れる先頭部分がない値は `0` になります。大文字小文字比較や真偽文字列の解釈はありません。

根拠: `src/program/generate.cpp:10390-10398`。

## 有効になる条件

この値が `a_env` に渡されるのは arena source の場合だけです。`a_arena` が偽なら `a_arena && ...` の短絡評価により環境変数を読みません。また、実際に非同期 adaptive tier が作られるには、`--adapt-async` が有効で、usage table が空でなく、かつ arena source または resident source の交換容量条件を満たす必要があります。したがって `STRATA_ADAPT_PICK_INLINE` が設定されていても、arena を使わない実行や非同期 adaptive tier が開始されない実行には影響しません。

`STRATA_ADAPT_ASYNC_WAIT` と `STRATA_ADAPT_ASYNC_BATCH` は同じ arena 経路で別々に読み取られ、コピー完了の待ち方と tick あたりの copy-in 数を決めます。これらは `STRATA_ADAPT_PICK_INLINE` の値を変更しません。

根拠: `src/program/generate.cpp:10387-10406`。

## 実行時の詳細

設定値は adaptive loop の初期化時にローカル変数 `a_inline` として一度読み込まれます。`static` cache ではないため、このコード範囲では初期化のたびに環境を参照します。実際の環境変更をプロセス実行中に行った場合の反映時期や子プロセスへの転送は、この設定のコードからは確認できません。

非同期 adaptive tier の arena 経路では、swap round を始める tick で `a_inline` が真なら、そのスレッドが `a_pick()` を実行してからコピー処理へ進みます。偽なら `a_pick` または `a_choose` を `ajob` に post し、job thread 側に選択を委ねます。`a_pick` は usage と residency の snapshot を使って候補と退役対象を選びます。環境変数はこの選択処理の実行場所を切り替えます。

リクエスト終了時の累積統計ログでは、arena の場合に `pick inline` または `pick on the job` と、inline 選択の平均 `ms/round` が表示されます。`docs/DETAILS.md` も arena の既定を `STRATA_ADAPT_PICK_INLINE=1` と記載しています。そこにある RTX 3090 の性能値は arena の非同期 adaptive tier 全体の測定であり、この変数単独の効果を測った値とは読み取れません。

根拠: `src/program/generate.cpp:10399-10406,10581-10614,15376-15384`; `docs/DETAILS.md:202-209`。

## 根拠

- `src/program/generate.cpp:10387-10398` — arena 経路の特定、環境値 helper、既定値 `1` と非ゼロ判定。
- `src/program/generate.cpp:10399-10406` — 非同期 adaptive tier の起動条件と適用範囲。
- `src/program/generate.cpp:10581-10614` — tick ごとの round 開始時に inline 実行または job thread に post する分岐。
- `src/program/generate.cpp:15376-15384` — round 統計と選択方法のログ。
- `docs/DETAILS.md:202-209` — arena 非同期 tier についての説明と `STRATA_ADAPT_PICK_INLINE=1` の既定記載。
