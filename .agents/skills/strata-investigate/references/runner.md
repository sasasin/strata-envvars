# 一括実行（runner）

未作成分を一気に作るための 2 スクリプトは**リポジトリ直下**に置く（`docs/` 相対と
`.create-envvars-docs.state.json` の gitignore 前提に依存するため、skill 内へ移さない）。

```bash
cd "$HOME/src/github.com/sasasin/strata-envvars"
uv run ./create-envvars-docs.py -p 5 -l 100
uv run ./create-cli-docs.py -p 12 -l 100
```

## envvars 側（`create-envvars-docs.py`）

- 候補は `docs/envvars/000_envvers.md` の `- \`NAME\`` 行から決める。`docs/envvars/<NAME>.md` が
  存在しないものを**先に確定してから** 1 変数 1 codex セッションで起動する。
  古い `seq | xargs` 運用と違い、並列でも同じ変数を重複調査せず、全件作成済みなら何も作らない。
- 主なフラグ
  - `-l`, `--doc-limit N` … 今回作成する件数上限（`0` で全件、既定 1）
  - `-p`, `--parallel N` … 同時に動かす codex 数（既定 1）
  - `--dry-run` … 起動せず対象を一覧する（**実行前に必ずこれで目視**）
  - `--include-tried` … 調べても文書ができなかった変数を再調査候補に加える
  - `--reset-state` … 試行記録を消して組み直す（全履歴を失うので通常は使わない）
  - `--stale-report PATH` … `find-stale.py` の報告（既定 `.strata-stale.json`）。陈旧化で削除した変数の
    調査対象 SHA・触れたコミット・差分の抜書を codex への依頼文に添える。報告の revision が Strata HEAD と
    違う場合は自動で無視する（`create-cli-docs.py` にも同じオプションがある）
- 試行記録は `.create-envvars-docs.state.json`（`{変数名: {attempts, status, updated_at}}`）。
  `status` は `created` / `no-doc`（Strata が実際には読まない候補。`001_investigation.md` の手順どおり
  「索引との食い違い」として報告され、文書は作られない）/ `error`。
  既定では `status` の有無に関わらず記録済みの変数を避け、`--include-tried` で再調査する。
- no-doc の中身は二種類ある。判定を間違えやすい方:
  - Strata がまったく読まない名前（外部 lib・driver 専用、索引の誤拾い）→ 本文は作らない。
  - **Strata が読むが、読み取り箇所がテスト・parity 専用コードだけ**（GEMV_X、QUANT_CTAB、
    STRATA_WMMA_PARITY_EXACT など）→ `001_investigation.md` が実装根拠にしないと決めているので本文は作らない。
    索引には残す。索引は grep 由来の候補一覧で、自分の冒頭で「テスト・開発/e2e スクリプトが読む変数」を
    内訳に含めると宣言している。
  - 逆に、セットアップ・ビルド・package スクリプト（`setup.py`、`packaging/**`、vision build の batch など）が
    読む変数は本文を作る対象。エンジン実行で読まないからと no-doc にするのは誤り（CUDA_PATH で実際に起きた）。
    再依頼では `001_investigation.md` の「調査対象と結界」の該当文を引用して範囲を示すと直る。
- 終了時サマリ `残りの未作成 N 件（未調査 M 件 / 試行済み K 件）` の **M が 0 なら飽和**。
  その索引に対しては作れる文書は揃った（残りは Strata が読まない名前）と判断してよい。
- codex の終了コードが 0 でも本文が増えていなければ `no-doc`。件数が増えない週が続いたら
  `check-docs.py` の孤児・綴りチェックを疑う。

## CLI 側（`create-cli-docs.py`）

- 候補は `docs/cli/README.md` の Markdown リンク（`- [..](path)`）のうち、存在しないもの。
  索引に予定リンクとして載った瞬間に作成対象になる。`--dry-run` は無いので、`-l` で件数を刻む。
- `-l`, `--doc-limit N` / `-p`, `--parallel N` のみ。試行記録は持たない（索引にリンクがあれば再現する）。
- 対象が `<command-path>/README.md` ならコマンド概要、`--option.md` / `-x.md` ならオプション文書になる。
  概要の基準文書は `docs/cli/strata-terminal/launch/README.md`（スクリプトが参照）。

## codex 実行の形（両スクリプト共通）

```bash
codex exec --skip-git-repo-check --sandbox workspace-write \
  --cd "$HOME/src/github.com/sasasin/strata-envvars" \
  --output-last-message <tmp>/last-message.md <prompt>
```

- `--sandbox workspace-write` なので、Strata 側は読み取り専用になる（Strata を workspace 外に置く運用）。
- 各セッションの last message に「索引との食い違い」報告が出ることがある。`no-doc` の理由として
  後から読めるようにログを残す（リポジトリには置かない）。

## 並列数と時間の実測メモ（2026-11 時点）

- Codex（GPT-6 Luna xhigh）で envvars 737 件の作成を走らせ、5 時間制限を 1.6 回使った。
  並列数と制限消費のバランスは見ながら調整する。
- 手元 PC（Radeon R9700 1 枚、OpenCode + Strata Qwen3.8 Flash Next IQ2_XXS、reasoning effort=high）では
  1 変数に 5〜15 分かかった。全件（1600 件超）をこのペースで回すのは現実的でない。
- CLI 側は 1 件が軽いので `-p 12` 程度まで張った実績がある。envvars 側は `-p 5` 前後。

## 実行後の確認

```bash
python3 .agents/skills/strata-investigate/scripts/check-docs.py --stale
git -C "$HOME/src/github.com/Niko1221/Strata" rev-parse HEAD   # 文書に書いた SHA と付き合わせる
```

1 件の追加・削除なら差分をそのままコミット。まとまった件数の作成は、索引更新コミットと
本文作成コミットを分ける（コミットメッセージの例: `増えた環境変数 737 件の調査文書を作成した`）。
