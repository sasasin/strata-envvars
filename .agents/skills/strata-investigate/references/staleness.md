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

2026-11-02 実測: envvars 1627 文書すべてに座標があり、座標 17,283 件のうち Strata 実パス 15,985、
this-repo 参照 1,298、ファイル名のみ 134、実在せず 1。

## Stage 1 — 根拠座標が差分で動いたか

```bash
python3 .agents/skills/strata-investigate/scripts/find-stale.py
```

文書ごとの `doc_sha..基準 revision` で `git diff -U0` を引き、引用行範囲が hunk と交差するかを見る。

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
`STRATA_PF_FUSED` の差分に `STRATA_PF_FUSED_SM75` が出て誤検地になった実例があるため、
部分一致は使わない。

## Stage 2 — 主題トークン交差

Stage 1 の `token-in-diff` がこれ。2026-11-02 実測:

- envvars: `same-revision` 742 / `file-only` 684 / `hunk-intact` 182 / **`token-in-diff` 12** / `moved` 6 / `unknown-sha` 1（初回実行、S-a を変数ごと grep していた頃）
- cli: `file-only` 652 / `hunk-intact` 315 / **`token-in-diff` 115** / `same-revision` 43

索引より古い commit で書かれた 885 文書（envvars）のうち 701 件が hunk と交するが、
名前の出ている差分に絞ると 12 件になる。ここが消すに値する範囲。

## Stage 3 — 補助判定（`--stage3`）

- **envvars S-a 所在移動**: 名前の所在は `build_name_index()` が作る「名前 → 出現ファイル」表で引く
  （git grep は 3 回だけ: 大文字のクォート名、`$NAME` / `${NAME:-…}`、bat の `%NAME%`）。
  変数ごとに grep していた実装では 12 分かかっていたのが、約 3 秒になった。
  - 表に無い → `name-gone`（候補。索引更新で消えるはずなので、索引に残っているなら索引側を疑う）
  - 見付かったが引用ファイルに無い → `moved`（**削除しない**。引用座標だけが古い）
    2026-11-02 実測 4 件はすべて実移動だった: `HIPK_CFG` / `HIPK_DBG` / `STRATA_DS4_HIPK` は
    `src/dsv41/ds4_iq.cu` が `ds4_iq_hip.inc` へ分割、`STRATA_PIN_RESERVE_GIB` は
    `src/core/pinned.cu` から `src/core/expert_source.cpp` へ移っている。
  - 引用ファイルに在る → `file-only` のまま（差分は出たが引用箇所は無傷）
  - `GPUS`・`HOME` のように一般名は、shell 参照まで拾わないと所在移動の誤判定になる
    （`docker/entrypoint.sh` の `${GPUS:-…}` を読む行が拾えず moved に出ていた例がある）
- **envvars S-b 引用シンボル**（`--with-symbols --symbol-limit N`）: 文書が挙げる helper・修飾名が
  現行に存在するか。シンボルは name index に載らないので、この判定だけ変数あたり git grep が走る。
  費用対効果が小さいので既定の上限は 200 件。2026-11-02 実測では 300 件検査して候補は 1 件増。
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
  --exclude-token=--help --limit 200 --apply                                          # 共通 option を後回し
```

- 既定の削除対象 verdict は `token-in-diff` / `option-absent-in-grammar` / `symbol-gone`。
  `name-gone` と `cited-file-gone` は索引更新・所在確認が要るので既定外。
- `--exclude-token=OPTION`（繰り返し可）で主題トークンを除外する。CLI では `--help` が候補の大半を占める
  （2026-11-02 実測 115 件中 97 件）が、Strata 側の usage 文言変更が主で文書の骨格は変わらない。
  先に除外して、動作の意味が変わる option（`--backend`、`--preset`、`--show-key` など）から消す。
  索引の option inventory との突合 (S-c) で `option-absent-in-grammar` 側に出たものは除外不要。
  ```bash
  python3 .agents/skills/strata-investigate/scripts/mark-stale.py --scope cli \
    --exclude-token=--help --exclude-token=--json --exclude-token=--quiet --exclude-token=--version
  ```
- **`--help` の除外は運用側で毎回付ける**。スクリプトに既定の除外リストは持たせない（暗黙に消えると
  何を除いたか分からなくなるため）。CLI を回すコマンドには必ず `--exclude-token=--help` を添える。
  したがって `find-stale.py` の候補数に `--help` が残り続けるのは正常状態で、
  「候補 0」を目安にするのは envvars 側（共通 option 相当がない）だけ。
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

## 実測メモ（2026-11-02、Strata `c62d5e3a` 基準）

- 全走査（Stage 1/2/3、S-a 含む）で約 3 秒。`--with-symbols` 300 件追加で約 3 分。
- 索引 SHA と同じ commit で書かれた文書（envvars 755 / cli 43）は差分ゼロで intact。
  envvars の 872 件・cli の 1,083 件は索引より古い commit で書かれており、この手順の主な対象になる。
- 一巡の実例: envvars の `token-in-diff` 12 件と `unknown-sha` 1 件を `mark-stale.py --apply --limit 20`
  で削除（数秒）→ `create-envvars-docs.py -p 5 -l 13` で再作成（4 分 27 秒、全件 created）→
  `find-stale.py --stage3` 再実行で envvars の候補は 0 件（`token-in-diff` 0、`unknown-sha` 0、
  `moved` 4、`file-only` 686、`hunk-intact` 182、`same-revision` 755）。
  再作成文書には backend 別の判定表や `STRATA_GFX12_DEFAULTS` との相互作用まで書けており、
  旧文書になかった変化が拾えていた（`STRATA_HC_Q8`）。旧 SHA 誤記の `STRATA_MOVE_ALWAYS_COPY` も
  現行 SHA の文書に置き換わった。
- CLI の `token-in-diff` 115 件のうち `--exclude-token=--help` で 97 件を除外し、18 件を一巡させた
  （削除→ `create-cli-docs.py -p 12 -l 30` で 2 分 42 秒、全件作成）。対象は `--backend` 3、`--preset` 2、
  `--show-key` 2、`--force`、`--model`、`--batch-groups`、`--expert-cache-device1`、`--kv-grow`、`--mtp-q4`、
  `--experts`、`--vram-experts`、`--gpu`、`--gpus`、`--vision`。
  残った `--help` 97 件はそのまま候補として置く運用にした（スクリプトに既定除外は無い。
  CLI を回すたびに `--exclude-token=--help` を付ける）。
- 見付かった実例: `STRATA_ATTN_LANECELL` は既定値テーブル `t.push_back({"STRATA_ATTN_LANECELL", "1"})` が
  `src/core/arch_defaults.cpp` に加わり、`STRATA_HC_Q8` は `getenv` 呼び出しがコメント化されている。
- 再作成後は `find-stale.py` をもう一度走らせて候補が減っていることを確認する（同じ commit 基準に
  揃うので `token-in-diff` は 0 になる）。`check-docs.py --stale` の commit 別分布でも追える。
