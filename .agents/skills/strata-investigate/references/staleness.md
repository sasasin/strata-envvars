# 内容の陳腐化検出（staleness）

既存文書が「今の Strata でも正しいか」を、Strata 側の差分から機械的に絞り込む手順。
索引更新（`index-refresh.md`）の直後に走らせる。索引更新前に走らせる必要はない
（索引 SHA と Strata HEAD が一致している状態で判定する）。

## 全体の流れ

```
索引更新 (docs/envvars/000_envvers.md, docs/cli/000_cli_tools.md, docs/cli/README.md)
  ↓
cli-grammar.py      … option 文字列の inventory (.cli-grammar.json)
evidence-index.py   … 文書の SHA と根拠座標の台帳 (.strata-evidence.json)
  ↓
find-stale.py       … Stage 1/2/3 で判定 (.strata-stale.json)
  ↓
mark-stale.py       … 候補を git rm + 試行記録から消す（既定 dry-run）
  ↓
create-*.py         … (3) 未調査に戻った分を再作成（--stale-report で理由を渡す）
  ↓
check-docs.py       … 突合
```

生成物 4 種は `.gitignore` 済み。毎回作り直す。

## Stage 0 — 証拠台帳

```bash
python3 .agents/skills/strata-investigate/scripts/evidence-index.py
```

各文書から次を拾う。

- `調査対象:` 行の commit SHA と調査日
- 根拠座標 `path:line`（または `path:12-30`）。Strata ツリーに実在するパスに正規化する。
  このリポジトリ自身の参照（`docs/envvars/000_envvers.md` 等）は除外、ファイル名だけ
  （`harness.py`）は Strata 内で一意なら解決し、複数候補は全候補を調べる。

## Stage 1 — 根拠座標が差分で動いたか

```bash
python3 .agents/skills/strata-investigate/scripts/find-stale.py
```

文書ごとの `doc_sha..基準 revision` で `git diff -M -U0` を引き、引用行範囲が hunk と交差するかを見る。

**diff は pathspec なしで全ツリーを引く**（`staleness_lib.hunk_data()`）。引用ファイルだけに絞ると、
大きなレイアウト移動で old パスが diff に入らず rename 検出が壊れて「全文追加」の巨大 hunk になり、
token-in-diff の誤検知を量産する。`-M` を効かせれば純粋な移動 (R100) は hunk を出さず、
内容が動いた箇所だけが候補になる。

**hunk ごとに「既知トークン -> 抜粋行」の写像を 1 回作る**（`WORD_RE` で語を切り出して
`known_tokens` と突き合わせる）。文書側の照合は写像参照の O(1)。語全体で一致させるので
`STRATA_PF_FUSED` の語に `STRATA_PF_FUSED_SM75` は入らない。

**並列化**: doc_sha 単位の全ツリー diff、候補ごとの `git log`（changed_commits）、
name index の git grep、`--with-symbols` の git grep は `--parallel N`（既定 `min(8, CPU コア数)`）
で `concurrent.futures.ThreadPoolExecutor` による並列。envvars と cli で同じ doc_sha の diff を
共有する。doc_sha 個の全ツリー diff が走査時間の大部分を占めるので、
`check-docs.py --stale` の commit 別分布で doc_sha が溜まっていないかを見る。

| 判定 | 意味 | 処置 |
| --- | --- | --- |
| `same-revision` | 索引と同じ commit 時点で書かれた | 対象外 |
| `hunk-intact` | 触れたコミットはあるが引用行範囲は動いていない | 削除しない |
| `file-only` | 引用ファイルは動いたが引用行範囲は無傷 | Stage 3 へ |
| `token-in-diff` | 動いた hunk の +/- 行に環境変数名／option 文字列そのものが出る | **削除候補（高確度）** |
| `cited-file-gone` | 引用ファイルが現行ツリーに無い | Stage 3 の所在追跡へ |
| `unknown-sha` | 文書の SHA が Strata に実在しない（誤記） | 索引 SHA と 3 文字以内なら `sha_suggestion` を添える。本文修正でも、削除→再作成でも解決できる |
| `no-meta` | 調査対象行が無い | 本文修正 |

名前の突き合わせは境界付き正規表現（`(?<![A-Za-z0-9_-])NAME(?![A-Za-z0-9_-])`）。
部分一致だと `STRATA_PF_FUSED` の差分に `STRATA_PF_FUSED_SM75` が混入するので使わない。

## Stage 2 — 主題トークン交差

