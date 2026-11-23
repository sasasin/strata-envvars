# `STRATA_PIPED_LOOKUP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

多段 layer split の pipelined MTP で、各 slot の次の verifier window に prompt lookup（過去に同じ末尾 token 列が続いた位置から得る候補）を MTP drafter の候補に代えて載せる機能を opt-in する。両方の候補がある場合、slot 共通の `DraftPolicy` が lookup window の予測採算が MTP window よりよいと判断したときだけ lookup を選ぶ。候補は verifier に渡され、採用 token は検証後に出力される。環境変数は生成結果を直接指定せず、候補選択経路と slot window の最大行数を変える（`engine/src/program/generate.cpp:7815-7829,17553-17567,17608-17627,17673-17700`）。

## 値と判定

`generate.cpp` の初期化時に `std::getenv` で一度取得し、`o.suffix_draft > 0` かつ値が未設定でなく、空文字でなく、先頭文字が `'0'` でなければ有効とする。文字列全体の parse や大文字小文字の変換はない。したがって `1`、`true`、`yes`、` 1`、`10x` は有効、`0`、`0anything`、空文字、未設定は無効。後続文字・空白・数値としての妥当性は検査しない。`--suffix-draft N` は `atoi` 後に 0 以上へ clamp され、0 以下なら環境変数が設定されていても無効（`engine/src/program/generate.cpp:4116,7821-7824`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `--suffix-draft` が正 | 無効 | `1`, `true`, ` 1` | 空文字, `0`, `0anything` |
| `--suffix-draft 0` または負値（CLI 側で 0 に clamp） | 無効 | なし | 未設定を含むすべて |

## 有効になる条件

- `--suffix-draft N` が `N > 0` であること。オプションの既定値は 3、明示的な `--suffix-draft 0` は無効化する（`engine/src/program/generate.cpp:1158,1341-1342,4116,7821-7824`）。
- batch serving の slot 経路で `pmtp` が有効であること。コード上、`pmtp` は `piped && piped_mtp && ver.deferred_commit_on() && pmtp_group_cap <= batch_max_t()` の場合だけ true（`engine/src/program/generate.cpp:17423-17436`）。`piped` は `--batch` と `--batch-groups > 1`、layer split が必要で、`piped_mtp` は batch MTP が有効で `STRATA_PIPED_MTP` が有効な group 解決を経て成立する。後者の有効判定も未設定・空文字・先頭 `'0'` を除外し、成立後は `atoi` 値を 1 以上かつ verifier / `--spec` の上限以下に clamp する（`engine/src/program/generate.cpp:7748-7749,7804-7813,17423-17436`）。
- `--batch-mtp` の制約も満たすこと。batch は serving (`--serve`) で 2 slot 以上、各 layer が別 GPU にある必要があり、MTP と `--spec >= 2` が必要。Metal では batch MTP の slot draft は無効化される。条件を満たさない batch MTP は警告後に無効化される（`engine/src/program/generate.cpp:7770-7802`）。
- prompt lookup 候補が現在の slot の文脈から得られること。履歴を使って proposal を要求し、候補があっても `DraftPolicy` が lookup を選ばなければ MTP 候補が使われる（`engine/src/program/generate.cpp:17608-17627`）。

上記を満たさない場合、`pm_lookup` が true でも `plk = pmtp && pm_lookup` が false となり、この変数による pipelined slot lookup は実行されない（`engine/src/program/generate.cpp:17553-17561`）。この経路の判定に OS 固有の条件はない。実際の利用には多段 GPU layer split と deferred commit 対応が必要である。

## 実行時の詳細

環境変数は `generate.cpp` の batch/pipeline 設定時に一度読み、関数内の `const bool pm_lookup` に保持する。プロセス実行中に環境値を変えても再評価されない。CLI 引数で環境変数値を上書きする機能はなく、`--suffix-draft` は lookup drafter 自体の利用条件として併用される（`engine/src/program/generate.cpp:4116,7815-7824`）。

`pm_lookup` が true の場合、pipelined MTP が有効になったときに slot ごとの `SuffixDrafter` を作り、stderr に lookup を使う slot window の最大行数と候補選択方針を出す。各 slot の位置ごとに候補を一度求め、`DraftPolicy::choose` の結果が lookup かつ `pk.t >= 2` のとき lookup token 列を window に載せる。そうでなければ MTP の draft 列を使う。slot 当たりの window 上限は、MTP の行数に加えて `--spec` と narrow verifier window の slot あたり容量から計算される（`engine/src/program/generate.cpp:7825-7829,17553-17567,17602-17627,18122-18135`）。

slot の履歴はその slot の token 列と次 window が供給した token から構成される。prompt admission 時は既存の solo-path lookup 履歴を再利用できる場合に引き継ぎ、そうでなければ slot の既存 token と現在 token から再構築する。turn read の履歴も slot の文脈に合わせて更新する（`engine/src/program/generate.cpp:19374-19389,23543-23563`）。timeout はこの環境変数に対して設けられていない。lookup 候補そのものがなくても MTP drafter の window を待つ経路が続く（`engine/src/program/generate.cpp:17613-17627,18035-18043`）。

## ログと測定値

`plk` が有効な場合、stderr に次の行を出す（`%d` は `pmtp_rows_per_slot` の値）。

```text
strata generate: STRATA_PIPED_LOOKUP: a slot's window in the pipelined groups takes up to %d rows, the prompt lookup's drafts where they promise more than the draft layer's
```

環境変数が有効でも `pmtp` が成立しない場合、この行は出ない。設定値専用の無効値警告はない。lookup 候補の採用数に関する専用ログは見当たらない。pipelined window の MTP draft 処理や verifier で失敗すれば、既存の `ERR batch MTP slot ...` または `ERR ...` 経路で batch 処理が失敗する（`engine/src/program/generate.cpp:17529-17536,17729-17743,18186-18189`）。

`docs/DETAILS.md:1543-1546` は一般の prompt lookup が過去の一致から候補を出し、採算が合う場合だけ使われ候補を検証すると説明するが、`STRATA_PIPED_LOOKUP` 固有の性能測定値は記載していない。ソースコメントはこの pipelined 経路について「two-card measurement」まで opt-in としているが、数値結果は示していない（`engine/src/program/generate.cpp:7815-7820`）。

## 根拠

- `engine/src/program/generate.cpp:7815-7829` — 環境値の判定、`--suffix-draft` 条件、slot window 行数。
- `engine/src/program/generate.cpp:7748-7749,7770-7807,17423-17436` — batch MTP / pipelined groups の前提条件。
- `engine/src/program/generate.cpp:17553-17567,17602-17627,18122-18135` — slot lookup drafter の作成、候補選択、verifier rows への設定。
- `engine/src/program/generate.cpp:19374-19389,23543-23563` — slot lookup 履歴の設定・引き継ぎ。
- `engine/src/program/generate.cpp:17529-17536,17729-17743,18186-18189` — batch MTP / verifier の失敗出力。
- `docs/DETAILS.md:1543-1546` — 一般の prompt lookup の説明（環境変数固有の測定ではない）。
