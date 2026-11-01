# 削除（prune）手順

索引から消えた項目の本文を後片付けする手順。**索引側が消えたことを確認してから**本文を消す。
Strata 側で消えたように見えても、読み取り箇所が別ファイルに移っただけのことがあるため、
索引の差分だけを見て本文を消すのは危険な操作だと前提にする。

## 1. 環境変数

1. 索引の差分から消えた名前を出す。

   ```bash
   cd "$HOME/src/github.com/sasasin/strata-envvars"
   git diff HEAD~1 -- docs/envvars/000_envvers.md | grep '^- - `' | sed 's/^- - `\(.*\)`$/\1/'
   ```

   （前回の索引更新が複数コミットに分かれている場合は `<prev-index-commit>` を指定する。）
2. 消えた名前 1 件ずつ、Strata 現行 checkout でまだ読まれていないか確認する。

   ```bash
   rg -n --hidden --glob '!.git/**' 'NAME' "$HOME/src/github.com/Niko1221/Strata"
   ```

   まだ読み取り箇所があるのに索引から消えたなら、**削除ではなく索引の落ち度**なので `index-refresh.md` §1 に戻る。
3. 確認できたものだけ本文を消す。

   ```bash
   git rm docs/envvars/<NAME>.md
   ```

4. 索引に `<NAME>` のリンク残骸が無いことを確認する（索引に一覧以外のリンクは無いが、他文書からの参照は残る）。
   他文書が参照している場合は、参照元の記述が誤りなので、その 1 文だけ現行実装に合わせて直す（文書全体の書き換えは別依頼）。
5. 試行記録 `.create-envvars-docs.state.json` に同名の entry が残っていると、次回 `create-envvars-docs.py` が
   「試行済み」扱いして再調査しない。**索引から消えた名前は entry も消す**。

   ```bash
   python3 - <<'PY'
   import json, pathlib
   p = pathlib.Path(".create-envvars-docs.state.json")
   d = json.loads(p.read_text())
   for name in ["NAME1", "NAME2"]:
       d.pop(name, None)
   p.write_text(json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
   PY
   ```

   （`--reset-state` は全記録を消すので使わない。）

## 2. CLI 文書

1. 索引の差分で、削除されたリンクを出す。

   ```bash
   cd "$HOME/src/github.com/sasasin/strata-envvars"
   git diff HEAD~1 -- docs/cli/README.md | grep '^- - \[' | sed 's/^- \[[^]]*\](\([^)]*\)).*/\1/'
   ```

2. 各パスが現行 parser にまだ存在するか確認する（`extraction-recipes.md` §3 で grammar を機械抽出して突き合わせる）。
   コマンド自体が消えた場合は、その command path 配下をまとめて対象にする。
3. 本文とコマンド概要を消す。

   ```bash
   git rm "docs/cli/<tool-id>/<command-path>/<option>.md"
   rmdir --ignore-fail-on-non-empty "docs/cli/<tool-id>/<command-path>"   # 空になった節ディレクトリ
   ```

4. tool-id ごと消えた場合は、`docs/cli/000_cli_tools.md` の入口一覧と `docs/cli/README.md` の
   `## \`tool-id\`` 節が既に更新済みであることを確認する（索引更新を先に済ませていないなら、ここで本文削除をやめる）。
5. 空ディレクトリと孤児が残っていないか `check-docs.py` で確認する。

   ```bash
   python3 .agents/skills/strata-investigate/scripts/check-docs.py --strict
   ```

## 3. 削除のときの決め手

- 索引から消えた + 現行 Strata に読み取り/宣言箇所が無い → 削除してよい。
- 索引から消えた + 現行 Strata にまだ在る → 索引を直す（本文は残す）。
- 索引に残っている + 読み取りがテスト・parity 専用コードだけ → 本文は作らず `no-doc` で記録し、索引はそのまま残す（索引は候補一覧で、テスト系の変数を内訳に含めている）。
- 索引に残っている + セットアップ・ビルド・package スクリプトだけが読む → 本文を作る対象。エンジン実行で読まないことは no-doc の理由にならない。
- 索引に残っている + 本文だけ要りそうな気がしない → 触らない。改名・移動は `docs/cli/001_investigation.md` の配置規約に沿って `git mv` し、索引リンクを同期する。
- 廃止されたが履歴として残す価値がある項目は、削除せず本文冒頭に廃止状態を書き、索引側にもその旨を残す（`docs/cli/001_investigation.md` 手順 8）。

## 4. 品質不足による作り直し（本文の削除 → 再作成）

`check-docs.py` が報告する「必須節の欠落」のように、既存本文が `001_investigation.md` の品質基準を満たさない場合の再作成手順:

1. 対象を `git rm docs/envvars/<NAME>.md` で消す。
2. 索引の名前は消さない（Strata が読むことは既に確認済みのため）。
3. 試行記録から該当 entry を消して「未調査」に戻す（§1 の python で `d.pop(name)`）。
4. `uv run ./create-envvars-docs.py --dry-run -l <件数>` で対象に意図しない変数が混じっていないか確認し、
   `-l <件数>` で実際に回す。
5. `no-doc` で戻ってきた場合は §3 の決め手で切り分ける。セットアップ・ビルド系なら
   `references/runner.md` の no-doc 節を参考に、調査範囲を引用した追加指示で 1 件ずつ再依頼する。
6. `python3 .agents/skills/strata-investigate/scripts/check-docs.py` で「必須節の欠落 0 件」を確認してコミットする。

陳腐化した可能性のある文書をまとめて探す場合は、この節の手動運用ではなく `references/staleness.md`（
`find-stale.py` → `mark-stale.py`）を使う。削除→再作成の流れは同じ。

## 5. 実装済み: 内容の陳腐化検出

「Strata 側で挙動が変わったため既存文書が陳腐化した」検出は `references/staleness.md` に実装した
（`scripts/evidence-index.py` / `scripts/find-stale.py` / `scripts/mark-stale.py` / `scripts/cli-grammar.py`）。
逆引きは envvars 文書の `## 根拠` にある `path:line` を機械抽出した台帳（`.strata-evidence.json`）が担い、
削除は上記 §4 と同じ流れ（本文を消して試行記録から entry を消す）で再作成に繋がる。
