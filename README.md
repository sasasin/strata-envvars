# strata-envvars

Strata で使用可能な環境変数がリリースの度に増えてるようで追いきれない。

そこで、

1. リリースノート眺めて目に入った環境変数ひとつをピックアップして、何をどう使ってる環境変数なのか、どういう値を設定できるのか、どういう条件が満たされたら使われるのか、実行時にどう効いてるのか、、、といった私が知りたい事柄の要望を詰めて、会話ラリーして調査させてサンプルとして1本をコーディングエージェントに仕上げてもらう。
1. このサンプルと、サンプルを作り上げた過程をもとに、環境変数1個を渡されてから仕上げるまでの調査マニュアルを、コーディングエージェントに作ってもらう。
1. 環境変数の一覧をコーディングエージェントに作ってもらう。550個ありました。
1. 最後に、こんな感じでコーディングエージェントに1セッションで1個の環境変数を調査してもらう

```bash
seq $(wc -l $HOME/src/github.com/Niko1221/Strata-EnvVars/000_envvers.md) \
| xargs -P6 -L1 -I{} time codex exec --skip-git-repo-check --sandbox 'workspace-write' \
'調査依頼です。調査対象ソースコードは `$HOME/src/github.com/Niko1221/Strata` です。 `$HOME/src/github.com/Niko1221/Strata-EnvVars/000_envvers.md` から、 `$HOME/src/github.com/Niko1221/Strata-EnvVars/` に調査結果ファイルが存在しない環境変数を、任意に1個を選んで、 `$HOME/src/github.com/Niko1221/Strata-EnvVars/001_investigation.md` の指示に従って、 `$HOME/src/github.com/Niko1221/Strata-EnvVars/` に調査結果ファイルを作成してください。環境変数1個ずつ調べてください。'
```

私の手元では OpenAI Codex で GPT-6 Luna xhigh で、5時間制限 1.6 回くらいで完走しました。xargs の並列数の増減と、5時間制限の消費を見ながら、ペース配分はお好みで。

なお手元パソコンで Radeon R9700 1枚で OpenCode で Strata Qwen3.8 Flash Next IQ2_XXS reasonig_efort=high でやらせたら、1変数に5分から15分くらい要してました。このペースでは何日かかるかわからんぞ...と。いうことで、私は手元で使用枠の余ってた Codex でガッとやらせました。

# つまり何を設定したら prefill や decode が増えるのよ!!

コーディングエージェントに、こんなプロンプトで調べさせて、設定反映、Strata再起動、(あれば)ベンチマーキング or 動作確認、を何周かすると、それなりに速度改善します。

> このパソコンには AMD Radeon AI PRO R9700 を1枚だけ挿してあり、推論エンジン Strata の GPU として利用しています。Strata の実行には run-iq2_xs.sh を用いています。prefill や decode の高速化のため、どのようなコマンドラインオプションや環境変数を利用できるか、Strata ソースコードを詳しく読解して、いくつか提案してください

このとき様々な環境変数を推奨してくるので、このリポジトリの md をチラ見するといいんじゃないかな。

# 最新版 Strata ソースコードに追従

[Strata の Release](https://github.com/Niko1221/Strata/releases) に新たなバージョンが公開されたら、手元の Strata ソースコードを最新化します。

```bash
cd $HOME/src/github.com/Niko1221/Strata
git pull
```

環境変数の一覧の最新化。

```bash
codex exec --skip-git-repo-check --sandbox 'workspace-write' '調査依頼です。調査対象ソースコードは `$HOME/src/github.com/Niko1221/Strata` です。ソースコードを網羅的に grep して、使用可能な環境変数を一覧化しただけの Markdown ファイルを作成してください。Markdown ファイル名は `$HOME/src/github.com/sasasin/strata-envvars/docs/000_envvers.md` としてください。環境変数名でソートしてください。'
```

消えた環境変数の md の削除。

```bash
codex exec --skip-git-repo-check --sandbox 'workspace-write' '`$HOME/src/github.com/sasasin/strata-envvars/docs/000_envvers.md` の git diff にもとづいて、削除された環境変数に対応する docs/${環境変数名}.md を削除してください'
```

増えた環境変数の md の作成。

```bash
seq 100 | xargs -P5 -L1 -I{} time codex exec --skip-git-repo-check --sandbox 'workspace-write' '調査依頼です。調査対象ソースコードは `$HOME/src/github.com/Niko1221/Strata` です。 `$HOME/src/github.com/sasasin/strata-envvars/docs/000_envvers.md` から、 `$HOME/src/github.com/sasasin/strata-envvars/docs/` に調査結果ファイルが存在しない環境変数を、任意に1個を選んで、 `$HOME/src/github.com/sasasin/strata-envvars/docs/001_investigation.md` の指示に従って、 `$HOME/src/github.com/sasasin/strata-envvars/docs/` に調査結果ファイルを作成してください。環境変数1個ずつ調べてください。'
```

変更のあった環境変数の md の更新。

```bash
echo "i have no idea"
```

# コマンドライン引数

環境変数もそうだけど、コマンドライン引数も興味がある。