Stage 1 の `token-in-diff` がこれ。索引より古い commit で書かれた文書のうち、hunk と交差する
件数は多いが、主題トークンそのものが出ている差分に絞ると大幅に減る。ここが消すに値する範囲。

## Stage 3 — 補助判定（`--stage3`）

- **envvars S-a 所在移動**: 名前の所在は `build_name_index()` が作る「名前 → 出現ファイル」表で引く
  （git grep は 3 回だけ: 大文字のクォート名、`$NAME` / `${NAME:-…}`、bat の `%NAME%`）。
  変数ごとに grep を走らせると走査が重くなる。
  - 表に無い → `name-gone`（候補。索引更新で消えるはずなので、索引に残っているなら索引側を疑う）
  - 見付かったが引用ファイルに無い → `moved`（**削除しない**。引用座標だけが古い）
  - 引用ファイルに在る → `file-only` のまま（差分は出たが引用箇所は無傷）
  - `GPUS`・`HOME` のように一般名は、shell 参照（`${GPUS:-…}` のような展開）まで拾わないと
    所在移動を誤判定する
- **envvars S-b 引用シンボル**（`--with-symbols --symbol-limit N`）: 文書が挙げる helper・修飾名が
  現行に存在するか。シンボルは name index に載らないので、この判定だけ変数あたり git grep が走る。
  費用対効果が小さいので既定の上限は 200 件。
- **cli S-c option inventory**: `cli-grammar.py` が Strata 全体から `"--xxx"` 文字列を拾い、
  索引の option identity と突合する。索引更新時に必ず再生成する。
  - 索引の option が inventory に無い → `option-absent-in-grammar`（候補）
  - `token-in-diff` の判定にも使う: 差分が option を宣言するファイル由来でなければ（usage 文言・別ファイル）
    `file-only` に落とす。

## 削除 (2) — mark-stale.py

```bash
python3 .agents/skills/strata-investigate/scripts/mark-stale.py --limit 20            # dry-run
python3 .agents/skills/strata-investigate/scripts/mark-stale.py --apply --limit 20    # 実行
python3 .agents/skills/strata-investigate/scripts/mark-stale.py --scope cli \
  --exclude-token=--json --exclude-token=--quiet --limit 200 --apply                  # 共通 option を後回し
```

- 既定の削除対象 verdict は `token-in-diff` / `option-absent-in-grammar` / `symbol-gone`。
  `name-gone` と `cited-file-gone` は索引更新・所在確認が要るので既定外。
- `--exclude-token=OPTION`（繰り返し可）で主題トークンを除外する。共通 option（`--json`、`--quiet`、
  `--version` など）を先に除外して、動作の意味が変わる option（`--backend`、`--preset`、`--show-key` など）から消す。
  `--help` は索引に載せず文書も作らない（`index-refresh.md` §3）ので候補に出ない。
  索引の option inventory との突合 (S-c) で `option-absent-in-grammar` 側に出たものは除外不要。
  ```bash
  python3 .agents/skills/strata-investigate/scripts/mark-stale.py --scope cli \
    --exclude-token=--json --exclude-token=--quiet --exclude-token=--version
  ```
- 除外は運用側で明示する。スクリプトに既定の除外リストは持たせない（暗黙に消えると
  何を除いたか分からなくなるため）。`--help` は文書が存在しないので除外指定は要らない。
- envvars は `.create-envvars-docs.state.json` から entry を消して「未調査」に戻す
  → `create-envvars-docs.py` が素直に拾う。CLI は索引の予定リンクが残るので `create-cli-docs.py` が拾う。
- 索引の名前は消さない（Strata が読むことは索引更新で確認済みの前提）。
- 削除した項目は `.strata-stale.removed.json` に理由（触れたコミット、差分行、判定）を保存する。
- **上限（`--limit`）で刻む**。1 リリースで本文の 1 割を超えないようにするのが安全。

## 再作成 (3)

```bash
uv run ./create-envvars-docs.py --dry-run -l 20
uv run ./create-envvars-docs.py -p 5 -l 20          # .strata-stale.json を自動で添付
uv run ./create-cli-docs.py -p 12 -l 40
```

`--stale-report` で「旧文書の SHA、触れたコミット、差分行、現在の所在候補、消えた識別子」が
codex への依頼文に添えられる。報告の revision が Strata HEAD と違う場合は自動的に無視される。

## 再作成後の確認

- `find-stale.py` をもう一度走らせて候補が減っていることを確認する（同じ commit 基準に
  揃うので `token-in-diff` は 0 になる）。`check-docs.py --stale` の commit 別分布でも追える。
