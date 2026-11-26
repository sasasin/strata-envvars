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
  存在しないものを**先に確定してから** 1 変数 1 セッションでエージェントを起動する。
  古い `seq | xargs` 運用と違い、並列でも同じ変数を重複調査せず、全件作成済みなら何も作らない。
- 主なフラグ
  - `-l`, `--doc-limit N` … 今回作成する件数上限（`0` で全件、既定 1）
  - `-p`, `--parallel N` … 同時に動かすエージェント数（既定 1）
  - `-r`, `--runner {codex,pi}` … 調査を任せるエージェント（既定 codex。次節）
  - `--dry-run` … 起動せず対象を一覧する（**実行前に必ずこれで目視**）
  - `--include-tried` … 調べても文書ができなかった変数を再調査候補に加える
  - `--reset-state` … 試行記録を消して組み直す（全履歴を失うので通常は使わない）
  - `--stale-report PATH` … `find-stale.py` の報告（既定 `.strata-stale.json`）。陳腐化で削除した変数の
    調査対象 SHA・触れたコミット・差分の抜書を codex への依頼文に添える。報告の revision が Strata HEAD と
    違う場合は自動で無視する（`create-cli-docs.py` にも同じオプションがある）。
    `unknown-sha` には「索引 SHA と N 文字差」の候補も添えられる
- 試行記録は `.create-envvars-docs.state.json`（`{変数名: {attempts, status, updated_at}}`）。
  `status` は `created` / `no-doc`（Strata が実際には読まない候補。`001_investigation.md` の手順どおり
  「索引との食い違い」として報告され、文書は作られない）/ `error`。
  既定では `status` の有無に関わらず記録済みの変数を避け、`--include-tried` で再調査する。
- no-doc の中身は二種類ある。判定を間違えやすい方:
  - Strata がまったく読まない名前（外部 lib・driver 専用、索引の誤拾い）→ 本文は作らない。
  - **Strata が読むが、読み取り箇所がテスト・parity 専用コードだけ**（GEMV_X、QUANT_CTAB、
    STRATA_WMMA_PARITY_EXACT など）→ `001_investigation.md` が実装根拠にしないと決めているので本文は作らない。
    索引には残す。索引は grep 由来の候補一覧で、テスト・開発/e2e スクリプトだけが読む名前も載せる決まり
    （`extraction-recipes.md` §5）。
  - 逆に、セットアップ・ビルド・package スクリプト（`**/setup.py`、`**/packaging/**`、vision build の batch など。
    2026-11 時点では `terminal/setup.py` と `tools/packaging/**`）が
    読む変数は本文を作る対象。エンジン実行で読まないからと no-doc にするのは誤り（CUDA_PATH で実際に起きた）。
    再依頼では `001_investigation.md` の「調査対象と結界」の該当文を引用して範囲を示すと直る。
- 終了時サマリ `残りの未作成 N 件（未調査 M 件 / 試行済み K 件）` の **M が 0 なら飽和**。
  その索引に対しては作れる文書は揃った（残りは Strata が読まない名前）と判断してよい。
- エージェントの終了コードが 0 でも本文が増えていなければ `no-doc`。件数が増えない週が続いたら
  `check-docs.py` の孤児・綴りチェックを疑う。

## CLI 側（`create-cli-docs.py`）

- 候補は `docs/cli/README.md` の Markdown リンク（`- [..](path)`）のうち、存在しないもの。
  索引に予定リンクとして載った瞬間に作成対象になる。`--dry-run` は無いので、`-l` で件数を刻む。
- `-l`, `--doc-limit N` / `-p`, `--parallel N` のみ。試行記録は持たない（索引にリンクがあれば再現する）。
- 対象が `<command-path>/README.md` ならコマンド概要、`--option.md` / `-x.md` ならオプション文書になる。
  概要の書式と詳しさは `docs/cli/001_investigation.md` の「コマンド概要の内容」（特定の文書を手本にしない）。
- `--help` は索引に載せない決まりなので作成対象にならない（`index-refresh.md` §3）。索引に `--help.md` へのリンクが紛れ込んでいたら、作成せず索引側を直す。

## ランナー実行の形（両スクリプト共通）

起動部はリポジトリ直下の `agent_runner.py` に集めてある。依頼文（`PROMPT_TEMPLATE`）は
ランナー間で同一。候補選択・試行記録・陳腐化報告の付与は各スクリプト側。

### codex（既定）

```bash
codex exec --model gpt-6-luna --config model_reasoning_effort=high \
  --skip-git-repo-check --sandbox workspace-write \
  --cd "$HOME/src/github.com/sasasin/strata-envvars" \
  --output-last-message <tmp>/last-message.md <prompt>
```

- `--sandbox workspace-write` なので、Strata 側は読み取り専用になる（Strata を workspace 外に置く運用）。

### pi

```bash
pi --provider ollama-cloud --model deepseek-v4.1-flash:1017 --thinking high \
  --print --no-session --no-approve --no-extensions --no-mcp --no-skills \
  --tools read,bash,edit,write -- <prompt>
```

- cwd はリポジトリ直下（`subprocess` の `cwd`）。`--print` の stdout が最終応答、stderr がログ。
  codex の `--output-last-message` 相当は無い。
- `--no-extensions --no-mcp --no-skills` と `--tools` で、web 検索・MCP・この skill 自体を
  モデルに宣言しない。Strata のソースだけを一次情報にする基準を、依頼文だけでなくツール側でも絞る。
  `--tools ''` は Pi 側の既定ツール構成に戻すだけで、skill・拡張・MCP は引き続き読み込まない。
- **codex の `--sandbox workspace-write` に相当する強制は Pi に無い。** Strata を書き換えないのは
  依頼文の制約だけなので、`-r pi` で回した後は `git -C "$HOME/src/github.com/Niko1221/Strata" status --short`
  が clean であることを目視する。
- ollama-cloud の契約上、同時実行数は 3 まで。`-p` は 3 以下で使う（スクリプト側にガードはない）。
- `--model` / `--thinking` は両ランナー共通の上書きオプション。`--provider` と `--tools` は `-r pi` のときだけ効く。

### 共通

- 各セッションの last message に「索引との食い違い」報告が出ることがある。`no-doc` の理由として
  後から読めるようにログを残す（リポジトリには置かない）。

## 並列数の目安

- Codex: envvars は `-p 5` 前後、CLI は 1 件が軽いので `-p 12` 程度まで張れる。
- `-r pi`（ollama-cloud）: 契約上の同時実行数が 3 までなので `-p 3` 以下で使う。
- ローカルモデルで回すと 1 変数に数十分かかる。全件をローカルで回すのは現実的でない。
- Pi 版の文書は codex 版より長くなりがち。見出し構成は `docs/cli/001_investigation.md` に従い
  `path:line` の裏付けも出るが、分量を揃えたいなら依頼文側で絞る（ランナー中立の文なので codex にも効く）。

## 実行後の確認

```bash
python3 .agents/skills/strata-investigate/scripts/check-docs.py --stale
git -C "$HOME/src/github.com/Niko1221/Strata" rev-parse HEAD   # 文書に書いた SHA と付き合わせる
```

1 件の追加・削除なら差分をそのままコミット。まとまった件数の作成は、索引更新コミットと
本文作成コミットを分ける（コミットメッセージの例: `増えた環境変数 737 件の調査文書を作成した`）。
