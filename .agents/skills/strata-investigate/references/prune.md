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
- 索引に残っている + 本文だけ要りそうな気がしない → 触らない。改名・移動は `docs/cli/001_investigation.md` の配置規約に沿って `git mv` し、索引リンクを同期する。
- 廃止されたが履歴として残す価値がある項目は、削除せず本文冒頭に廃止状態を書き、索引側にもその旨を残す（`docs/cli/001_investigation.md` 手順 8）。

## 4. 未実装（スコープ外）: 変更検出

「Strata 側で挙動が変わったため既存文書が陳腐化した」検出は未定義。実装するなら次の形が想定される
（今回は作らない。`check-docs.py --stale` は commit 別の件数を出すだけで、内容の差分は判定しない）。

- 各 envvars 文書の `## 根拠` にある `path:line` を逆引き表（変数 → 実装ファイル）にする。
- Strata 側で `git diff <prev-doc-sha>..HEAD -- <そのファイル>` を取り、差分がその環境変数の読み取り付近に触れていれば再調査候補として並べる。
- 再調査は 1 変数 1 セッション（`create-envvars-docs.py` と同じ形）で、既存文書を上書き更新する。
